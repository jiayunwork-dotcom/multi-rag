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

export interface ChatRequest {
  question: string
  conversation_id?: number
  knowledge_base_id?: number
  stream?: boolean
  top_k?: number
  rerank_n?: number
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
