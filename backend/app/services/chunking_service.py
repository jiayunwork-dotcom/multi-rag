import re
import jieba
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ChunkingService:
    def __init__(self, embedding_service=None):
        self.embedding_service = embedding_service
        self._init_tokenizer()

    def _init_tokenizer(self):
        try:
            import tiktoken
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            logger.warning("tiktoken not installed, using simple token counting")
            self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        return len(text) // 4

    def chunk(
        self,
        text: str,
        strategy: str = "token",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        semantic_threshold: float = 0.5,
        page_contents: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if not text.strip():
            return [], {"total_chunks": 0, "avg_chunk_length": 0, "max_chunk_length": 0, "min_chunk_length": 0}

        chunkers = {
            "token": self._chunk_by_token,
            "paragraph": self._chunk_by_paragraph,
            "semantic": self._chunk_by_semantic,
        }

        chunker = chunkers.get(strategy, self._chunk_by_token)
        chunks = chunker(text, chunk_size, chunk_overlap, semantic_threshold, page_contents)

        stats = self._compute_stats(chunks)
        return chunks, stats

    def _chunk_by_token(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        *args,
        **kwargs
    ) -> List[Dict[str, Any]]:
        chunks = []
        sentences = self._split_sentences(text)
        current_chunk = []
        current_length = 0
        chunk_index = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            token_count = self.count_tokens(sentence)

            if current_length + token_count > chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "chunk_index": chunk_index,
                    "content": chunk_text,
                    "token_count": self.count_tokens(chunk_text),
                })
                chunk_index += 1

                overlap_sentences = []
                overlap_length = 0
                for s in reversed(current_chunk):
                    s_len = self.count_tokens(s)
                    if overlap_length + s_len <= chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_length += s_len
                    else:
                        break

                current_chunk = overlap_sentences
                current_length = overlap_length

            current_chunk.append(sentence)
            current_length += token_count

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "chunk_index": chunk_index,
                "content": chunk_text,
                "token_count": self.count_tokens(chunk_text),
            })

        return chunks

    def _chunk_by_paragraph(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        *args,
        **kwargs
    ) -> List[Dict[str, Any]]:
        chunks = []
        paragraphs = re.split(r'\n\s*\n', text.strip())
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            token_count = self.count_tokens(para)

            if token_count <= chunk_size:
                chunks.append({
                    "chunk_index": chunk_index,
                    "content": para,
                    "token_count": token_count,
                })
                chunk_index += 1
            else:
                sub_chunks = self._chunk_by_token(
                    para, chunk_size, chunk_overlap
                )
                for sub_chunk in sub_chunks:
                    sub_chunk["chunk_index"] = chunk_index
                    chunks.append(sub_chunk)
                    chunk_index += 1

        return chunks

    def _chunk_by_semantic(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        threshold: float = 0.5,
        *args,
        **kwargs
    ) -> List[Dict[str, Any]]:
        if not self.embedding_service:
            logger.warning("Embedding service not available, falling back to token chunking")
            return self._chunk_by_token(text, chunk_size, chunk_overlap)

        sentences = self._split_sentences(text)
        if len(sentences) < 2:
            return [{
                "chunk_index": 0,
                "content": text,
                "token_count": self.count_tokens(text),
            }]

        try:
            embeddings = []
            for sentence in sentences:
                emb = self.embedding_service.encode_text(sentence)
                embeddings.append(emb)

            chunks = []
            current_chunk = [sentences[0]]
            current_embedding = embeddings[0]
            chunk_index = 0
            current_length = self.count_tokens(sentences[0])

            for i in range(1, len(sentences)):
                similarity = self._cosine_similarity(current_embedding, embeddings[i])

                if similarity < threshold or current_length + self.count_tokens(sentences[i]) > chunk_size:
                    chunk_text = " ".join(current_chunk)
                    chunks.append({
                        "chunk_index": chunk_index,
                        "content": chunk_text,
                        "token_count": self.count_tokens(chunk_text),
                    })
                    chunk_index += 1

                    if chunk_overlap > 0 and len(current_chunk) > 1:
                        overlap_count = min(len(current_chunk) - 1, chunk_overlap // 20)
                        current_chunk = current_chunk[-overlap_count:]
                        current_length = sum(self.count_tokens(s) for s in current_chunk)
                    else:
                        current_chunk = []
                        current_length = 0

                current_chunk.append(sentences[i])
                current_length += self.count_tokens(sentences[i])

                if len(current_chunk) > 1:
                    chunk_embs = [embeddings[j] for j in range(i - len(current_chunk) + 1, i + 1)]
                    current_embedding = np.mean(chunk_embs, axis=0)
                else:
                    current_embedding = embeddings[i]

            if current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "chunk_index": chunk_index,
                    "content": chunk_text,
                    "token_count": self.count_tokens(chunk_text),
                })

            return chunks

        except Exception as e:
            logger.error(f"Semantic chunking failed: {e}, falling back to token chunking")
            return self._chunk_by_token(text, chunk_size, chunk_overlap)

    def _split_sentences(self, text: str) -> List[str]:
        sentence_endings = r'(?<=[。！？.!?])\s*'
        sentences = re.split(sentence_endings, text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def _compute_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not chunks:
            return {
                "total_chunks": 0,
                "avg_chunk_length": 0,
                "max_chunk_length": 0,
                "min_chunk_length": 0,
            }

        lengths = [chunk["token_count"] for chunk in chunks]
        return {
            "total_chunks": len(chunks),
            "avg_chunk_length": float(sum(lengths)) / len(lengths),
            "max_chunk_length": max(lengths),
            "min_chunk_length": min(lengths),
        }

    def extract_keywords(self, text: str, top_k: int = 20) -> List[str]:
        words = jieba.cut_for_search(text)
        stopwords = self._get_stopwords()
        keywords = [w for w in words if w.strip() and w not in stopwords and len(w) > 1]

        freq = {}
        for word in keywords:
            freq[word] = freq.get(word, 0) + 1

        sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [k for k, v in sorted_keywords[:top_k]]

    def _get_stopwords(self) -> set:
        return {
            '的', '了', '和', '是', '就', '都', '而', '及', '与', '等',
            '也', '在', '这', '那', '有', '不', '人', '我', '你', '他',
            '她', '它', '们', '个', '上', '下', '中', '为', '以', '于',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'and', 'or', 'but', 'if', 'then', 'else', 'when', 'at',
            'by', 'for', 'with', 'about', 'against', 'between', 'into',
        }
