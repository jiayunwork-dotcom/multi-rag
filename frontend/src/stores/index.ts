import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { KnowledgeBase, Document, Conversation, Message, Citation, RetrievalDebug, EvaluationMetrics, GraphQueryResult, GraphQueryDebug, GraphCitation } from '@/types'
import { knowledgeBaseApi, documentApi, chatApi, adminApi } from '@/api'
import type { SystemConfig, UsageStats } from '@/types'

export const useAppStore = defineStore('app', () => {
  const knowledgeBases = ref<KnowledgeBase[]>([])
  const currentKnowledgeBaseId = ref<number | null>(null)
  const documents = ref<Document[]>([])
  const conversations = ref<Conversation[]>([])
  const currentConversationId = ref<number | null>(null)
  const messages = ref<Message[]>([])
  const systemConfig = ref<SystemConfig | null>(null)
  const usageStats = ref<UsageStats | null>(null)
  const loading = ref(false)

  const currentKnowledgeBase = computed(() =>
    knowledgeBases.value.find(kb => kb.id === currentKnowledgeBaseId.value) || null
  )

  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentConversationId.value) || null
  )

  async function loadKnowledgeBases() {
    try {
      const res = await knowledgeBaseApi.list()
      knowledgeBases.value = res.data
      if (!currentKnowledgeBaseId.value && knowledgeBases.value.length > 0) {
        currentKnowledgeBaseId.value = knowledgeBases.value[0].id
      }
    } catch (e) {
      console.error('加载知识库失败:', e)
    }
  }

  async function loadDocuments(kbId?: number) {
    try {
      const params = kbId ? { knowledge_base_id: kbId } : {}
      const res = await documentApi.list(params)
      documents.value = res.data
    } catch (e) {
      console.error('加载文档失败:', e)
    }
  }

  async function loadConversations() {
    try {
      const res = await chatApi.listConversations()
      conversations.value = res.data
    } catch (e) {
      console.error('加载会话失败:', e)
    }
  }

  async function loadMessages(convId: number) {
    try {
      const res = await chatApi.getConversation(convId)
      messages.value = res.data.messages || []
      currentConversationId.value = convId
    } catch (e) {
      console.error('加载消息失败:', e)
    }
  }

  async function loadSystemConfig() {
    try {
      const res = await adminApi.getConfig()
      systemConfig.value = res.data
    } catch (e) {
      console.error('加载配置失败:', e)
    }
  }

  async function loadUsageStats() {
    try {
      const res = await adminApi.getStats()
      usageStats.value = res.data
    } catch (e) {
      console.error('加载统计数据失败:', e)
    }
  }

  function addMessage(message: Message) {
    messages.value.push(message)
  }

  function updateLastMessage(updates: Partial<Message>) {
    if (messages.value.length > 0) {
      const lastIndex = messages.value.length - 1
      messages.value[lastIndex] = { ...messages.value[lastIndex], ...updates }
    }
  }

  return {
    knowledgeBases,
    currentKnowledgeBaseId,
    documents,
    conversations,
    currentConversationId,
    messages,
    systemConfig,
    usageStats,
    loading,
    currentKnowledgeBase,
    currentConversation,
    loadKnowledgeBases,
    loadDocuments,
    loadConversations,
    loadMessages,
    loadSystemConfig,
    loadUsageStats,
    addMessage,
    updateLastMessage,
  }
})
