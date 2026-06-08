import time
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime

from ..database import get_db
from .. import models, schemas
from ..services.pipeline_service import service_manager
from ..services.conversation_service import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["对话聊天"])


@router.get("/conversations", response_model=List[schemas.Conversation])
def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
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


@router.post("/conversations", response_model=schemas.Conversation, status_code=status.HTTP_201_CREATED)
def create_conversation(
    conv_data: schemas.ConversationCreate,
    db: Session = Depends(get_db)
):
    conv = models.Conversation(**conv_data.model_dump())
    db.add(conv)
    db.commit()
    db.refresh(conv)

    return schemas.Conversation(
        id=conv.id,
        knowledge_base_id=conv.knowledge_base_id,
        title=conv.title,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/conversations/{conv_id}", response_model=schemas.ConversationDetail)
def get_conversation(conv_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import func

    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    msg_count = db.query(func.count(models.Message.id)).filter(
        models.Message.conversation_id == conv_id
    ).scalar()

    messages = []
    for msg in conv.messages:
        messages.append(schemas.Message(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            citations=msg.citations,
            retrieval_debug=msg.retrieval_debug,
            evaluation=msg.evaluation,
            response_time=msg.response_time,
            created_at=msg.created_at,
        ))

    return schemas.ConversationDetail(
        id=conv.id,
        knowledge_base_id=conv.knowledge_base_id,
        title=conv.title,
        message_count=msg_count,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


@router.put("/conversations/{conv_id}", response_model=schemas.Conversation)
def update_conversation(
    conv_id: int,
    conv_data: schemas.ConversationUpdate,
    db: Session = Depends(get_db)
):
    from sqlalchemy import func

    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    update_data = conv_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(conv, key, value)

    db.commit()
    db.refresh(conv)

    msg_count = db.query(func.count(models.Message.id)).filter(
        models.Message.conversation_id == conv_id
    ).scalar()

    return schemas.Conversation(
        id=conv.id,
        knowledge_base_id=conv.knowledge_base_id,
        title=conv.title,
        message_count=msg_count,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conv_id: int, db: Session = Depends(get_db)):
    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    db.delete(conv)
    db.commit()
    return None


@router.delete("/conversations/{conv_id}/messages/{msg_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(conv_id: int, msg_id: int, db: Session = Depends(get_db)):
    msg = db.query(models.Message).filter(
        models.Message.id == msg_id,
        models.Message.conversation_id == conv_id
    ).first()
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")

    db.delete(msg)
    db.commit()
    return None


@router.get("/history")
def get_chat_history(
    conversation_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    if conversation_id:
        conv = db.query(models.Conversation).filter(
            models.Conversation.id == conversation_id
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")

        messages = db.query(models.Message).filter(
            models.Message.conversation_id == conversation_id
        ).order_by(models.Message.created_at).all()
    else:
        messages = db.query(models.Message).order_by(
            models.Message.created_at.desc()
        ).limit(100).all()
        messages = list(reversed(messages))

    return [
        {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "content": msg.content,
            "citations": msg.citations,
            "evaluation": msg.evaluation,
            "created_at": msg.created_at,
        }
        for msg in messages
    ]


@router.post("")
async def chat(
    request: schemas.ChatRequest,
    db: Session = Depends(get_db)
):
    start_time = time.time()

    knowledge_base_id = request.knowledge_base_id

    if request.conversation_id:
        conv = db.query(models.Conversation).filter(
            models.Conversation.id == request.conversation_id
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        if not knowledge_base_id:
            knowledge_base_id = conv.knowledge_base_id
    else:
        conv = models.Conversation(
            knowledge_base_id=knowledge_base_id,
        )
        db.add(conv)
        db.flush()
        db.refresh(conv)

    if not knowledge_base_id:
        raise HTTPException(status_code=400, detail="需要指定知识库ID")

    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == knowledge_base_id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    user_message = models.Message(
        conversation_id=conv.id,
        role="user",
        content=request.question,
    )
    db.add(user_message)
    db.flush()

    if not conv.title:
        conv_service = ConversationService(db)
        conv.title = conv_service.generate_conversation_title(request.question)
        db.flush()

    conv_service = ConversationService(db, service_manager.llm_service)
    conversation_history = conv_service.get_conversation_history(conv.id)

    retrieval_results, retrieval_debug = service_manager.retrieval_service.hybrid_search(
        knowledge_base_id=knowledge_base_id,
        query=request.question,
        top_k=request.top_k,
        rerank_n=request.rerank_n,
    )

    for result in retrieval_results:
        doc = db.query(models.Document).filter(
            models.Document.id == result.get("document_id")
        ).first()
        if doc:
            result["document_title"] = doc.title

    context, citations = service_manager.llm_service.build_context(retrieval_results)

    messages = service_manager.llm_service.build_prompt(
        question=request.question,
        context=context,
        conversation_history=conversation_history,
    )

    if request.stream:
        return StreamingResponse(
            stream_chat_response(
                messages=messages,
                question=request.question,
                context_chunks=retrieval_results,
                citations=citations,
                retrieval_debug=retrieval_debug,
                conversation_id=conv.id,
                db=db,
                start_time=start_time,
            ),
            media_type="text/event-stream",
        )
    else:
        response = service_manager.llm_service.generate(messages)
        answer = response.choices[0].message.content

        formatted = service_manager.llm_service.format_answer_with_citations(answer, citations)

        retrieval_scores = [r.get("rerank_score") or r.get("rrf_score") or 0 for r in retrieval_results]
        evaluation = service_manager.evaluation_service.evaluate(
            question=request.question,
            answer=formatted["answer"],
            context_chunks=retrieval_results,
            retrieval_scores=retrieval_scores,
        )

        response_time = time.time() - start_time

        assistant_message = models.Message(
            conversation_id=conv.id,
            role="assistant",
            content=formatted["answer"],
            citations=formatted["citations"],
            retrieval_debug=retrieval_debug,
            evaluation=evaluation,
            response_time=response_time,
        )
        db.add(assistant_message)
        db.commit()

        await conv_service.update_history_summary(conv.id)

        formatted_results = []
        for r in retrieval_results:
            formatted_results.append(schemas.RetrievalResult(
                chunk_id=r.get("chunk_id", 0),
                document_id=r.get("document_id", 0),
                document_title=r.get("document_title", "Unknown"),
                chunk_index=r.get("chunk_index", 0),
                content=r.get("content", ""),
                page_number=r.get("page_number"),
                semantic_score=r.get("semantic_score"),
                bm25_score=r.get("bm25_score"),
                rrf_score=r.get("rrf_score"),
                rerank_score=r.get("rerank_score"),
            ))

        return schemas.ChatResponse(
            answer=formatted["answer"],
            conversation_id=conv.id,
            citations=formatted["citations"],
            retrieval_results=formatted_results,
            retrieval_debug=retrieval_debug,
            evaluation=evaluation,
        )


async def stream_chat_response(
    messages,
    question: str,
    context_chunks,
    citations,
    retrieval_debug,
    conversation_id: int,
    db: Session,
    start_time: float,
):
    full_answer = ""

    yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"

    async for chunk in service_manager.llm_service.generate_stream(messages):
        full_answer += chunk
        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

    formatted = service_manager.llm_service.format_answer_with_citations(full_answer, citations)

    retrieval_scores = [r.get("rerank_score") or r.get("rrf_score") or 0 for r in context_chunks]
    evaluation = service_manager.evaluation_service.evaluate(
        question=question,
        answer=formatted["answer"],
        context_chunks=context_chunks,
        retrieval_scores=retrieval_scores,
    )

    response_time = time.time() - start_time

    assistant_message = models.Message(
        conversation_id=conversation_id,
        role="assistant",
        content=formatted["answer"],
        citations=formatted["citations"],
        retrieval_debug=retrieval_debug,
        evaluation=evaluation,
        response_time=response_time,
    )
    db.add(assistant_message)
    db.commit()

    conv_service = ConversationService(db, service_manager.llm_service)
    await conv_service.update_history_summary(conversation_id)

    yield f"data: {json.dumps({'type': 'citations', 'citations': formatted['citations']})}\n\n"
    yield f"data: {json.dumps({'type': 'evaluation', 'evaluation': evaluation})}\n\n"
    yield f"data: {json.dumps({'type': 'debug', 'retrieval_debug': retrieval_debug})}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'response_time': response_time})}\n\n"
