import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base
from app.middleware import AuthMiddleware, LoggingMiddleware, CORSMiddleware as CustomCORSMiddleware
from app.routers import kb_router, doc_router, chat_router, admin_router, graph_router
from app.services.pipeline_service import service_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.MODELS_DIR, exist_ok=True)

    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    logger.info("Initializing service manager...")
    try:
        service_manager.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)

    from app import models
    from sqlalchemy.orm import Session
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        default_kb = db.query(models.KnowledgeBase).filter(
            models.KnowledgeBase.name == "默认知识库"
        ).first()
        if not default_kb:
            default_kb = models.KnowledgeBase(
                name="默认知识库",
                description="系统默认创建的知识库"
            )
            db.add(default_kb)
            db.commit()
            logger.info("Created default knowledge base")

            try:
                service_manager.vector_store.create_collection(default_kb.id, "text")
                service_manager.bm25_index.build_index(default_kb.id, [])
            except Exception as e:
                logger.warning(f"Failed to initialize default KB indices: {e}")
    finally:
        db.close()

    logger.info("Application started successfully")
    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title="多模态RAG问答系统",
    description="支持多模态文档的检索增强生成问答系统",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kb_router)
app.include_router(doc_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(graph_router)

if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
async def root():
    return {
        "app": "多模态RAG问答系统",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "database": "ok",
            "vector_store": "ok" if service_manager.vector_store else "not initialized",
            "embedding": "ok" if service_manager.embedding_service else "not initialized",
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "服务器内部错误",
            "error": str(exc) if os.getenv("DEBUG") else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
