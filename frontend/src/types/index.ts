export interface KnowledgeBase {
  id: number
  name: string
  description?: string
  document_count: number
  created_at: string
  updated_at?: string
}

export interface Document {
  id: number
  title: string
  knowledge_base_id: number
  filename: string
  file_type: string
  file_size: number
  page_count: number
  parse_status: 'pending' | 'parsing' | 'completed' | 'failed'
  parse_error?: string
  chunk_strategy?: string
  chunk_size?: number
  total_chunks?: number
  avg_chunk_length?: number
  created_at: string
  updated_at?: string
}

export interface Chunk {
  id: number
  content: string
  document_id: number
  chunk_index: number
  content_type: string
  page_number?: number
  token_count: number
  keywords?: string[]
  metadata?: Record<string, any>
  created_at: string
  document_title?: string
}

export interface ParseTask {
  id: number
  document_id: number
  status: 'pending' | 'parsing' | 'completed' | 'failed'
  stage?: string
  progress: number
  processed_chunks: number
  total_chunks: number
  estimated_remaining?: number
  error_message?: string
  started_at?: string
  completed_at?: string
}

export interface Conversation {
  id: number
  knowledge_base_id?: number
  title?: string
  message_count: number
  created_at: string
  updated_at?: string
}

export interface Message {
  id: number
  conversation_id: number
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  retrieval_debug?: RetrievalDebug
  evaluation?: EvaluationMetrics
  response_time?: number
  created_at: string
  is_compare?: boolean
  compare_kb_ids?: number[]
  compare_results?: any
  graph_results?: GraphQueryResult
  graph_debug?: GraphQueryDebug
  graph_citations?: GraphCitation[]
}

export interface Citation {
  index: number
  chunk_id: number
  document_id: number
  document_title: string
  chunk_index: number
  page_number?: number
  content: string
  semantic_score?: number
  bm25_score?: number
  rrf_score?: number
  rerank_score?: number
}

export interface RetrievalDebug {
  semantic_retrieval: any[]
  bm25_retrieval: any[]
  rrf_fusion: any[]
  reranked: any[]
}

export interface EvaluationMetrics {
  faithfulness: number
  answer_relevancy: number
  context_precision: number
  faithfulness_reason?: string
  answer_relevancy_reason?: string
  context_precision_reason?: string
}

export interface RetrievalResult {
  chunk_id: number
  document_id: number
  document_title: string
  chunk_index: number
  content: string
  page_number?: number
  semantic_score?: number
  bm25_score?: number
  rrf_score?: number
  rerank_score?: number
}

export interface ChatResponse {
  answer: string
  conversation_id: number
  citations: Citation[]
  retrieval_results: RetrievalResult[]
  retrieval_debug: RetrievalDebug
  evaluation?: EvaluationMetrics
}

export interface RetrievalStrategy {
  semantic_top_k: number
  bm25_top_k: number
  use_rrf: boolean
  rrf_k: number
  use_rerank: boolean
  rerank_n: number
}

export interface ChatRequest {
  question: string
  conversation_id?: number
  knowledge_base_id?: number
  stream?: boolean
  top_k?: number
  rerank_n?: number
  strategy?: RetrievalStrategy
}

export interface SystemConfig {
  llm_endpoint: string
  llm_api_key: string
  llm_model: string
  embedding_model: string
  cross_encoder_model: string
  default_chunk_strategy: string
  default_chunk_size: number
  default_chunk_overlap: number
  retrieval_top_k: number
  rerank_top_n: number
  prompt_template: string
}

export interface UsageStats {
  total_qa_count: number
  avg_response_time: number
  retrieval_hit_rate: number
  total_documents: number
  total_knowledge_bases: number
  total_chunks: number
}

export interface ChunkingConfig {
  strategy: 'token' | 'paragraph' | 'semantic'
  chunk_size: number
  chunk_overlap: number
  semantic_threshold: number
}

export interface CompareRequest {
  question: string
  knowledge_base_ids: number[]
  conversation_id?: number
  stream?: boolean
  top_k?: number
  rerank_n?: number
  strategy?: RetrievalStrategy
}

export interface KnowledgeBaseRetrievalResult {
  knowledge_base_id: number
  knowledge_base_name: string
  retrieval_results: RetrievalResult[]
  retrieval_debug: RetrievalDebug
}

export interface CompareViewpoint {
  viewpoint: string
  knowledge_base_id: number
  knowledge_base_name: string
  document_id: number
  document_title: string
  chunk_id: number
  page_number?: number
}

export interface CompareAnalysis {
  comparison_table?: Record<string, any>[]
  viewpoints: CompareViewpoint[]
  summary: string
}

export interface CompareChatResponse {
  answer: string
  conversation_id: number
  kb_results: KnowledgeBaseRetrievalResult[]
  analysis: CompareAnalysis
  citations: Citation[]
  evaluation?: EvaluationMetrics
}

export interface VisualizationPoint {
  x: number
  y: number
  chunk_id: number
  document_id: number
  document_title: string
  chunk_index: number
  content_preview: string
  relevance_score: number
}

