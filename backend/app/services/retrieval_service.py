from typing import List, Dict, Any, Optional, Tuple
import logging
import time
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from collections import defaultdict
import numpy as np
from sklearn.decomposition import PCA

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

    def search_with_strategy(
        self,
        knowledge_base_id: int,
        query: str,
        strategy: Dict[str, Any],
        return_timing: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Optional[float]]:
        start_time = time.time()
        debug_info = {}
        query_embedding = self.embedding_service.encode_text(query)

        semantic_top_k = strategy.get("semantic_top_k", 20)
        bm25_top_k = strategy.get("bm25_top_k", 20)
        use_rrf = strategy.get("use_rrf", True)
        rrf_k = strategy.get("rrf_k", self.rrf_k)
        use_rerank = strategy.get("use_rerank", True)
        rerank_n = strategy.get("rerank_n", 5)

        semantic_results = self.vector_store.search(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            top_k=semantic_top_k
        )
        debug_info["semantic_retrieval"] = self._format_debug_results(semantic_results, "semantic_score")

        bm25_results = self.bm25_index.search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=bm25_top_k
        )
        debug_info["bm25_retrieval"] = self._format_debug_results(bm25_results, "bm25_score")

        if use_rrf:
            fused_results = self._rrf_fusion_with_k(semantic_results, bm25_results, max(semantic_top_k, bm25_top_k) * 2, rrf_k)
            debug_info["rrf_fusion"] = self._format_debug_results(fused_results, "rrf_score")
        else:
            combined = {}
            for r in semantic_results:
                combined[r["chunk_id"]] = r
            for r in bm25_results:
                if r["chunk_id"] not in combined:
                    combined[r["chunk_id"]] = r
            fused_results = list(combined.values())
            fused_results.sort(key=lambda x: x.get("semantic_score", 0) + x.get("bm25_score", 0), reverse=True)
            fused_results = fused_results[:max(semantic_top_k, bm25_top_k)]
            debug_info["rrf_fusion"] = []

        if use_rerank and len(fused_results) > 0:
            reranked_results = self._rerank(query, fused_results, rerank_n)
            debug_info["reranked"] = self._format_debug_results(reranked_results, "rerank_score")
            final_results = reranked_results
        else:
            final_results = fused_results[:rerank_n] if len(fused_results) > rerank_n else fused_results
            debug_info["reranked"] = []

        elapsed_ms = (time.time() - start_time) * 1000
        if return_timing:
            return final_results, debug_info, elapsed_ms
        return final_results, debug_info, None

    def _rrf_fusion_with_k(
        self,
        semantic_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        top_n: int,
        rrf_k: int
    ) -> List[Dict[str, Any]]:
        scores = defaultdict(lambda: {"semantic_score": 0, "bm25_score": 0, "rrf_score": 0})
        chunk_data = {}

        for rank, result in enumerate(semantic_results, 1):
            chunk_id = result.get("chunk_id")
            if chunk_id is None:
                continue
            scores[chunk_id]["semantic_score"] = result.get("semantic_score", 0)
            scores[chunk_id]["rrf_score"] += 1 / (rrf_k + rank)
            chunk_data[chunk_id] = result

        for rank, result in enumerate(bm25_results, 1):
            chunk_id = result.get("chunk_id")
            if chunk_id is None:
                continue
            scores[chunk_id]["bm25_score"] = result.get("bm25_score", 0)
            scores[chunk_id]["rrf_score"] += 1 / (rrf_k + rank)
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

    def search_multiple_kb(
        self,
        knowledge_base_ids: List[int],
        query: str,
        strategy: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        rerank_n: int = 5,
        parallel: bool = True
    ) -> Dict[int, Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
        results = {}
        
        if not parallel or len(knowledge_base_ids) <= 1:
            for kb_id in knowledge_base_ids:
                if strategy:
                    retrieval_results, debug_info, _ = self.search_with_strategy(kb_id, query, strategy)
                else:
                    retrieval_results, debug_info = self.hybrid_search(kb_id, query, top_k, rerank_n)
                results[kb_id] = (retrieval_results, debug_info)
            return results

        def _search_kb(kb_id: int) -> Tuple[int, List[Dict[str, Any]], Dict[str, Any]]:
            if strategy:
                retrieval_results, debug_info, _ = self.search_with_strategy(kb_id, query, strategy)
            else:
                retrieval_results, debug_info = self.hybrid_search(kb_id, query, top_k, rerank_n)
            return (kb_id, retrieval_results, debug_info)

        with ThreadPoolExecutor(max_workers=min(len(knowledge_base_ids), 4)) as executor:
            futures = [executor.submit(_search_kb, kb_id) for kb_id in knowledge_base_ids]
            for future in futures:
                kb_id, retrieval_results, debug_info = future.result()
                results[kb_id] = (retrieval_results, debug_info)
        
        return results

    def get_visualization_data(
        self,
        knowledge_base_id: int,
        query: str,
        retrieval_results: List[Dict[str, Any]],
        filter_document_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        if not retrieval_results:
            return {
                "query_point": None,
                "chunks": [],
                "score_data": [],
                "explained_variance_ratio": [0, 0]
            }

        chunk_ids = [r["chunk_id"] for r in retrieval_results]
        document_ids = list(set([r["document_id"] for r in retrieval_results]))

        collection_name = self.vector_store._get_collection_name(knowledge_base_id, "text")
        try:
            collection = self.vector_store.client.get_collection(name=collection_name)
        except Exception as e:
            logger.warning(f"Collection {collection_name} not found: {e}")
            return {
                "query_point": None,
                "chunks": [],
                "score_data": [],
                "explained_variance_ratio": [0, 0]
            }

        where = {"chunk_id": {"$in": [str(cid) for cid in chunk_ids]}}
        try:
            chunk_data = collection.get(
                where=where,
                include=["embeddings", "metadatas", "documents"]
            )
        except Exception as e:
            logger.error(f"Failed to get chunk embeddings: {e}")
            return {
                "query_point": None,
                "chunks": [],
                "score_data": [],
                "explained_variance_ratio": [0, 0]
            }

        if not chunk_data.get("embeddings") or len(chunk_data["embeddings"]) == 0:
            return {
                "query_point": None,
                "chunks": [],
                "score_data": [],
                "explained_variance_ratio": [0, 0]
            }

        query_embedding = self.embedding_service.encode_text(query)
        all_embeddings = np.array(chunk_data["embeddings"])
        all_embeddings = np.vstack([all_embeddings, query_embedding])

        n_samples = all_embeddings.shape[0]
        n_components = min(2, n_samples - 1) if n_samples > 1 else 1

        if n_samples > 2:
            pca = PCA(n_components=n_components, random_state=42)
            reduced = pca.fit_transform(all_embeddings)
            explained_variance = pca.explained_variance_ratio_.tolist()
            if len(explained_variance) < 2:
                explained_variance = explained_variance + [0] * (2 - len(explained_variance))
        else:
            reduced = all_embeddings[:, :2] if all_embeddings.shape[1] >= 2 else np.hstack([all_embeddings, np.zeros((n_samples, 1))])
            explained_variance = [0.5, 0.5]

        result_map = {r["chunk_id"]: r for r in retrieval_results}
        chunks_visual = []
        score_data = []

        for i in range(len(chunk_data["ids"])):
            metadata = chunk_data["metadatas"][i]
            chunk_id = int(metadata.get("chunk_id", 0))
            document_id = int(metadata.get("document_id", 0))
            chunk_index = int(metadata.get("chunk_index", 0))
            content = chunk_data["documents"][i]
            result = result_map.get(chunk_id, {})
            relevance_score = result.get("rerank_score") or result.get("rrf_score") or result.get("semantic_score", 0)

            chunks_visual.append({
                "x": float(reduced[i, 0]),
                "y": float(reduced[i, 1]),
                "chunk_id": chunk_id,
                "document_id": document_id,
                "document_title": result.get("document_title", "Unknown"),
                "chunk_index": chunk_index,
                "content_preview": content[:100] + "..." if len(content) > 100 else content,
                "relevance_score": float(relevance_score)
            })

            score_data.append({
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "document_title": result.get("document_title", "Unknown"),
                "semantic_score": float(result.get("semantic_score", 0)),
                "bm25_score": float(result.get("bm25_score", 0)),
                "rrf_score": float(result.get("rrf_score", 0)),
                "rerank_score": float(result.get("rerank_score", 0)),
                "content_preview": content[:100] + "..." if len(content) > 100 else content
            })

        query_point = {
            "x": float(reduced[-1, 0]),
            "y": float(reduced[-1, 1]),
            "chunk_id": -1,
            "document_id": -1,
            "document_title": "用户问题",
            "chunk_index": -1,
            "content_preview": query[:100] + "..." if len(query) > 100 else query,
            "relevance_score": 1.0
        }

        return {
            "query_point": query_point,
            "chunks": chunks_visual,
            "score_data": score_data,
            "explained_variance_ratio": explained_variance
        }
