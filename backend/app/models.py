from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum


class ParseStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkStrategy(str, enum.Enum):
    TOKEN = "token"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    title = Column(String(255), nullable=False)
    filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    page_count = Column(Integer, default=0)
    parse_status = Column(String(50), default=ParseStatus.PENDING, nullable=False)
    parse_error = Column(Text, nullable=True)
    chunk_strategy = Column(String(50), nullable=True)
    chunk_size = Column(Integer, nullable=True)
    chunk_overlap = Column(Integer, nullable=True)
    semantic_threshold = Column(Float, nullable=True)
    total_chunks = Column(Integer, default=0)
    avg_chunk_length = Column(Float, default=0)
    max_chunk_length = Column(Integer, default=0)
    min_chunk_length = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    parse_tasks = relationship("ParseTask", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(50), default="text")
    page_number = Column(Integer, nullable=True)
    token_count = Column(Integer, default=0)
    embedding_id = Column(String(255), nullable=True)
    keywords = Column(JSON, nullable=True)
    chunk_metadata = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")


class ParseTask(Base):
    __tablename__ = "parse_tasks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    status = Column(String(50), default=ParseStatus.PENDING, nullable=False)
    stage = Column(String(100), nullable=True)
    progress = Column(Float, default=0.0)
    processed_chunks = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    estimated_remaining = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="parse_tasks")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=True)
    title = Column(String(255), nullable=True)
    history_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)
    retrieval_debug = Column(JSON, nullable=True)
    evaluation = Column(JSON, nullable=True)
    response_time = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


class BM25Index(Base):
    __tablename__ = "bm25_indices"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_base_id = Column(Integer, nullable=False)
    keyword = Column(String(255), nullable=False, index=True)
    chunk_ids = Column(JSON, nullable=False)
    doc_freq = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemStats(Base):
    __tablename__ = "system_stats"

    id = Column(Integer, primary_key=True, index=True)
    stat_key = Column(String(100), unique=True, nullable=False)
    stat_value = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
