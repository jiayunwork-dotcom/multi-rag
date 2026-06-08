from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self, db_session, llm_service=None):
        self.db = db_session
        self.llm_service = llm_service
        self.max_history_rounds = 5

    def get_conversation_history(
        self,
        conversation_id: int,
        max_rounds: Optional[int] = None
    ) -> List[Dict[str, str]]:
        from .. import models

        max_rounds = max_rounds or self.max_history_rounds

        conversation = self.db.query(models.Conversation).filter(
            models.Conversation.id == conversation_id
        ).first()

        if not conversation:
            return []

        messages = self.db.query(models.Message).filter(
            models.Message.conversation_id == conversation_id
        ).order_by(models.Message.created_at.desc()).limit(max_rounds * 2).all()

        messages = list(reversed(messages))

        if len(messages) >= max_rounds * 2:
            if conversation.history_summary:
                return self._build_history_with_summary(
                    messages,
                    conversation.history_summary,
                    max_rounds
                )
            else:
                recent_messages = messages[-(max_rounds * 2):]
                history = []
                for msg in recent_messages:
                    history.append({
                        "role": msg.role,
                        "content": msg.content
                    })
                return history

        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })

        return history

    def _build_history_with_summary(
        self,
        messages: List,
        summary: str,
        max_rounds: int
    ) -> List[Dict[str, str]]:
        recent_messages = messages[-(max_rounds * 2):]

        history = [
            {"role": "system", "content": f"历史对话摘要: {summary}"}
        ]

        for msg in recent_messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })

        return history

    async def update_history_summary(
        self,
        conversation_id: int,
        force_update: bool = False
    ) -> Optional[str]:
        from .. import models

        conversation = self.db.query(models.Conversation).filter(
            models.Conversation.id == conversation_id
        ).first()

        if not conversation:
            return None

        messages = self.db.query(models.Message).filter(
            models.Message.conversation_id == conversation_id
        ).order_by(models.Message.created_at).all()

        if len(messages) <= self.max_history_rounds * 2 and not force_update:
            return conversation.history_summary

        if len(messages) > self.max_history_rounds * 2 or force_update:
            if not self.llm_service:
                logger.warning("LLM service not available for summarization")
                return None

            older_messages = messages[:-self.max_history_rounds * 2]
            history_text = self._format_messages_for_summary(older_messages)

            summary = await self._generate_summary(history_text, conversation.history_summary)

            conversation.history_summary = summary
            self.db.commit()

            return summary

        return conversation.history_summary

    def _format_messages_for_summary(self, messages: List) -> str:
        parts = []
        for msg in messages:
            if msg.role == "user":
                parts.append(f"用户: {msg.content}")
            elif msg.role == "assistant":
                parts.append(f"助手: {msg.content}")
        return "\n".join(parts)

    async def _generate_summary(self, history_text: str, existing_summary: Optional[str]) -> str:
        if not self.llm_service:
            return ""

        prompt = f"""请为以下对话历史生成一个简洁的摘要（不超过200字），
保留关键信息点和上下文脉络。
{'现有摘要（请基于此更新）：' + existing_summary if existing_summary else ''}

对话历史：
{history_text}

摘要："""

        messages = [
            {"role": "system", "content": "你是一个专业的对话摘要助手，能够简洁准确地总结对话内容。"},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm_service.generate(messages)
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return existing_summary or ""

    def generate_conversation_title(
        self,
        first_question: str,
        max_length: int = 30
    ) -> str:
        title = first_question.strip()
        if len(title) > max_length:
            title = title[:max_length] + "..."
        return title

    def get_statistics(self) -> Dict[str, Any]:
        from .. import models
        from sqlalchemy import func

        total_conversations = self.db.query(func.count(models.Conversation.id)).scalar()
        total_messages = self.db.query(func.count(models.Message.id)).scalar()
        total_qa_pairs = self.db.query(func.count(models.Message.id)).filter(
            models.Message.role == "assistant"
        ).scalar()

        avg_response_time = self.db.query(func.avg(models.Message.response_time)).filter(
            models.Message.role == "assistant",
            models.Message.response_time.isnot(None)
        ).scalar() or 0

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_qa_pairs": total_qa_pairs,
            "avg_response_time": float(avg_response_time),
        }