export interface VisualizationData {
  query_point: VisualizationPoint
  chunks: VisualizationPoint[]
  score_data: Record<string, any>[]
  explained_variance_ratio: number[]
}

export interface VisualizationResponse {
  visualization: VisualizationData
  retrieval_debug: RetrievalDebug
  retrieval_results: RetrievalResult[]
}

export interface ABCompareRequest {
  question: string
  knowledge_base_id: number
  conversation_id?: number
  stream?: boolean
  strategy_a: RetrievalStrategy
  strategy_b: RetrievalStrategy
}

export interface StrategyResult {
  strategy_name: string
  strategy_config: RetrievalStrategy
  retrieval_time_ms: number
  chunk_count: number
  final_score: number
  retrieval_results: RetrievalResult[]
  retrieval_debug: RetrievalDebug
  answer: string
  citations: Citation[]
}

export interface ABCompareResponse {
  conversation_id: number
  strategy_a: StrategyResult
  strategy_b: StrategyResult
  question: string
}

export type EntityType = 'person' | 'organization' | 'location' | 'tech_concept' | 'event'
export type RelationType = 'belongs_to' | 'located_in' | 'created_by' | 'uses' | 'depends_on' | 'contains'
export type GraphBuildStatus = 'pending' | 'building' | 'completed' | 'failed'

export interface GraphEntity {
  id: number
  knowledge_base_id: number
  name: string
  entity_type: EntityType
  description?: string
  neo4j_id?: string
  occurrence_count: number
  document_count: number
  degree: number
  related_chunks: Record<string, any>[]
  metadata?: Record<string, any>
  created_at: string
  updated_at?: string
}

export interface GraphRelation {
  id: number
  knowledge_base_id: number
  source_entity_id: number
  target_entity_id: number
  relation_type: RelationType
  description?: string
  neo4j_id?: string
  frequency: number
  source_entity_name?: string
  target_entity_name?: string
  source_entity_type?: EntityType
  target_entity_type?: EntityType
  created_at: string
  updated_at?: string
}

export interface EntityOccurrence {
  id: number
  entity_id: number
  document_id: number
  chunk_id: number
  document_title?: string
  chunk_index?: number
  context_snippet?: string
  start_pos?: number
  end_pos?: number
  confidence: number
  created_at: string
}

export interface GraphEntityDetail extends GraphEntity {
  occurrences: EntityOccurrence[]
  source_relations: GraphRelation[]
  target_relations: GraphRelation[]
}

export interface GraphEntityCreate {
  knowledge_base_id: number
  name: string
  entity_type: EntityType
  description?: string
  metadata?: Record<string, any>
}

export interface GraphEntityUpdate {
  name?: string
  entity_type?: EntityType
  description?: string
  metadata?: Record<string, any>
}

export interface GraphRelationCreate {
  knowledge_base_id: number
  source_entity_id: number
  target_entity_id: number
  relation_type: RelationType
  description?: string
  metadata?: Record<string, any>
}

export interface GraphRelationUpdate {
  relation_type?: RelationType
  description?: string
  metadata?: Record<string, any>
}

export interface GraphStats {
  knowledge_base_id: number
  entity_count: number
  relation_count: number
  connected_components: number
  avg_degree: number
  max_degree: number
  community_count: number
  entity_types_distribution: Record<string, number>
  relation_types_distribution: Record<string, number>
  build_status: GraphBuildStatus
  last_built_at?: string
}

export interface GraphNode {
  id: string
  name: string
  entity_type: EntityType
  size: number
  degree: number
  community_id?: number
  x?: number
  y?: number
  is_super_node: boolean
  super_node_members?: string[]
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  relation_type: RelationType
  width: number
  frequency: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: GraphStats
}

export interface GraphPath {
  path: Record<string, any>[]
  score: number
}

export interface GraphQueryResult {
  query_entities: string[]
  paths: GraphPath[]
  related_entities: GraphEntity[]
  graph_context: string
}

export interface GraphQueryDebug {
  query_entities: string[]
  cypher_queries: string[]
  paths_found: number
  graph_context_length: number
}

export interface GraphBuildRequest {
  knowledge_base_id: number
  document_ids?: number[]
  rebuild: boolean
}

export interface GraphBuildProgress {
  status: GraphBuildStatus
  progress: number
  stage?: string
  entity_count: number
  relation_count: number
  error?: string
}

export interface GraphQueryRequest {
  question: string
  knowledge_base_id: number
  max_hops?: number
  max_entities?: number
}

export interface ChatGraphRequest extends ChatRequest {
  use_graph?: boolean
  graph_max_hops?: number
}

export interface ChatGraphResponse extends ChatResponse {
  graph_results?: GraphQueryResult
  graph_debug?: GraphQueryDebug
  graph_citations?: Record<string, any>[]
}

export interface GraphCitation {
  type: 'graph'
  entity: string
  entity_type: EntityType
  occurrence_count: number
}
