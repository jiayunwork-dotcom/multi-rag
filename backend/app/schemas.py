from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Literal
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


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    TECH_CONCEPT = "tech_concept"
    EVENT = "event"


class RelationType(str, Enum):
    BELONGS_TO = "belongs_to"
    LOCATED_IN = "located_in"
    CREATED_BY = "created_by"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    CONTAINS = "contains"


class GraphBuildStatus(str, Enum):
    PENDING = "pending"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


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


class RetrievalStrategy(BaseModel):
    semantic_top_k: int = Field(default=20, ge=1, le=50)
    bm25_top_k: int = Field(default=20, ge=1, le=50)
    use_rrf: bool = True
    rrf_k: int = Field(default=60, ge=10, le=120)
    use_rerank: bool = True
    rerank_n: int = Field(default=5, ge=1, le=20)


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    knowledge_base_id: Optional[int] = None
    stream: bool = False
    top_k: int = Field(default=10, ge=1, le=50)
    rerank_n: int = Field(default=5, ge=1, le=20)
    strategy: Optional[RetrievalStrategy] = None


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


class CompareRequest(BaseModel):
    question: str
    knowledge_base_ids: List[int] = Field(..., min_length=2, max_length=3)
    conversation_id: Optional[int] = None
    stream: bool = False
    top_k: int = Field(default=10, ge=1, le=50)
    rerank_n: int = Field(default=5, ge=1, le=20)
    strategy: Optional[RetrievalStrategy] = None


class KnowledgeBaseRetrievalResult(BaseModel):
    knowledge_base_id: int
    knowledge_base_name: str
    retrieval_results: List[RetrievalResult]
    retrieval_debug: Dict[str, Any]


class CompareViewpoint(BaseModel):
    viewpoint: str
    knowledge_base_id: int
    knowledge_base_name: str
    document_id: int
    document_title: str
    chunk_id: int
    page_number: Optional[int] = None


class CompareAnalysis(BaseModel):
    comparison_table: Optional[List[Dict[str, Any]]] = None
    viewpoints: List[CompareViewpoint]
    summary: str


class CompareChatResponse(BaseModel):
    answer: str
    conversation_id: int
    kb_results: List[KnowledgeBaseRetrievalResult]
    analysis: CompareAnalysis
    citations: List[Dict[str, Any]]
    evaluation: Optional[Dict[str, Any]] = None


class VisualizationPoint(BaseModel):
    x: float
    y: float
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content_preview: str
    relevance_score: float


class VisualizationData(BaseModel):
    query_point: VisualizationPoint
    chunks: List[VisualizationPoint]
    score_data: List[Dict[str, Any]]
    explained_variance_ratio: List[float]


class ABCompareRequest(BaseModel):
    question: str
    knowledge_base_id: int
    conversation_id: Optional[int] = None
    stream: bool = False
    strategy_a: RetrievalStrategy
    strategy_b: RetrievalStrategy


class StrategyResult(BaseModel):
    strategy_name: str
    strategy_config: RetrievalStrategy
    retrieval_time_ms: float
    chunk_count: int
    final_score: float
    retrieval_results: List[RetrievalResult]
    retrieval_debug: Dict[str, Any]
    answer: str
    citations: List[Dict[str, Any]]


class ABCompareResponse(BaseModel):
    conversation_id: int
    strategy_a: StrategyResult
    strategy_b: StrategyResult
    question: str


DocumentDetail.model_rebuild()


class GraphEntityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    entity_type: EntityType
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GraphEntityCreate(GraphEntityBase):
    knowledge_base_id: int


class GraphEntityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    entity_type: Optional[EntityType] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GraphEntity(GraphEntityBase):
    id: int
    knowledge_base_id: int
    neo4j_id: Optional[str] = None
    occurrence_count: int = 0
    document_count: int = 0
    degree: int = 0
    related_chunks: List[Dict[str, Any]] = []
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class GraphEntityDetail(GraphEntity):
    occurrences: List["EntityOccurrence"] = []
    source_relations: List["GraphRelation"] = []
    target_relations: List["GraphRelation"] = []


