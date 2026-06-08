from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ParseStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkStrategy(str, Enum):
    TOKEN = "token"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"


class KnowledgeBaseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class KnowledgeBase(KnowledgeBaseBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    document_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DocumentBase(BaseModel):
    title: str
    knowledge_base_id: int


class DocumentCreate(DocumentBase):
    filename: str
    file_type: str
    file_size: int
    file_path: str
    page_count: int = 0


class Document(DocumentBase):
    id: int
    filename: str
    file_type: str
    file_size: int
    page_count: int
    parse_status: ParseStatus
    parse_error: Optional[str]
    chunk_strategy: Optional[str]
    chunk_size: Optional[int]
    total_chunks: Optional[int]
    avg_chunk_length: Optional[float]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(Document):
    chunks: List["Chunk"] = []


class ChunkBase(BaseModel):
    content: str


class ChunkCreate(ChunkBase):
    document_id: int
    chunk_index: int
    content_type: str = "text"
    page_number: Optional[int] = None
    token_count: int = 0
    keywords: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class Chunk(ChunkBase):
    id: int
    document_id: int
    chunk_index: int
    content_type: str
    page_number: Optional[int]
    token_count: int
    keywords: Optional[List[str]]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    document_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChunkStats(BaseModel):
    total_chunks: int
    avg_chunk_length: float
    max_chunk_length: int
    min_chunk_length: int


class ParseTaskBase(BaseModel):
    pass


class ParseTask(ParseTaskBase):
    id: int
    document_id: int
    status: ParseStatus
    stage: Optional[str]
    progress: float
    processed_chunks: int
    total_chunks: int
    estimated_remaining: Optional[int]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ChunkingConfig(BaseModel):
    strategy: ChunkStrategy = ChunkStrategy.TOKEN
    chunk_size: int = Field(default=512, ge=128, le=4096)
    chunk_overlap: int = Field(default=50, ge=0, le=512)
    semantic_threshold: float = Field(default=0.5, ge=0.3, le=0.7)


class MessageBase(BaseModel):
    role: str
    content: str


class MessageCreate(MessageBase):
    conversation_id: int
    citations: Optional[List[Dict[str, Any]]] = None
    retrieval_debug: Optional[Dict[str, Any]] = None
    evaluation: Optional[Dict[str, Any]] = None


class Message(MessageBase):
    id: int
    conversation_id: int
    citations: Optional[List[Dict[str, Any]]]
    retrieval_debug: Optional[Dict[str, Any]]
    evaluation: Optional[Dict[str, Any]]
    response_time: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationBase(BaseModel):
    knowledge_base_id: Optional[int] = None
    title: Optional[str] = None


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(BaseModel):
    title: Optional[str] = None


class Conversation(ConversationBase):
    id: int
    message_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(Conversation):
    messages: List[Message] = []


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    knowledge_base_id: Optional[int] = None
    stream: bool = False
    top_k: int = Field(default=10, ge=1, le=50)
    rerank_n: int = Field(default=5, ge=1, le=20)


class RetrievalResult(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    page_number: Optional[int]
    semantic_score: Optional[float]
    bm25_score: Optional[float]
    rrf_score: Optional[float]
    rerank_score: Optional[float]


class ChatResponse(BaseModel):
    answer: str
    conversation_id: int
    citations: List[Dict[str, Any]]
    retrieval_results: List[RetrievalResult]
    retrieval_debug: Dict[str, Any]
    evaluation: Optional[Dict[str, Any]]


class EvaluationMetrics(BaseModel):
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    faithfulness_reason: Optional[str]
    answer_relevancy_reason: Optional[str]
    context_precision_reason: Optional[str]


class SystemConfig(BaseModel):
    llm_endpoint: str
    llm_api_key: str
    llm_model: str
    embedding_model: str
    cross_encoder_model: str
    default_chunk_strategy: str
    default_chunk_size: int
    default_chunk_overlap: int
    retrieval_top_k: int
    rerank_top_n: int
    prompt_template: str


class SystemConfigUpdate(BaseModel):
    llm_endpoint: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    embedding_model: Optional[str] = None
    cross_encoder_model: Optional[str] = None
    default_chunk_strategy: Optional[str] = None
    default_chunk_size: Optional[int] = None
    default_chunk_overlap: Optional[int] = None
    retrieval_top_k: Optional[int] = None
    rerank_top_n: Optional[int] = None
    prompt_template: Optional[str] = None


class UsageStats(BaseModel):
    total_qa_count: int
    avg_response_time: float
    retrieval_hit_rate: float
    total_documents: int
    total_knowledge_bases: int
    total_chunks: int


DocumentDetail.model_rebuild()
