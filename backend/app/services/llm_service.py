import re
import json
from typing import List, Dict, Any, Optional, Tuple, AsyncIterator
from openai import OpenAI, AsyncOpenAI
import logging

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        default_prompt_template: str,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.default_prompt_template = default_prompt_template
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._init_client()

    def _init_client(self):
        try:
            self.client = OpenAI(
                base_url=self.endpoint,
                api_key=self.api_key,
            )
            self.async_client = AsyncOpenAI(
                base_url=self.endpoint,
                api_key=self.api_key,
            )
            logger.info(f"LLM client initialized with endpoint: {self.endpoint}, model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise

    def build_context(
        self,
        retrieval_results: List[Dict[str, Any]],
        max_context_tokens: int = 4000
    ) -> Tuple[str, List[Dict[str, Any]]]:
        if not retrieval_results:
            return "", []

        context_parts = []
        citations = []

        for i, result in enumerate(retrieval_results, 1):
            doc_title = result.get("document_title", "Unknown Document")
            page_num = result.get("page_number")
            content = result.get("content", "")

            citation_mark = f"[{i}]"
            if page_num:
                context_part = f"{citation_mark} 来源: {doc_title} (第{page_num}页)\n{content}\n"
            else:
                context_part = f"{citation_mark} 来源: {doc_title}\n{content}\n"

            context_parts.append(context_part)

            citations.append({
                "index": i,
                "chunk_id": result.get("chunk_id"),
                "document_id": result.get("document_id"),
                "document_title": doc_title,
                "chunk_index": result.get("chunk_index"),
                "page_number": page_num,
                "content": content,
                "semantic_score": result.get("semantic_score"),
                "bm25_score": result.get("bm25_score"),
                "rrf_score": result.get("rrf_score"),
                "rerank_score": result.get("rerank_score"),
            })

        context = "\n".join(context_parts)
        return context, citations

    def build_prompt(
        self,
        question: str,
        context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        custom_template: Optional[str] = None
    ) -> List[Dict[str, str]]:
        template = custom_template or self.default_prompt_template

        messages = []

        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        system_prompt = """你是一个专业的问答助手，能够基于提供的参考资料准确回答用户问题。
请严格遵循以下规则：
1. 只使用参考资料中明确提到的信息，不要编造或推测
2. 如果参考资料中没有相关信息，请明确说明"根据现有资料无法回答该问题"
3. 每个答案段落结束时，请使用[1][2]等格式标注引用来源，对应的是参考资料的编号
4. 引用来源必须准确对应到具体的资料段落
5. 回答要清晰、有条理，重要信息可以适当强调
"""
        messages.insert(0, {"role": "system", "content": system_prompt})

        user_content = template.format(context=context, question=question)
        messages.append({"role": "user", "content": user_content})

        return messages

    def generate(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False
    ):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=stream
            )
            return response
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    async def generate_stream(
        self,
        messages: List[Dict[str, str]]
    ) -> AsyncIterator[str]:
        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"LLM stream generation failed: {e}")
            raise

    def extract_citations_from_answer(
        self,
        answer: str,
        citations: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        pattern = r'\[(\d+)\]'
        citation_numbers = re.findall(pattern, answer)

        used_citations = []
        seen_indices = set()

        for num_str in citation_numbers:
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(citations) and idx not in seen_indices:
                    used_citations.append(citations[idx])
                    seen_indices.add(idx)
            except (ValueError, IndexError):
                continue

        return answer, used_citations

    def add_citation_markers(
        self,
        answer: str,
        citations: List[Dict[str, Any]]
    ) -> str:
        if not citations:
            return answer

        citation_map = {}
        for cite in citations:
            chunk_id = cite.get("chunk_id")
            if chunk_id:
                citation_map[chunk_id] = cite["index"]

        return answer

    def format_answer_with_citations(
        self,
        answer: str,
        citations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        answer_with_citations, used_citations = self.extract_citations_from_answer(answer, citations)

        return {
            "answer": answer_with_citations,
            "citations": used_citations,
        }
