import jieba
import math
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.knowledge_base_indices = {}
        self.db_session = None

    def set_db_session(self, db_session):
        self.db_session = db_session

    def load_from_db(self, knowledge_base_id: int):
        from .. import models

        if not self.db_session:
            logger.warning("No DB session available for loading BM25 index")
            return

        db_indices = self.db_session.query(models.BM25Index).filter(
            models.BM25Index.knowledge_base_id == knowledge_base_id
        ).all()

        if not db_indices:
            return

        doc_ids = []
        doc_tokens = []
        doc_lengths = []
        tf = []
        doc_freq = defaultdict(int)

        for idx in db_indices:
            chunk_ids = idx.chunk_ids
            for chunk_id in chunk_ids:
                if chunk_id not in doc_ids:
                    doc_ids.append(chunk_id)

        for doc_id in doc_ids:
            chunk = self.db_session.query(models.Chunk).filter(
                models.Chunk.id == doc_id
            ).first()
            if chunk:
                tokens = self.tokenize(chunk.content)
                doc_tokens.append(tokens)
                doc_lengths.append(len(tokens))

                term_freq = defaultdict(int)
                for token in tokens:
                    term_freq[token] += 1
                tf.append(term_freq)

                unique_tokens = set(tokens)
                for token in unique_tokens:
                    doc_freq[token] += 1

        N = len(doc_ids)
        avgdl = sum(doc_lengths) / N if N else 0

        idf = {}
        for token, freq in doc_freq.items():
            idf[token] = math.log((N - freq + 0.5) / (freq + 0.5) + 1)

        self.knowledge_base_indices[knowledge_base_id] = {
            "doc_ids": doc_ids,
            "doc_tokens": doc_tokens,
            "doc_lengths": doc_lengths,
            "avgdl": avgdl,
            "tf": tf,
            "idf": idf,
            "doc_freq": doc_freq,
            "N": N,
        }

        logger.info(f"Loaded BM25 index from DB for KB {knowledge_base_id}: {N} documents")

    def load_all_from_db(self):
        from .. import models

        if not self.db_session:
            logger.warning("No DB session available for loading BM25 indices")
            return

        kb_ids = self.db_session.query(models.BM25Index.knowledge_base_id).distinct().all()
        for (kb_id,) in kb_ids:
            self.load_from_db(kb_id)

    def _save_to_db(self, knowledge_base_id: int):
        from .. import models

        if not self.db_session:
            return

        if knowledge_base_id not in self.knowledge_base_indices:
            return

        index = self.knowledge_base_indices[knowledge_base_id]

        self.db_session.query(models.BM25Index).filter(
            models.BM25Index.knowledge_base_id == knowledge_base_id
        ).delete()

        keyword_inverted = defaultdict(list)
        for i, doc_id in enumerate(index["doc_ids"]):
            for token in index["doc_tokens"][i]:
                if doc_id not in keyword_inverted[token]:
                    keyword_inverted[token].append(doc_id)

        for keyword, chunk_ids in keyword_inverted.items():
            db_idx = models.BM25Index(
                knowledge_base_id=knowledge_base_id,
                keyword=keyword,
                chunk_ids=chunk_ids,
                doc_freq=len(chunk_ids)
            )
            self.db_session.add(db_idx)

        self.db_session.commit()
        logger.info(f"Saved BM25 index to DB for KB {knowledge_base_id}")

    def _get_stopwords(self) -> set:
        return {
            '的', '了', '和', '是', '就', '都', '而', '及', '与', '等',
            '也', '在', '这', '那', '有', '不', '人', '我', '你', '他',
            '她', '它', '们', '个', '上', '下', '中', '为', '以', '于',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'and', 'or', 'but', 'if', 'then', 'else', 'when', 'at',
            'by', 'for', 'with', 'about', 'against', 'between', 'into',
        }

    def tokenize(self, text: str) -> List[str]:
        stopwords = self._get_stopwords()
        words = jieba.cut_for_search(text.lower())
        return [w.strip() for w in words if w.strip() and w not in stopwords and len(w) > 1]

    def build_index(self, knowledge_base_id: int, chunks: List[Dict[str, Any]]):
        doc_ids = []
        doc_tokens = []
        doc_lengths = []

        for chunk in chunks:
            chunk_id = chunk.get("id") or chunk.get("chunk_id")
            content = chunk.get("content", "")
            tokens = self.tokenize(content)

            doc_ids.append(chunk_id)
            doc_tokens.append(tokens)
            doc_lengths.append(len(tokens))

        avgdl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0

        doc_freq = defaultdict(int)
        for tokens in doc_tokens:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1

        tf = []
        for tokens in doc_tokens:
            term_freq = defaultdict(int)
            for token in tokens:
                term_freq[token] += 1
            tf.append(term_freq)

        N = len(doc_ids)
        idf = {}
        for token, freq in doc_freq.items():
            idf[token] = math.log((N - freq + 0.5) / (freq + 0.5) + 1)

        self.knowledge_base_indices[knowledge_base_id] = {
            "doc_ids": doc_ids,
            "doc_tokens": doc_tokens,
            "doc_lengths": doc_lengths,
            "avgdl": avgdl,
            "tf": tf,
            "idf": idf,
            "doc_freq": doc_freq,
            "N": N,
        }

        self._save_to_db(knowledge_base_id)
        logger.info(f"BM25 index built for KB {knowledge_base_id}: {N} documents, {len(doc_freq)} unique terms")

    def search(
        self,
        knowledge_base_id: int,
        query: str,
        top_k: int = 10,
        filter_chunk_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        if knowledge_base_id not in self.knowledge_base_indices:
            logger.info(f"BM25 index not in memory for KB {knowledge_base_id}, trying to load from DB")
            self.load_from_db(knowledge_base_id)
            if knowledge_base_id not in self.knowledge_base_indices:
                logger.warning(f"No BM25 index for KB {knowledge_base_id}")
                return []

        index = self.knowledge_base_indices[knowledge_base_id]
        query_tokens = self.tokenize(query)

        if not query_tokens:
            return []

        scores = []
        filter_set = set(filter_chunk_ids) if filter_chunk_ids else None

        for i, doc_id in enumerate(index["doc_ids"]):
            if filter_set and doc_id not in filter_set:
                continue

            score = 0.0
            dl = index["doc_lengths"][i]
            avgdl = index["avgdl"]

            for token in query_tokens:
                if token not in index["idf"]:
                    continue

                idf = index["idf"][token]
                tf = index["tf"][i].get(token, 0)

                if tf == 0:
                    continue

                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (dl / avgdl))
                score += idf * (numerator / denominator)

            if score > 0:
                scores.append({
                    "chunk_id": doc_id,
                    "bm25_score": float(score),
                })

        scores.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scores[:top_k]

    def add_chunks(self, knowledge_base_id: int, new_chunks: List[Dict[str, Any]]):
        if knowledge_base_id not in self.knowledge_base_indices:
            self.build_index(knowledge_base_id, new_chunks)
            return

        index = self.knowledge_base_indices[knowledge_base_id]

        for chunk in new_chunks:
            chunk_id = chunk.get("id") or chunk.get("chunk_id")
            content = chunk.get("content", "")
            tokens = self.tokenize(content)

            index["doc_ids"].append(chunk_id)
            index["doc_tokens"].append(tokens)
            index["doc_lengths"].append(len(tokens))

            term_freq = defaultdict(int)
            for token in tokens:
                term_freq[token] += 1
            index["tf"].append(term_freq)

            unique_tokens = set(tokens)
            for token in unique_tokens:
                index["doc_freq"][token] = index["doc_freq"].get(token, 0) + 1

        index["N"] = len(index["doc_ids"])
        index["avgdl"] = sum(index["doc_lengths"]) / index["N"] if index["N"] else 0

        for token, freq in index["doc_freq"].items():
            index["idf"][token] = math.log((index["N"] - freq + 0.5) / (freq + 0.5) + 1)

        self._save_to_db(knowledge_base_id)
        logger.info(f"Added {len(new_chunks)} chunks to BM25 index for KB {knowledge_base_id}")

    def delete_chunks(self, knowledge_base_id: int, chunk_ids: List[int]):
        if knowledge_base_id not in self.knowledge_base_indices:
            return

        index = self.knowledge_base_indices[knowledge_base_id]
        delete_set = set(chunk_ids)

        keep_indices = []
        for i, doc_id in enumerate(index["doc_ids"]):
            if doc_id not in delete_set:
                keep_indices.append(i)

        if len(keep_indices) == len(index["doc_ids"]):
            return

        new_doc_ids = []
        new_doc_tokens = []
        new_doc_lengths = []
        new_tf = []
        new_doc_freq = defaultdict(int)

        for i in keep_indices:
            new_doc_ids.append(index["doc_ids"][i])
            new_doc_tokens.append(index["doc_tokens"][i])
            new_doc_lengths.append(index["doc_lengths"][i])
            new_tf.append(index["tf"][i])

            unique_tokens = set(index["doc_tokens"][i])
            for token in unique_tokens:
                new_doc_freq[token] += 1

        N = len(new_doc_ids)
        avgdl = sum(new_doc_lengths) / N if N else 0

        new_idf = {}
        for token, freq in new_doc_freq.items():
            new_idf[token] = math.log((N - freq + 0.5) / (freq + 0.5) + 1)

        self.knowledge_base_indices[knowledge_base_id] = {
            "doc_ids": new_doc_ids,
            "doc_tokens": new_doc_tokens,
            "doc_lengths": new_doc_lengths,
            "avgdl": avgdl,
            "tf": new_tf,
            "idf": new_idf,
            "doc_freq": new_doc_freq,
            "N": N,
        }

        self._save_to_db(knowledge_base_id)
        logger.info(f"Deleted {len(chunk_ids)} chunks from BM25 index for KB {knowledge_base_id}")

    def clear_index(self, knowledge_base_id: int):
        from .. import models

        if knowledge_base_id in self.knowledge_base_indices:
            del self.knowledge_base_indices[knowledge_base_id]

        if self.db_session:
            self.db_session.query(models.BM25Index).filter(
                models.BM25Index.knowledge_base_id == knowledge_base_id
            ).delete()
            self.db_session.commit()

        logger.info(f"BM25 index cleared for KB {knowledge_base_id}")
