from typing import List, Dict, Any, Optional, Tuple
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(
        self,
        vector_store,
        bm25_index,
        embedding_service,
        rrf_k: int = 60
    ):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.embedding_service = embedding_service
        self.rrf_k = rrf_k

    def hybrid_search(
        self,
        knowledge_base_id: int,
        query: str,
        top_k: int = 10,
        rerank_n: int = 5,
        filter_document_ids: Optional[List[int]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        debug_info = {}

        query_embedding = self.embedding_service.encode_text(query)

        semantic_results = self.vector_store.search(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            top_k=top_k,
            filter_document_ids=filter_document_ids
        )
        debug_info["semantic_retrieval"] = self._format_debug_results(semantic_results, "semantic_score")
        logger.info(f"Semantic search returned {len(semantic_results)} results")

        bm25_results = self.bm25_index.search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=top_k
        )
        debug_info["bm25_retrieval"] = self._format_debug_results(bm25_results, "bm25_score")
        logger.info(f"BM25 search returned {len(bm25_results)} results")

        fused_results = self._rrf_fusion(semantic_results, bm25_results, top_k * 2)
        debug_info["rrf_fusion"] = self._format_debug_results(fused_results, "rrf_score")
        logger.info(f"RRF fusion returned {len(fused_results)} results")

        if len(fused_results) > 0:
            reranked_results = self._rerank(query, fused_results, rerank_n)
            debug_info["reranked"] = self._format_debug_results(reranked_results, "rerank_score")
            logger.info(f"Reranking returned {len(reranked_results)} results")
            final_results = reranked_results
        else:
            final_results = []
            debug_info["reranked"] = []

        return final_results, debug_info

    def _rrf_fusion(
        self,
        semantic_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        top_n: int = 20
    ) -> List[Dict[str, Any]]:
        scores = defaultdict(lambda: {"semantic_score": 0, "bm25_score": 0, "rrf_score": 0})
        chunk_data = {}

        for rank, result in enumerate(semantic_results, 1):
            chunk_id = result.get("chunk_id")
            if chunk_id is None:
                continue
            scores[chunk_id]["semantic_score"] = result.get("semantic_score", 0)
            scores[chunk_id]["rrf_score"] += 1 / (self.rrf_k + rank)
            chunk_data[chunk_id] = result

        bm25_by_id = {}
        for result in bm25_results:
            chunk_id = result.get("chunk_id")
            if chunk_id is not None:
                bm25_by_id[chunk_id] = result.get("bm25_score", 0)

        for rank, result in enumerate(bm25_results, 1):
            chunk_id = result.get("chunk_id")
            if chunk_id is None:
                continue
            scores[chunk_id]["bm25_score"] = result.get("bm25_score", 0)
            scores[chunk_id]["rrf_score"] += 1 / (self.rrf_k + rank)
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = {
                    "chunk_id": chunk_id,
                    "content": "",
                    "document_id": 0,
                    "chunk_index": 0,
                    "page_number": 0,
                }

        fused = []
        for chunk_id, score_data in scores.items():
            if chunk_id in chunk_data:
                result = chunk_data[chunk_id].copy()
                result["semantic_score"] = score_data["semantic_score"]
                result["bm25_score"] = score_data["bm25_score"]
                result["rrf_score"] = score_data["rrf_score"]
                fused.append(result)

        fused.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fused[:top_n]

    def _rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        if not results:
            return []

        documents = [r.get("content", "") for r in results]
        ranked_indices, scores = self.embedding_service.rerank(query, documents, top_n)

        reranked = []
        for i, idx in enumerate(ranked_indices):
            if idx < len(results):
                result = results[idx].copy()
                result["rerank_score"] = float(scores[idx])
                reranked.append(result)

        return reranked

    def _format_debug_results(self, results: List[Dict[str, Any]], score_key: str) -> List[Dict[str, Any]]:
        formatted = []
        for r in results:
            formatted.append({
                "chunk_id": r.get("chunk_id"),
                "document_id": r.get("document_id"),
                "chunk_index": r.get("chunk_index"),
                "score": r.get(score_key, 0),
                "content_preview": r.get("content", "")[:100] + "..." if len(r.get("content", "")) > 100 else r.get("content", "")
            })
        return formatted
