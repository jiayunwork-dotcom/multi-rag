import os
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
import logging
from sqlalchemy.orm import Session

from .. import models
from .document_parser import DocumentParser
from .chunking_service import ChunkingService
from .embedding_service import EmbeddingService
from .vector_store import VectorStore
from .bm25_index import BM25Index
from ..config import settings

logger = logging.getLogger(__name__)


class DocumentPipeline:
    def __init__(
        self,
        document_parser: DocumentParser,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        bm25_index: BM25Index
    ):
        self.document_parser = document_parser
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.active_tasks = {}

    async def process_document(
        self,
        db: Session,
        document_id: int,
        chunking_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        document = db.query(models.Document).filter(
            models.Document.id == document_id
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        parse_task = models.ParseTask(
            document_id=document_id,
            status=models.ParseStatus.PENDING,
            stage="初始化",
            progress=0.0,
            started_at=datetime.utcnow()
        )
        db.add(parse_task)
        db.commit()
        db.refresh(parse_task)

        self.active_tasks[document_id] = parse_task.id

        try:
            await self._update_progress(db, parse_task, 5, "正在解析文档...", models.ParseStatus.PARSING)

            content, page_count, page_contents = await asyncio.to_thread(
                self.document_parser.parse,
                document.file_path,
                document.file_type
            )

            document.page_count = page_count
            await self._update_progress(db, parse_task, 25, "文档解析完成，正在分块...")

            strategy = chunking_config.get("strategy", settings.DEFAULT_CHUNK_STRATEGY) if chunking_config else settings.DEFAULT_CHUNK_STRATEGY
            chunk_size = chunking_config.get("chunk_size", settings.DEFAULT_CHUNK_SIZE) if chunking_config else settings.DEFAULT_CHUNK_SIZE
            chunk_overlap = chunking_config.get("chunk_overlap", settings.DEFAULT_CHUNK_OVERLAP) if chunking_config else settings.DEFAULT_CHUNK_OVERLAP
            semantic_threshold = chunking_config.get("semantic_threshold", settings.DEFAULT_SEMANTIC_THRESHOLD) if chunking_config else settings.DEFAULT_SEMANTIC_THRESHOLD

            document.chunk_strategy = strategy
            document.chunk_size = chunk_size
            document.chunk_overlap = chunk_overlap
            document.semantic_threshold = semantic_threshold

            chunks, chunk_stats = await asyncio.to_thread(
                self.chunking_service.chunk,
                content,
                strategy,
                chunk_size,
                chunk_overlap,
                semantic_threshold,
                page_contents
            )

            parse_task.total_chunks = chunk_stats["total_chunks"]
            document.total_chunks = chunk_stats["total_chunks"]
            document.avg_chunk_length = chunk_stats["avg_chunk_length"]
            document.max_chunk_length = chunk_stats["max_chunk_length"]
            document.min_chunk_length = chunk_stats["min_chunk_length"]

            await self._update_progress(db, parse_task, 40, f"分块完成，共{len(chunks)}个块，正在生成嵌入...")

            db_chunks = []
            for chunk_data in chunks:
                keywords = self.chunking_service.extract_keywords(chunk_data["content"])
                db_chunk = models.Chunk(
                    document_id=document_id,
                    chunk_index=chunk_data["chunk_index"],
                    content=chunk_data["content"],
                    content_type="text",
                    page_number=chunk_data.get("page_number"),
                    token_count=chunk_data["token_count"],
                    keywords=keywords,
                    metadata=chunk_data.get("metadata")
                )
                db.add(db_chunk)
                db_chunks.append(db_chunk)

            db.flush()

            chunk_dicts = []
            for db_chunk in db_chunks:
                chunk_dicts.append({
                    "id": db_chunk.id,
                    "document_id": db_chunk.document_id,
                    "chunk_index": db_chunk.chunk_index,
                    "content": db_chunk.content,
                    "page_number": db_chunk.page_number,
                })

            await self._update_progress(db, parse_task, 50, "正在生成文本嵌入...")

            texts = [c["content"] for c in chunk_dicts]
            embeddings = await asyncio.to_thread(
                self.embedding_service.encode_texts,
                texts
            )

            await self._update_progress(db, parse_task, 70, "正在存储向量...")

            embedding_ids = await asyncio.to_thread(
                self.vector_store.add_chunks,
                document.knowledge_base_id,
                chunk_dicts,
                embeddings,
                "text"
            )

            for db_chunk, emb_id in zip(db_chunks, embedding_ids):
                db_chunk.embedding_id = emb_id

            await self._update_progress(db, parse_task, 85, "正在构建BM25索引...")

            await asyncio.to_thread(
                self.bm25_index.add_chunks,
                document.knowledge_base_id,
                chunk_dicts
            )

            document.parse_status = models.ParseStatus.COMPLETED
            parse_task.status = models.ParseStatus.COMPLETED
            parse_task.progress = 100.0
            parse_task.stage = "处理完成"
            parse_task.processed_chunks = len(chunks)
            parse_task.completed_at = datetime.utcnow()

            db.commit()

            if progress_callback:
                await progress_callback({
                    "task_id": parse_task.id,
                    "status": "completed",
                    "progress": 100.0,
                    "stage": "处理完成"
                })

            logger.info(f"Document {document_id} processed successfully: {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
            document.parse_status = models.ParseStatus.FAILED
            document.parse_error = str(e)
            parse_task.status = models.ParseStatus.FAILED
            parse_task.error_message = str(e)
            parse_task.completed_at = datetime.utcnow()
            db.commit()

            if progress_callback:
                await progress_callback({
                    "task_id": parse_task.id,
                    "status": "failed",
                    "error": str(e)
                })

            raise
        finally:
            if document_id in self.active_tasks:
                del self.active_tasks[document_id]

    async def _update_progress(
        self,
        db: Session,
        parse_task: models.ParseTask,
        progress: float,
        stage: str,
        status: Optional[str] = None
    ):
        parse_task.progress = progress
        parse_task.stage = stage
        if status:
            parse_task.status = status

        elapsed = (datetime.utcnow() - parse_task.started_at).total_seconds() if parse_task.started_at else 0
        if progress > 0 and parse_task.total_chunks > 0:
            parse_task.processed_chunks = int(parse_task.total_chunks * progress / 100)
            remaining = elapsed * (100 - progress) / progress
            parse_task.estimated_remaining = int(remaining)

        db.commit()

    def get_task_status(self, db: Session, document_id: int) -> Optional[Dict[str, Any]]:
        parse_task = db.query(models.ParseTask).filter(
            models.ParseTask.document_id == document_id
        ).order_by(models.ParseTask.started_at.desc()).first()

        if not parse_task:
            return None

        return {
            "id": parse_task.id,
            "document_id": parse_task.document_id,
            "status": parse_task.status,
            "stage": parse_task.stage,
            "progress": parse_task.progress,
            "processed_chunks": parse_task.processed_chunks,
            "total_chunks": parse_task.total_chunks,
            "estimated_remaining": parse_task.estimated_remaining,
            "error_message": parse_task.error_message,
            "started_at": parse_task.started_at,
            "completed_at": parse_task.completed_at,
        }

    def delete_document_data(self, db: Session, document_id: int):
        document = db.query(models.Document).filter(
            models.Document.id == document_id
        ).first()

        if not document:
            return

        chunk_ids = [c.id for c in document.chunks]

        self.vector_store.delete_chunks_by_document(
            document.knowledge_base_id,
            document_id
        )

        self.bm25_index.delete_chunks(
            document.knowledge_base_id,
            chunk_ids
        )

        logger.info(f"Deleted index data for document {document_id}")


class ServiceManager:
    _instance = None

    def __init__(self):
        self.document_parser = None
        self.embedding_service = None
        self.chunking_service = None
        self.vector_store = None
        self.bm25_index = None
        self.retrieval_service = None
        self.llm_service = None
        self.evaluation_service = None
        self.pipeline = None
        self._initialized = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self):
        if self._initialized:
            return

        logger.info("Initializing service manager...")

        self.document_parser = DocumentParser(settings.UPLOAD_DIR)

        self.embedding_service = EmbeddingService(
            text_model_name=settings.EMBEDDING_MODEL,
            clip_model_name=settings.CLIP_MODEL,
            clip_pretrained=settings.CLIP_PRETRAINED,
            cross_encoder_name=settings.CROSS_ENCODER_MODEL,
            cache_dir=settings.MODELS_DIR
        )

        self.chunking_service = ChunkingService(self.embedding_service)

        self.vector_store = VectorStore(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT
        )

        self.bm25_index = BM25Index()

        from .retrieval_service import RetrievalService
        self.retrieval_service = RetrievalService(
            self.vector_store,
            self.bm25_index,
            self.embedding_service,
            rrf_k=settings.RRF_K
        )

        from .llm_service import LLMService
        self.llm_service = LLMService(
            endpoint=settings.LLM_ENDPOINT,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            default_prompt_template=settings.PROMPT_TEMPLATE,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS
        )

        self.evaluation_service = EvaluationService(self.embedding_service)

        self.pipeline = DocumentPipeline(
            self.document_parser,
            self.chunking_service,
            self.embedding_service,
            self.vector_store,
            self.bm25_index
        )

        self._initialized = True
        logger.info("Service manager initialized successfully")


service_manager = ServiceManager.get_instance()
