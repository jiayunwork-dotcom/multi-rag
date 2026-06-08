import api from './client'
import type {
  KnowledgeBase, Document, ParseTask, Conversation, Message,
  ChatResponse, ChatRequest, SystemConfig, UsageStats, Chunk,
  CompareRequest, CompareChatResponse, VisualizationResponse,
  ABCompareRequest, ABCompareResponse
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
  sendMessage: (data: ChatRequest) =>
    api.post<ChatResponse>('/chat', data),
  sendMessageStream: (data: ChatRequest) => {
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
