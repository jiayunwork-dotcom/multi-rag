from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://raguser:ragpass@localhost:5432/ragdb"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    UPLOAD_DIR: str = "uploads"
    MODELS_DIR: str = "models"

    LLM_ENDPOINT: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "qwen2.5"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048

    API_TOKEN: str = "rag-token-secret"

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    CLIP_MODEL: str = "ViT-B-32"
    CLIP_PRETRAINED: str = "laion2b_s34b_b79k"
    VISION_EMBEDDING_DIM: int = 512

    DEFAULT_CHUNK_STRATEGY: str = "token"
    DEFAULT_CHUNK_SIZE: int = 512
    DEFAULT_CHUNK_OVERLAP: int = 50
    DEFAULT_SEMANTIC_THRESHOLD: float = 0.5

    RETRIEVAL_TOP_K: int = 10
    RRF_K: int = 60
    RERANK_TOP_N: int = 5

    MAX_BATCH_UPLOAD: int = 20
    MAX_FILE_SIZE_MB: int = 50

    PROMPT_TEMPLATE: str = """基于以下参考资料回答用户问题，如果参考资料中没有相关信息请说明无法回答。
参考资料:
{context}
用户问题:
{question}
"""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
