from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, List
import logging

from ..database import get_db
from .. import models, schemas
from ..config import settings
from ..services.pipeline_service import service_manager
from ..services.conversation_service import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["管理后台"])


@router.get("/config", response_model=schemas.SystemConfig)
def get_system_config():
    return schemas.SystemConfig(
        llm_endpoint=settings.LLM_ENDPOINT,
        llm_api_key=settings.LLM_API_KEY,
        llm_model=settings.LLM_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        cross_encoder_model=settings.CROSS_ENCODER_MODEL,
        default_chunk_strategy=settings.DEFAULT_CHUNK_STRATEGY,
        default_chunk_size=settings.DEFAULT_CHUNK_SIZE,
        default_chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
        retrieval_top_k=settings.RETRIEVAL_TOP_K,
        rerank_top_n=settings.RERANK_TOP_N,
        prompt_template=settings.PROMPT_TEMPLATE,
    )


@router.put("/config", response_model=schemas.SystemConfig)
def update_system_config(config: schemas.SystemConfigUpdate):
    updates = config.model_dump(exclude_unset=True)

    if "llm_endpoint" in updates:
        settings.LLM_ENDPOINT = updates["llm_endpoint"]
    if "llm_api_key" in updates:
        settings.LLM_API_KEY = updates["llm_api_key"]
    if "llm_model" in updates:
        settings.LLM_MODEL = updates["llm_model"]
    if "embedding_model" in updates:
        settings.EMBEDDING_MODEL = updates["embedding_model"]
    if "cross_encoder_model" in updates:
        settings.CROSS_ENCODER_MODEL = updates["cross_encoder_model"]
    if "default_chunk_strategy" in updates:
        settings.DEFAULT_CHUNK_STRATEGY = updates["default_chunk_strategy"]
    if "default_chunk_size" in updates:
        settings.DEFAULT_CHUNK_SIZE = updates["default_chunk_size"]
    if "default_chunk_overlap" in updates:
        settings.DEFAULT_CHUNK_OVERLAP = updates["default_chunk_overlap"]
    if "retrieval_top_k" in updates:
        settings.RETRIEVAL_TOP_K = updates["retrieval_top_k"]
    if "rerank_top_n" in updates:
        settings.RERANK_TOP_N = updates["rerank_top_n"]
    if "prompt_template" in updates:
        settings.PROMPT_TEMPLATE = updates["prompt_template"]

    if "llm_endpoint" in updates or "llm_api_key" in updates or "llm_model" in updates:
        from ..services.llm_service import LLMService
        service_manager.llm_service = LLMService(
            endpoint=settings.LLM_ENDPOINT,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            default_prompt_template=settings.PROMPT_TEMPLATE,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

    return schemas.SystemConfig(
        llm_endpoint=settings.LLM_ENDPOINT,
        llm_api_key=settings.LLM_API_KEY,
        llm_model=settings.LLM_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        cross_encoder_model=settings.CROSS_ENCODER_MODEL,
        default_chunk_strategy=settings.DEFAULT_CHUNK_STRATEGY,
        default_chunk_size=settings.DEFAULT_CHUNK_SIZE,
        default_chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
        retrieval_top_k=settings.RETRIEVAL_TOP_K,
        rerank_top_n=settings.RERANK_TOP_N,
        prompt_template=settings.PROMPT_TEMPLATE,
    )


@router.get("/stats", response_model=schemas.UsageStats)
def get_usage_stats(db: Session = Depends(get_db)):
    total_documents = db.query(func.count(models.Document.id)).scalar()
    total_kb = db.query(func.count(models.KnowledgeBase.id)).scalar()
    total_chunks = db.query(func.count(models.Chunk.id)).scalar()

    conv_service = ConversationService(db)
    conv_stats = conv_service.get_statistics()

    total_qa = conv_stats["total_qa_pairs"]
    avg_response_time = conv_stats["avg_response_time"]

    messages_with_evaluation = db.query(models.Message).filter(
        models.Message.role == "assistant",
        models.Message.evaluation.isnot(None)
    ).all()

    retrieval_hit_rate = 0.0
    if messages_with_evaluation:
        hit_count = 0
        for msg in messages_with_evaluation:
            if msg.evaluation and isinstance(msg.evaluation, dict):
                cp = msg.evaluation.get("context_precision", 0)
                if cp > 0:
                    hit_count += 1
        retrieval_hit_rate = hit_count / len(messages_with_evaluation)

    return schemas.UsageStats(
        total_qa_count=total_qa,
        avg_response_time=avg_response_time,
        retrieval_hit_rate=retrieval_hit_rate,
        total_documents=total_documents,
        total_knowledge_bases=total_kb,
        total_chunks=total_chunks,
    )


@router.get("/documents", response_model=List[schemas.Document])
def list_all_documents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    documents = db.query(models.Document).order_by(
        models.Document.created_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for doc in documents:
        result.append(schemas.Document(
            id=doc.id,
            title=doc.title,
            knowledge_base_id=doc.knowledge_base_id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            page_count=doc.page_count,
            parse_status=doc.parse_status,
            parse_error=doc.parse_error,
            chunk_strategy=doc.chunk_strategy,
            chunk_size=doc.chunk_size,
            total_chunks=doc.total_chunks,
            avg_chunk_length=doc.avg_chunk_length,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ))

    return result


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_admin(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    service_manager.pipeline.delete_document_data(db, doc_id)

    import os
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file {doc.file_path}: {e}")

    db.delete(doc)
    db.commit()
    return None


@router.post("/documents/{doc_id}/reparse", response_model=schemas.ParseTask)
async def reparse_document_admin(
    doc_id: int,
    db: Session = Depends(get_db)
):
    from .documents import process_document_background
    from fastapi import BackgroundTasks

    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    service_manager.pipeline.delete_document_data(db, doc_id)

    for chunk in doc.chunks:
        db.delete(chunk)

    doc.parse_status = models.ParseStatus.PENDING
    doc.parse_error = None
    doc.total_chunks = 0
    db.commit()

    bg_tasks = BackgroundTasks()
    bg_tasks.add_task(process_document_background, doc_id, None)

    status = service_manager.pipeline.get_task_status(db, doc_id)
    if status:
        return schemas.ParseTask(**status)

    parse_task = models.ParseTask(
        document_id=doc_id,
        status=models.ParseStatus.PENDING,
        stage="排队中",
        progress=0.0,
    )
    db.add(parse_task)
    db.commit()
    db.refresh(parse_task)

    return schemas.ParseTask(
        id=parse_task.id,
        document_id=parse_task.document_id,
        status=parse_task.status,
        stage=parse_task.stage,
        progress=parse_task.progress,
        processed_chunks=parse_task.processed_chunks,
        total_chunks=parse_task.total_chunks,
        estimated_remaining=parse_task.estimated_remaining,
        error_message=parse_task.error_message,
        started_at=parse_task.started_at,
        completed_at=parse_task.completed_at,
    )


@router.get("/conversations", response_model=List[schemas.Conversation])
def list_all_conversations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    from sqlalchemy import func

    conversations = db.query(models.Conversation).order_by(
        models.Conversation.updated_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for conv in conversations:
        msg_count = db.query(func.count(models.Message.id)).filter(
            models.Message.conversation_id == conv.id
        ).scalar()

        result.append(schemas.Conversation(
            id=conv.id,
            knowledge_base_id=conv.knowledge_base_id,
            title=conv.title,
            message_count=msg_count,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        ))

    return result


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_admin(conv_id: int, db: Session = Depends(get_db)):
    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    db.delete(conv)
    db.commit()
    return None