class GraphRelationBase(BaseModel):
    source_entity_id: int
    target_entity_id: int
    relation_type: RelationType
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GraphRelationCreate(GraphRelationBase):
    knowledge_base_id: int


class GraphRelationUpdate(BaseModel):
    relation_type: Optional[RelationType] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GraphRelation(GraphRelationBase):
    id: int
    knowledge_base_id: int
    neo4j_id: Optional[str] = None
    frequency: int = 0
    source_entity_name: Optional[str] = None
    target_entity_name: Optional[str] = None
    source_entity_type: Optional[EntityType] = None
    target_entity_type: Optional[EntityType] = None
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class EntityOccurrence(BaseModel):
    id: int
    entity_id: int
    document_id: int
    chunk_id: int
    document_title: Optional[str] = None
    chunk_index: Optional[int] = None
    context_snippet: Optional[str] = None
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None
    confidence: float = 1.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RelationOccurrence(BaseModel):
    id: int
    relation_id: int
    document_id: int
    chunk_id: int
    document_title: Optional[str] = None
    chunk_index: Optional[int] = None
    context_snippet: Optional[str] = None
    confidence: float = 1.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedEntity(BaseModel):
    name: str
    entity_type: EntityType
    context_snippet: str
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None
    confidence: float = 0.8


class ExtractedRelation(BaseModel):
    source_entity: str
    target_entity: str
    source_type: EntityType
    target_type: EntityType
    relation_type: RelationType
    context_snippet: str
    confidence: float = 0.8


class GraphExtractionResult(BaseModel):
    entities: List[ExtractedEntity]
    relations: List[ExtractedRelation]


class GraphBuildRequest(BaseModel):
    knowledge_base_id: int
    document_ids: Optional[List[int]] = None
    rebuild: bool = False


class GraphBuildProgress(BaseModel):
    status: GraphBuildStatus
    progress: float
    stage: Optional[str] = None
    entity_count: int = 0
    relation_count: int = 0
    error: Optional[str] = None


class GraphStats(BaseModel):
    knowledge_base_id: int
    entity_count: int
    relation_count: int
    connected_components: int
    avg_degree: float
    max_degree: int
    community_count: int
    entity_types_distribution: Dict[str, int]
    relation_types_distribution: Dict[str, int]
    build_status: GraphBuildStatus
    last_built_at: Optional[datetime]


class GraphNode(BaseModel):
    id: str
    name: str
    entity_type: EntityType
    size: int = 10
    degree: int = 0
    community_id: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    is_super_node: bool = False
    super_node_members: Optional[List[str]] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation_type: RelationType
    width: float = 1.0
    frequency: int = 1


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: GraphStats


class GraphQueryRequest(BaseModel):
    question: str
    knowledge_base_id: int
    max_hops: int = 2
    max_entities: int = 10


class GraphPath(BaseModel):
    path: List[Dict[str, Any]]
    score: float


class GraphQueryResult(BaseModel):
    query_entities: List[str]
    paths: List[GraphPath]
    related_entities: List[GraphEntity]
    graph_context: str


class GraphQueryDebug(BaseModel):
    query_entities: List[str]
    cypher_queries: List[str]
    paths_found: int
    graph_context_length: int


class ChatGraphRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    knowledge_base_id: Optional[int] = None
    stream: bool = False
    top_k: int = Field(default=10, ge=1, le=50)
    rerank_n: int = Field(default=5, ge=1, le=20)
    use_graph: bool = False
    graph_max_hops: int = 2
    strategy: Optional[RetrievalStrategy] = None


class ChatGraphResponse(ChatResponse):
    graph_results: Optional[GraphQueryResult] = None
    graph_debug: Optional[GraphQueryDebug] = None
    graph_citations: Optional[List[Dict[str, Any]]] = None


