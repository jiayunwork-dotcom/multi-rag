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

    def build_compare_context(
        self,
        kb_results: Dict[int, Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        context_parts = []
        citations = []
        cite_index = 1

        for kb_id, kb_data in kb_results.items():
            kb_name = kb_data.get("knowledge_base_name", f"知识库{kb_id}")
            retrieval_results = kb_data.get("retrieval_results", [])

            context_parts.append(f"\n=== 知识库: {kb_name} (ID: {kb_id}) ===")

            for result in retrieval_results:
                doc_title = result.get("document_title", "Unknown Document")
                page_num = result.get("page_number")
                content = result.get("content", "")

                citation_mark = f"[{cite_index}]"
                kb_tag = f"[{kb_name}]"

                if page_num:
                    context_part = f"{citation_mark}{kb_tag} 来源: {doc_title} (第{page_num}页)\n{content}\n"
                else:
                    context_part = f"{citation_mark}{kb_tag} 来源: {doc_title}\n{content}\n"

                context_parts.append(context_part)

                citations.append({
                    "index": cite_index,
                    "kb_id": kb_id,
                    "kb_name": kb_name,
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
                cite_index += 1

        context = "\n".join(context_parts)
        return context, citations

    def build_compare_prompt(
        self,
        question: str,
        context: str,
        kb_names: List[str],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        kb_list_str = ", ".join(kb_names)

        system_prompt = f"""你是一个专业的多知识库对比分析助手。用户会提出问题，你需要基于{len(kb_names)}个知识库的内容进行对比分析。

请严格遵循以下规则：
1. 只使用参考资料中明确提到的信息，不要编造或推测
2. 如果某个知识库中没有相关信息，请明确说明"[知识库名]中未提及相关内容"
3. 回答需要清晰区分各知识库的观点，建议使用表格形式展示对比
4. 每个观点必须标注来源：使用[编号][知识库名]格式，例如[1][知识库A]
5. 对比分析应包含：各知识库的共同点、差异点、各自的侧重点
6. 最后给出综合总结

参考资料格式说明：
- 每个段落开头有[编号][知识库名]标记，表示该内容来自哪个知识库
- 编号是全局唯一的，用于精确引用

{kb_list_str}"""

        messages = []
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        messages.insert(0, {"role": "system", "content": system_prompt})

        user_content = f"""参考资料：
{context}

用户问题：{question}

请基于以上{len(kb_names)}个知识库的内容，进行对比分析回答。
要求：
1. 首先用表格形式对比各知识库的核心观点
2. 然后详细分析各知识库的异同点
3. 每个观点都要标注来源，格式为[编号][知识库名]
4. 最后给出综合总结"""

        messages.append({"role": "user", "content": user_content})
        return messages

    def parse_compare_analysis(
        self,
        answer: str,
        citations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        pattern = r'\[(\d+)\]\[([^\]]+)\]'
        matches = re.findall(pattern, answer)

        viewpoints = []
        seen_indices = set()

        for num_str, kb_name in matches:
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(citations) and idx not in seen_indices:
                    cite = citations[idx]
                    viewpoints.append({
                        "viewpoint": answer[max(0, answer.find(f"[{num_str}][{kb_name}]") - 50):answer.find(f"[{num_str}][{kb_name}]") + 50].strip(),
                        "knowledge_base_id": cite.get("kb_id"),
                        "knowledge_base_name": cite.get("kb_name"),
                        "document_id": cite.get("document_id"),
                        "document_title": cite.get("document_title"),
                        "chunk_id": cite.get("chunk_id"),
                        "page_number": cite.get("page_number"),
                    })
                    seen_indices.add(idx)
            except (ValueError, IndexError):
                continue

        return {
            "viewpoints": viewpoints,
            "summary": "对比分析完成"
        }

    def build_graph_rag_context(
        self,
        retrieval_context: str,
        graph_context: str
    ) -> str:
        combined_parts = []

        if retrieval_context:
            combined_parts.append("## 文档检索信息")
            combined_parts.append(retrieval_context)

        if graph_context:
            combined_parts.append("\n" + graph_context)

        return "\n".join(combined_parts)

    def build_graph_rag_prompt(
        self,
        question: str,
        context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        use_graph: bool = False
    ) -> List[Dict[str, str]]:
        messages = []

        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        if use_graph:
            system_prompt = """你是一个专业的知识图谱增强问答助手，能够基于文档检索和知识图谱两种信息源回答用户问题。

请严格遵循以下规则：
1. 区分信息来源：来自知识图谱推理的信息用 🟦 标记，来自文档原文检索的信息用 🟨 标记
2. 只使用提供的信息，不要编造或推测
3. 如果信息不足，明确说明"根据现有资料无法回答该问题"
4. 每个答案段落结束时，使用[1][2]等格式标注引用来源
5. 对于图谱推理的结论，要清晰说明推理路径（如"根据[实体A]--[关系]-->[实体B]的关联..."）
6. 优先使用文档原文信息，图谱信息作为补充和推理依据
7. 回答要清晰、有条理，重要信息可以适当强调

信息标记说明：
- 🟦 表示该信息来自知识图谱的关联推理
- 🟨 表示该信息直接来自文档原文检索
- 🟩 表示该信息结合了文档和图谱的综合分析"""
        else:
            system_prompt = """你是一个专业的问答助手，能够基于提供的参考资料准确回答用户问题。

请严格遵循以下规则：
1. 只使用参考资料中明确提到的信息，不要编造或推测
2. 如果参考资料中没有相关信息，请明确说明"根据现有资料无法回答该问题"
3. 每个答案段落结束时，请使用[1][2]等格式标注引用来源，对应的是参考资料的编号
4. 引用来源必须准确对应到具体的资料段落
5. 回答要清晰、有条理，重要信息可以适当强调"""

        messages.insert(0, {"role": "system", "content": system_prompt})

        template = """参考资料：
{context}

用户问题：{question}

请基于以上参考资料回答用户问题。
要求：
1. 确保引用来源标注准确
2. 回答要全面、准确、有条理"""

        user_content = template.format(context=context, question=question)
        messages.append({"role": "user", "content": user_content})

        return messages

    def format_answer_with_graph_markers(
        self,
        formatted: Dict[str, Any]
    ) -> Dict[str, Any]:
        answer = formatted["answer"]

        import re

        graph_patterns = [
            r'知识图谱', r'图谱', r'关联', r'推理', r'路径', r'社区',
            r'属于', r'位于', r'创建', r'使用', r'依赖', r'包含',
            r'-->', r'→', r'关系', r'实体'
        ]

        doc_patterns = [
            r'文档', r'原文', r'检索', r'引用', r'来源', r'第\d+页',
            r'\[\d+\]'
        ]

        sentences = re.split(r'(?<=[。！？])', answer)
        marked_sentences = []

        for sentence in sentences:
            if not sentence.strip():
                continue

            has_graph = any(re.search(p, sentence) for p in graph_patterns)
            has_doc = any(re.search(p, sentence) for p in doc_patterns)

            if has_graph and has_doc:
                marker = "🟩 "
            elif has_graph:
                marker = "🟦 "
            elif has_doc:
                marker = "🟨 "
            else:
                marker = ""

            if marker and not sentence.startswith(("🟦", "🟨", "🟩")):
                marked_sentences.append(marker + sentence)
            else:
                marked_sentences.append(sentence)

        marked_answer = "".join(marked_sentences)

        if not any(c in marked_answer for c in ["🟦", "🟨", "🟩"]):
            marked_answer = "🟨 " + marked_answer

        return {
            "answer": marked_answer,
            "citations": formatted["citations"],
        }
