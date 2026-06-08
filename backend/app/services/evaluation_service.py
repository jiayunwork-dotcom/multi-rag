import re
import jieba
from typing import List, Dict, Any, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self, embedding_service=None):
        self.embedding_service = embedding_service

    def evaluate(
        self,
        question: str,
        answer: str,
        context_chunks: List[Dict[str, Any]],
        retrieval_scores: List[float]
    ) -> Dict[str, Any]:
        try:
            faithfulness, faith_reason = self._calculate_faithfulness(answer, context_chunks)
            answer_relevancy, relevancy_reason = self._calculate_answer_relevancy(question, answer)
            context_precision, precision_reason = self._calculate_context_precision(
                answer, context_chunks, retrieval_scores
            )

            return {
                "faithfulness": faithfulness,
                "answer_relevancy": answer_relevancy,
                "context_precision": context_precision,
                "faithfulness_reason": faith_reason,
                "answer_relevancy_reason": relevancy_reason,
                "context_precision_reason": precision_reason,
            }
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "faithfulness_reason": f"评估失败: {str(e)}",
                "answer_relevancy_reason": f"评估失败: {str(e)}",
                "context_precision_reason": f"评估失败: {str(e)}",
            }

    def _calculate_faithfulness(
        self,
        answer: str,
        context_chunks: List[Dict[str, Any]]
    ) -> Tuple[float, str]:
        if not answer.strip():
            return 0.0, "答案为空"

        if not context_chunks:
            return 0.0, "没有检索到上下文"

        answer_sentences = self._split_sentences(answer)
        if not answer_sentences:
            return 0.0, "答案无法拆分为句子"

        context_text = " ".join([chunk.get("content", "") for chunk in context_chunks])
        context_text = context_text.lower()

        supported_sentences = 0
        reasons = []

        for i, sentence in enumerate(answer_sentences):
            sentence_lower = sentence.lower().strip()
            if len(sentence_lower) < 5:
                continue

            is_supported = self._check_sentence_support(sentence_lower, context_text)

            if is_supported:
                supported_sentences += 1
                reasons.append(f"句子{i+1}: 找到依据")
            else:
                reasons.append(f"句子{i+1}: 未找到依据 - '{sentence[:50]}...'")

        faithfulness = supported_sentences / len([s for s in answer_sentences if len(s.strip()) >= 5]) if answer_sentences else 0.0
        faithfulness = round(faithfulness * 100, 1)

        reason_summary = f"共{len(answer_sentences)}个句子，{supported_sentences}个找到依据。\n" + "\n".join(reasons[:5])
        if len(reasons) > 5:
            reason_summary += f"\n...共{len(reasons)}条"

        return faithfulness, reason_summary

    def _check_sentence_support(self, sentence: str, context: str) -> bool:
        sentence_keywords = self._extract_keywords(sentence)

        if not sentence_keywords:
            return True

        matched_keywords = 0
        for keyword in sentence_keywords:
            if keyword in context:
                matched_keywords += 1

        if matched_keywords / len(sentence_keywords) >= 0.6:
            return True

        if self.embedding_service:
            try:
                sentence_emb = self.embedding_service.encode_text(sentence)
                context_emb = self.embedding_service.encode_text(context)
                similarity = self._cosine_similarity(sentence_emb, context_emb)
                return similarity > 0.7
            except Exception as e:
                logger.warning(f"Embedding-based faithfulness check failed: {e}")

        return matched_keywords / len(sentence_keywords) >= 0.8

    def _calculate_answer_relevancy(
        self,
        question: str,
        answer: str
    ) -> Tuple[float, str]:
        if not question.strip() or not answer.strip():
            return 0.0, "问题或答案为空"

        if self.embedding_service:
            try:
                question_emb = self.embedding_service.encode_text(question)
                answer_emb = self.embedding_service.encode_text(answer)
                similarity = self._cosine_similarity(question_emb, answer_emb)
                relevancy = round(float(similarity), 3)

                reason = f"问题与答案的语义相似度为{relevancy}"
                if relevancy >= 0.8:
                    reason += "，高度相关"
                elif relevancy >= 0.5:
                    reason += "，中度相关"
                else:
                    reason += "，相关性较低"

                return relevancy, reason
            except Exception as e:
                logger.warning(f"Embedding-based relevancy check failed: {e}")

        question_keywords = self._extract_keywords(question)
        answer_keywords = self._extract_keywords(answer)

        if not question_keywords:
            return 0.5, "问题关键词提取失败，使用默认值"

        overlap = len(set(question_keywords) & set(answer_keywords))
        relevancy = round(overlap / len(question_keywords), 3)

        reason = f"问题关键词{len(question_keywords)}个，答案覆盖{overlap}个，覆盖率{relevancy}"
        return relevancy, reason

    def _calculate_context_precision(
        self,
        answer: str,
        context_chunks: List[Dict[str, Any]],
        retrieval_scores: List[float]
    ) -> Tuple[float, str]:
        if not context_chunks or not answer.strip():
            return 0.0, "没有上下文或答案为空"

        answer_keywords = self._extract_keywords(answer)
        if not answer_keywords:
            return 0.5, "答案关键词提取失败，使用默认值"

        relevant_positions = []
        chunk_relevance = []

        for i, chunk in enumerate(context_chunks):
            chunk_content = chunk.get("content", "").lower()
            chunk_keywords = self._extract_keywords(chunk_content)

            if not chunk_keywords:
                chunk_relevance.append(False)
                continue

            overlap = len(set(answer_keywords) & set(chunk_keywords))
            is_relevant = overlap / len(answer_keywords) >= 0.3

            if self.embedding_service and is_relevant:
                try:
                    answer_emb = self.embedding_service.encode_text(answer)
                    chunk_emb = self.embedding_service.encode_text(chunk_content)
                    similarity = self._cosine_similarity(answer_emb, chunk_emb)
                    is_relevant = similarity > 0.5
                except Exception as e:
                    logger.warning(f"Embedding-based precision check failed: {e}")

            chunk_relevance.append(is_relevant)
            if is_relevant:
                relevant_positions.append(i + 1)

        if not any(chunk_relevance):
            return 0.0, "没有找到与答案相关的上下文块"

        precision_at_k = []
        cumulative_relevant = 0
        for i, is_rel in enumerate(chunk_relevance, 1):
            if is_rel:
                cumulative_relevant += 1
                precision_at_k.append(cumulative_relevant / i)

        context_precision = round(sum(precision_at_k) / len(precision_at_k), 3) if precision_at_k else 0.0

        reason = f"相关上下文块位置: {relevant_positions}\n"
        reason += f"平均精确率(AP): {context_precision}\n"
        for i, (is_rel, score) in enumerate(zip(chunk_relevance, retrieval_scores), 1):
            status = "✓ 相关" if is_rel else "✗ 不相关"
            reason += f"  排名{i}: {status} (检索分数: {score:.4f})\n"

        return context_precision, reason

    def _split_sentences(self, text: str) -> List[str]:
        sentence_endings = r'(?<=[。！？.!?])\s*'
        sentences = re.split(sentence_endings, text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _extract_keywords(self, text: str, top_k: int = 20) -> List[str]:
        stopwords = self._get_stopwords()
        words = jieba.cut_for_search(text.lower())
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
            '什么', '怎么', '为什么', '如何', '哪些', '哪个', '多少',
            '哪里', '什么时候', '谁', '吗', '呢', '啊', '吧', '哦',
        }

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1 * norm2))