GraphEntityDetail.model_rebuild()


class GraphVersionSnapshotEntity(BaseModel):
    entity_id: int
    name: str
    entity_type: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GraphVersionSnapshotRelation(BaseModel):
    relation_id: int
    source_entity_id: int
    target_entity_id: int
    source_entity_name: str
    target_entity_name: str
    relation_type: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GraphVersionBase(BaseModel):
    knowledge_base_id: int
    version_number: int
    entity_count: int
    relation_count: int
    connected_components: int
    description: Optional[str] = None
    created_at: datetime


class GraphVersion(GraphVersionBase):
    id: int
    entities: List[GraphVersionSnapshotEntity] = []
    relations: List[GraphVersionSnapshotRelation] = []

    model_config = ConfigDict(from_attributes=True)


class GraphVersionDiff(BaseModel):
    version_a_id: int
    version_a_number: int
    version_b_id: int
    version_b_number: int
    added_entities: List[GraphVersionSnapshotEntity] = []
    removed_entities: List[GraphVersionSnapshotEntity] = []
    added_relations: List[GraphVersionSnapshotRelation] = []
    removed_relations: List[GraphVersionSnapshotRelation] = []
    added_entity_count: int
    removed_entity_count: int
    added_relation_count: int
    removed_relation_count: int


class GraphVersionCompareRequest(BaseModel):
    knowledge_base_id: int
    version_a_id: Optional[int] = None
    version_b_id: int


class GraphMergeConflictEntity(BaseModel):
    source_entity: GraphEntity
    target_entity: GraphEntity
    disambiguation_score: float
    source_documents: List[str] = []
    context_snippets: List[str] = []


class PendingConflictEntity(BaseModel):
    entity_id: int
    name: str
    entity_type: str
    source_kb_name: str
    context_summary: str


class PendingConflict(BaseModel):
    conflict_id: str
    entity_a: PendingConflictEntity
    entity_b: PendingConflictEntity
    score: float
    action: Optional[Literal["merge", "keep"]] = None


class GraphMergePreview(BaseModel):
    source_kb_id: int
    target_kb_id: int
    source_kb_name: str
    target_kb_name: str
    source_entity_count: int
    source_relation_count: int
    target_entity_count: int
    target_relation_count: int
    auto_merged_count: int
    pending_count: int
    pending_conflicts: List[PendingConflict] = []


class GraphMergeResolve(BaseModel):
    source_entity_id: int
    target_entity_id: int
    action: Literal["merge", "keep_separate"]


class GraphMergeRequest(BaseModel):
    source_kb_id: int
    target_kb_id: int
    resolutions: List[GraphMergeResolve] = []


class GraphMergeResult(BaseModel):
    success: bool
    new_version_id: Optional[int] = None
    merged_entity_count: int
    merged_relation_count: int
    conflict_resolved_count: int


class GraphQLQueryRequest(BaseModel):
    knowledge_base_id: int
    query: str
    max_hops: int = Field(default=3, ge=1, le=10)


class GraphQLQueryResult(BaseModel):
    query_type: Literal["find", "path", "natural_language"]
    parsed_query: Optional[str] = None
    matched_entities: List[GraphEntity] = []
    matched_paths: List[Dict[str, Any]] = []
    path_edges: List[GraphRelation] = []
    highlight_node_ids: List[str] = []
    highlight_edge_ids: List[str] = []
    execution_time_ms: float = 0.0


class GraphQLAutocompleteRequest(BaseModel):
    knowledge_base_id: int
    prefix: str
    limit: int = Field(default=10, ge=1, le=50)


class GraphQLAutocompleteResult(BaseModel):
    suggestions: List[str] = []


class GraphQueryHistoryItem(BaseModel):
    id: int
    query: str
    created_at: datetime


class GraphQueryHistoryResponse(BaseModel):
    history: List[GraphQueryHistoryItem] = []
