import os
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import logging

from ..database import get_db
from .. import models, schemas
from ..config import settings
from ..services.pipeline_service import service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["文档管理"])

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.md', '.markdown', '.txt', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'}


@router.post("/upload", response_model=List[schemas.Document], status_code=status.HTTP_201_CREATED)
async def upload_documents(
    background_tasks: BackgroundTasks,
    knowledge_base_id: int = Query(..., description="知识库ID"),
    chunk_strategy: Optional[schemas.ChunkStrategy] = Query(None, description="分块策略"),
    chunk_size: Optional[int] = Query(None, ge=128, le=4096, description="分块大小"),
    chunk_overlap: Optional[int] = Query(None, ge=0, le=512, description="重叠大小"),
    semantic_threshold: Optional[float] = Query(None, ge=0.3, le=0.7, description="语义分割阈值"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    if len(files) > settings.MAX_BATCH_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"最多只能上传{settings.MAX_BATCH_UPLOAD}个文件"
        )

    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == knowledge_base_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    uploaded_docs = []
    chunking_config = None

    if chunk_strategy:
        chunking_config = {
            "strategy": chunk_strategy.value,
            "chunk_size": chunk_size or settings.DEFAULT_CHUNK_SIZE,
            "chunk_overlap": chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP,
            "semantic_threshold": semantic_threshold or settings.DEFAULT_SEMANTIC_THRESHOLD,
        }

    for file in files:
        try:
            ext = Path(file.filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的文件格式: {ext}。支持格式: {', '.join(ALLOWED_EXTENSIONS)}"
                )

            file_id = str(uuid.uuid4())
            safe_filename = f"{file_id}{ext}"
            file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

            content = await file.read()

            if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件过大，最大支持{settings.MAX_FILE_SIZE_MB}MB"
                )

            with open(file_path, "wb") as f:
                f.write(content)

            file_type = service_manager.document_parser.get_file_type(file.filename)

            title = Path(file.filename).stem
            document = models.Document(
                knowledge_base_id=knowledge_base_id,
                title=title,
                filename=file.filename,
                file_path=file_path,
                file_type=file_type,
                file_size=len(content),
                parse_status=models.ParseStatus.PENDING,
            )
            db.add(document)
            db.flush()
            db.refresh(document)

            background_tasks.add_task(
                process_document_background,
                document.id,
                chunking_config
            )

            uploaded_docs.append(document)
            logger.info(f"File uploaded: {file.filename} -> Document ID: {document.id}")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading file {file.filename}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}")

    db.commit()

    result = []
    for doc in uploaded_docs:
        db.refresh(doc)
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


async def process_document_background(document_id: int, chunking_config: Optional[dict]):
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        await service_manager.pipeline.process_document(db, document_id, chunking_config)
    finally:
        db.close()


@router.get("", response_model=List[schemas.Document])
def list_documents(
    knowledge_base_id: Optional[int] = Query(None, description="知识库ID"),
    parse_status: Optional[schemas.ParseStatus] = Query(None, description="解析状态"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(models.Document)

    if knowledge_base_id:
        query = query.filter(models.Document.knowledge_base_id == knowledge_base_id)

    if parse_status:
        query = query.filter(models.Document.parse_status == parse_status)

    documents = query.order_by(models.Document.created_at.desc()).offset(skip).limit(limit).all()

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


@router.get("/{doc_id}", response_model=schemas.DocumentDetail)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    chunks = []
    for chunk in doc.chunks:
        chunks.append(schemas.Chunk(
            id=chunk.id,
            content=chunk.content,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content_type=chunk.content_type,
            page_number=chunk.page_number,
            token_count=chunk.token_count,
            keywords=chunk.keywords,
            metadata=chunk.metadata,
            created_at=chunk.created_at,
            document_title=doc.title,
        ))

    return schemas.DocumentDetail(
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
        chunks=chunks,
    )


@router.get("/{doc_id}/parse-status", response_model=schemas.ParseTask)
def get_parse_status(doc_id: int, db: Session = Depends(get_db)):
    status = service_manager.pipeline.get_task_status(db, doc_id)
    if not status:
        raise HTTPException(status_code=404, detail="解析任务不存在")
    return schemas.ParseTask(**status)


@router.get("/{doc_id}/chunks/{chunk_index}", response_model=schemas.Chunk)
def get_chunk(doc_id: int, chunk_index: int, db: Session = Depends(get_db)):
    chunk = db.query(models.Chunk).filter(
        models.Chunk.document_id == doc_id,
        models.Chunk.chunk_index == chunk_index
    ).first()

    if not chunk:
        raise HTTPException(status_code=404, detail="分块不存在")

    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()

    return schemas.Chunk(
        id=chunk.id,
        content=chunk.content,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        content_type=chunk.content_type,
        page_number=chunk.page_number,
        token_count=chunk.token_count,
        keywords=chunk.keywords,
        metadata=chunk.metadata,
        created_at=chunk.created_at,
        document_title=doc.title if doc else None,
    )


@router.post("/{doc_id}/reparse", response_model=schemas.ParseTask)
async def reparse_document(
    doc_id: int,
    background_tasks: BackgroundTasks,
    chunk_strategy: Optional[schemas.ChunkStrategy] = Query(None),
    chunk_size: Optional[int] = Query(None, ge=128, le=4096),
    chunk_overlap: Optional[int] = Query(None, ge=0, le=512),
    semantic_threshold: Optional[float] = Query(None, ge=0.3, le=0.7),
    db: Session = Depends(get_db)
):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    service_manager.pipeline.delete_document_data(db, doc_id)

    for chunk in doc.chunks:
        db.delete(chunk)

    chunking_config = None
    if chunk_strategy:
        chunking_config = {
            "strategy": chunk_strategy.value,
            "chunk_size": chunk_size or settings.DEFAULT_CHUNK_SIZE,
            "chunk_overlap": chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP,
            "semantic_threshold": semantic_threshold or settings.DEFAULT_SEMANTIC_THRESHOLD,
        }

    doc.parse_status = models.ParseStatus.PENDING
    doc.parse_error = None
    doc.total_chunks = 0
    db.commit()

    background_tasks.add_task(process_document_background, doc_id, chunking_config)

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


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    service_manager.pipeline.delete_document_data(db, doc_id)

    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file {doc.file_path}: {e}")

    db.delete(doc)
    db.commit()

    return None


@router.get("/{doc_id}/download")
def download_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        doc.file_path,
        filename=doc.filename,
        media_type="application/octet-stream"
    )
