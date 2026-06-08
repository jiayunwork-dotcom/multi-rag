import api from './client'
import type {
  KnowledgeBase, Document, ParseTask, Conversation, Message,
  ChatResponse, ChatRequest, SystemConfig, UsageStats, Chunk,
  CompareRequest, CompareChatResponse, VisualizationResponse,
  ABCompareRequest, ABCompareResponse,
  GraphStats, GraphData, GraphEntity, GraphEntityDetail, GraphRelation,
  GraphEntityCreate, GraphEntityUpdate, GraphRelationCreate, GraphRelationUpdate,
  GraphBuildRequest, GraphBuildProgress, GraphQueryRequest, GraphQueryResult, GraphQueryDebug,
  ChatGraphRequest, ChatGraphResponse
} from '@/types'

export const knowledgeBaseApi = {
  list: () => api.get<KnowledgeBase[]>('/knowledge-bases'),
  get: (id: number) => api.get<KnowledgeBase>(`/knowledge-bases/${id}`),
  create: (data: { name: string; description?: string }) =>
    api.post<KnowledgeBase>('/knowledge-bases', data),
  update: (id: number, data: { name?: string; description?: string }) =>
    api.put<KnowledgeBase>(`/knowledge-bases/${id}`, data),
  delete: (id: number) => api.delete(`/knowledge-bases/${id}`),
}

export const documentApi = {
  list: (params?: { knowledge_base_id?: number; parse_status?: string; skip?: number; limit?: number }) =>
    api.get<Document[]>('/documents', { params }),
  get: (id: number) => api.get<Document>(`/documents/${id}`),
  upload: (
    knowledgeBaseId: number,
    files: File[],
    chunkingConfig?: {
      chunk_strategy?: string
      chunk_size?: number
      chunk_overlap?: number
      semantic_threshold?: number
    }
  ) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    const params: Record<string, any> = { knowledge_base_id: knowledgeBaseId }
    if (chunkingConfig) {
      Object.assign(params, chunkingConfig)
    }
    return api.post<Document[]>('/documents/upload', formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getParseStatus: (id: number) => api.get<ParseTask>(`/documents/${id}/parse-status`),
  getChunk: (docId: number, chunkIndex: number) => api.get<Chunk>(`/documents/${docId}/chunks/${chunkIndex}`),
  reparse: (id: number, chunkingConfig?: {
    chunk_strategy?: string
    chunk_size?: number
    chunk_overlap?: number
    semantic_threshold?: number
  }) => api.post<ParseTask>(`/documents/${id}/reparse`, null, { params: chunkingConfig }),
  delete: (id: number) => api.delete(`/documents/${id}`),
}

export const chatApi = {
  listConversations: (params?: { skip?: number; limit?: number }) =>
    api.get<Conversation[]>('/chat/conversations', { params }),
  createConversation: (data: { knowledge_base_id?: number; title?: string }) =>
    api.post<Conversation>('/chat/conversations', data),
  getConversation: (id: number) => api.get<Conversation & { messages: Message[] }>(`/chat/conversations/${id}`),
  updateConversation: (id: number, data: { title?: string }) =>
    api.put<Conversation>(`/chat/conversations/${id}`, data),
  deleteConversation: (id: number) => api.delete(`/chat/conversations/${id}`),
  deleteMessage: (convId: number, msgId: number) =>
    api.delete(`/chat/conversations/${convId}/messages/${msgId}`),
  getHistory: (conversationId?: number) =>
    api.get<Message[]>('/chat/history', { params: { conversation_id: conversationId } }),
  sendMessage: (data: ChatGraphRequest) =>
    api.post<ChatGraphResponse>('/chat', data),
  sendMessageStream: (data: ChatGraphRequest) => {
    const token = localStorage.getItem('api_token') || 'rag-token-secret'
    return fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ ...data, stream: true })
    })
  },
  sendCompareMessage: (data: CompareRequest) =>
    api.post<CompareChatResponse>('/chat/compare', data),
  getVisualization: (data: ChatRequest) =>
    api.post<VisualizationResponse>('/chat/visualization', data),
  sendABCompare: (data: ABCompareRequest) =>
    api.post<ABCompareResponse>('/chat/ab-compare', data)
}

export const graphApi = {
  getStats: (kbId: number) =>
    api.get<GraphStats>(`/knowledge-graph/${kbId}/stats`),
  getGraphData: (kbId: number, params?: { filter_entity_types?: string[]; limit?: number }) =>
    api.get<GraphData>(`/knowledge-graph/${kbId}/graph-data`, { params }),
  getEntityDetail: (entityId: number) =>
    api.get<GraphEntityDetail>(`/knowledge-graph/entities/${entityId}`),
  listEntities: (kbId: number, params?: { entity_type?: string; skip?: number; limit?: number }) =>
    api.get<GraphEntity[]>(`/knowledge-graph/${kbId}/entities`, { params }),
  listRelations: (kbId: number, params?: { relation_type?: string; skip?: number; limit?: number }) =>
    api.get<GraphRelation[]>(`/knowledge-graph/${kbId}/relations`, { params }),
  createEntity: (data: GraphEntityCreate) =>
    api.post<GraphEntity>('/knowledge-graph/entities', data),
  updateEntity: (entityId: number, data: GraphEntityUpdate) =>
    api.put<GraphEntity>(`/knowledge-graph/entities/${entityId}`, data),
  deleteEntity: (entityId: number) =>
    api.delete(`/knowledge-graph/entities/${entityId}`),
  createRelation: (data: GraphRelationCreate) =>
    api.post<GraphRelation>('/knowledge-graph/relations', data),
  updateRelation: (relationId: number, data: GraphRelationUpdate) =>
    api.put<GraphRelation>(`/knowledge-graph/relations/${relationId}`, data),
  deleteRelation: (relationId: number) =>
    api.delete(`/knowledge-graph/relations/${relationId}`),
  buildGraph: (data: GraphBuildRequest) =>
    api.post<GraphBuildProgress>('/knowledge-graph/build', data),
  getBuildProgress: (kbId: number) =>
    api.get<GraphBuildProgress>(`/knowledge-graph/${kbId}/build-progress`),
  queryGraph: (data: GraphQueryRequest) =>
    api.post<{ result: GraphQueryResult; debug: GraphQueryDebug }>('/knowledge-graph/query', data),
  exportGraph: (kbId: number) =>
    api.get(`/knowledge-graph/${kbId}/export`, { responseType: 'blob' }),
  clearGraph: (kbId: number) =>
    api.delete(`/knowledge-graph/${kbId}/clear`)
}

export const adminApi = {
  getConfig: () => api.get<SystemConfig>('/admin/config'),
  updateConfig: (data: Partial<SystemConfig>) =>
    api.put<SystemConfig>('/admin/config', data),
  getStats: () => api.get<UsageStats>('/admin/stats'),
  listAllDocuments: (params?: { skip?: number; limit?: number }) =>
    api.get<Document[]>('/admin/documents', { params }),
  listAllConversations: (params?: { skip?: number; limit?: number }) =>
    api.get<Conversation[]>('/admin/conversations', { params }),
}
