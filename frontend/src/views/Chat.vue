<template>
  <div class="chat-container">
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="store.messages.length === 0" class="empty-state">
        <el-icon class="empty-icon"><ChatDotRound /></el-icon>
        <h3>开始对话</h3>
        <p>请上传文档并选择知识库，然后向我提问</p>
      </div>
      <div
        v-for="msg in store.messages"
        :key="msg.id"
        class="message-item"
        :class="{ 'message-user': msg.role === 'user', 'message-assistant': msg.role === 'assistant' }"
      >
        <div class="message-avatar">
          <el-icon v-if="msg.role === 'user'"><User /></el-icon>
          <el-icon v-else><Service /></el-icon>
        </div>
        <div class="message-content">
          <div class="message-bubble" v-if="msg.role === 'user'">
            <div class="msg-meta" v-if="msg.is_compare">
              <el-tag size="small" type="warning">
                <el-icon><Scale /></el-icon>
                对比模式
              </el-tag>
              <span class="kb-list">
                <el-tag
                  v-for="kbId in msg.compare_kb_ids"
                  :key="kbId"
                  size="small"
                  type="info"
                  class="kb-tag"
                >
                  {{ getKbName(kbId) }}
                </el-tag>
              </span>
            </div>
            {{ msg.content }}
          </div>
          <div class="message-bubble assistant-bubble" v-else>
            <div v-if="msg.is_compare && msg.compare_results" class="compare-results">
              <div class="compare-header">
                <el-tag type="warning" size="small">
                  <el-icon><Scale /></el-icon>
                  多知识库对比分析
                </el-tag>
              </div>

              <el-tabs v-model="activeCompareTab">
                <el-tab-pane label="对比分析" name="analysis">
                  <div class="answer-content" v-html="formatMessageContent(msg.content)"></div>

                  <div v-if="msg.compare_results.analysis?.viewpoints?.length" class="viewpoints-section">
                    <h4>观点来源追踪</h4>
                    <div
                      v-for="(vp, idx) in msg.compare_results.analysis.viewpoints"
                      :key="idx"
                      class="viewpoint-item"
                    >
                      <el-tag size="small" :type="getKbTagType(vp.knowledge_base_id)">
                        {{ vp.knowledge_base_name }}
                      </el-tag>
                      <span class="viewpoint-doc">
                        {{ vp.document_title }}
                        <span v-if="vp.page_number">(p.{{ vp.page_number }})</span>
                      </span>
                    </div>
                  </div>
                </el-tab-pane>

                <el-tab-pane
                  v-for="kb in msg.compare_results.kb_results"
                  :key="kb.knowledge_base_id"
                  :label="`${kb.knowledge_base_name}检索结果`"
                  :name="`kb-${kb.knowledge_base_id}`"
                >
                  <div class="kb-retrieval-section">
                    <el-table :data="kb.retrieval_results" size="small">
                      <el-table-column prop="chunk_index" label="块索引" width="80" />
                      <el-table-column prop="document_title" label="文档" width="150" />
                      <el-table-column prop="content" label="内容" show-overflow-tooltip />
                      <el-table-column label="得分" width="200">
                        <template #default="{ row }">
                          <div class="score-row">
                            <span class="score-item">
                              语义: {{ (row.semantic_score || 0).toFixed(3) }}
                            </span>
                            <span class="score-item">
                              重排: {{ (row.rerank_score || 0).toFixed(3) }}
                            </span>
                          </div>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </el-tab-pane>
              </el-tabs>
            </div>

            <div v-else class="message-text" v-html="formatMessageContent(msg.content)"></div>

            <div v-if="msg.citations && msg.citations.length > 0" class="citations-section">
              <div class="citations-title">引用来源:</div>
              <div
                v-for="cite in msg.citations"
                :key="cite.index"
                class="citation-item"
                @click="showCitationDetail(cite)"
              >
                <span class="cite-index">[{{ cite.index }}]</span>
                <span v-if="cite.kb_name" class="cite-kb">{{ cite.kb_name }}</span>
                <span class="cite-doc">{{ cite.document_title }}</span>
                <span class="cite-page" v-if="cite.page_number">p.{{ cite.page_number }}</span>
              </div>
            </div>

            <div v-if="msg.evaluation" class="evaluation-section">
              <el-tooltip placement="top" :content="`Faithfulness: ${(msg.evaluation.faithfulness * 100).toFixed(1)}%\n${msg.evaluation.faithfulness_reason || ''}`">
                <el-tag size="small" :type="getMetricColor(msg.evaluation.faithfulness)" class="metric-tag">
                  <el-icon><Check /></el-icon>
                  {{ (msg.evaluation.faithfulness * 100).toFixed(0) }}%
                </el-tag>
              </el-tooltip>
              <el-tooltip placement="top" :content="`Answer Relevancy: ${msg.evaluation.answer_relevancy.toFixed(2)}\n${msg.evaluation.answer_relevancy_reason || ''}`">
                <el-tag size="small" :type="getMetricColor(msg.evaluation.answer_relevancy)" class="metric-tag">
                  <el-icon><Star /></el-icon>
                  {{ msg.evaluation.answer_relevancy.toFixed(2) }}
                </el-tag>
              </el-tooltip>
              <el-tooltip placement="top" :content="`Context Precision: ${msg.evaluation.context_precision.toFixed(2)}\n${msg.evaluation.context_precision_reason || ''}`">
                <el-tag size="small" :type="getMetricColor(msg.evaluation.context_precision)" class="metric-tag">
                  <el-icon><TrendCharts /></el-icon>
                  {{ msg.evaluation.context_precision.toFixed(2) }}
                </el-tag>
              </el-tooltip>
              <el-button size="small" text type="primary" @click="showDebugPanel(msg)">
                调试信息
              </el-button>
              <el-button
                v-if="!msg.is_compare"
                size="small"
                text
                type="success"
                @click="loadVisualization(msg)"
              >
                <el-icon><DataAnalysis /></el-icon>
                可视化
              </el-button>
            </div>
          </div>
          <div class="message-time">{{ formatTime(msg.created_at) }}</div>
        </div>
      </div>
      <div v-if="isTyping" class="message-item message-assistant">
        <div class="message-avatar">
          <el-icon><Service /></el-icon>
        </div>
        <div class="message-content">
          <div class="message-bubble assistant-bubble">
            <div class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input-area">
      <div class="input-options">
        <el-tooltip content="流式输出">
          <el-checkbox v-model="streamEnabled">
            <el-icon><VideoPlay /></el-icon>
          </el-checkbox>
        </el-tooltip>
        <el-select v-model="topK" size="small" placeholder="Top-K" style="width: 100px;">
          <el-option :label="5" :value="5" />
          <el-option :label="10" :value="10" />
          <el-option :label="20" :value="20" />
        </el-select>

        <el-divider direction="vertical" />

        <el-tooltip content="对比模式">
          <el-checkbox v-model="compareModeEnabled">
            <el-icon><Scale /></el-icon>
            <span>对比模式</span>
          </el-checkbox>
        </el-tooltip>

        <el-select
          v-if="compareModeEnabled"
          v-model="selectedCompareKbIds"
          multiple
          size="small"
          placeholder="选择2-3个知识库"
          style="min-width: 200px; max-width: 350px;"
        >
          <el-option
            v-for="kb in store.knowledgeBases"
            :key="kb.id"
            :label="kb.name"
            :value="kb.id"
          />
        </el-select>

        <el-tooltip content="A/B策略对比">
          <el-button size="small" :disabled="!store.currentKnowledgeBaseId" @click="showABCompare = true">
            <el-icon><Histogram /></el-icon>
            A/B对比
          </el-button>
        </el-tooltip>
      </div>

      <el-input
        v-model="question"
        type="textarea"
        :rows="2"
        :placeholder="compareModeEnabled ? '请输入对比问题（将从选中的多个知识库检索并对比分析）...' : '请输入您的问题...'"
        @keydown.enter.ctrl="sendMessage"
        resize="none"
      />
      <div class="input-actions">
        <span class="hint">Ctrl + Enter 发送</span>
        <span v-if="compareModeEnabled" class="mode-hint">
          <el-tag size="small" type="warning">对比模式</el-tag>
          已选择 {{ selectedCompareKbIds.length }}/3 个知识库
        </span>
        <el-button type="primary" :loading="isSending" @click="sendMessage">
          <el-icon><Promotion /></el-icon>
          {{ compareModeEnabled ? '发送对比' : '发送' }}
        </el-button>
      </div>
    </div>

    <el-dialog v-model="debugPanelVisible" title="检索调试信息" width="900px">
      <el-tabs v-if="currentDebugMsg">
        <el-tab-pane label="语义检索" name="semantic">
          <el-table :data="currentDebugMsg.retrieval_debug?.semantic_retrieval || []" size="small">
            <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
            <el-table-column prop="document_title" label="文档" width="150" />
            <el-table-column prop="content" label="内容" show-overflow-tooltip />
            <el-table-column prop="score" label="语义得分" width="100">
              <template #default="{ row }">
                {{ row.score?.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="BM25检索" name="bm25">
          <el-table :data="currentDebugMsg.retrieval_debug?.bm25_retrieval || []" size="small">
            <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
            <el-table-column prop="document_title" label="文档" width="150" />
            <el-table-column prop="content" label="内容" show-overflow-tooltip />
            <el-table-column prop="score" label="BM25得分" width="100">
              <template #default="{ row }">
                {{ row.score?.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="RRF融合" name="rrf">
          <el-table :data="currentDebugMsg.retrieval_debug?.rrf_fusion || []" size="small">
            <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
            <el-table-column prop="document_title" label="文档" width="150" />
            <el-table-column prop="score" label="RRF得分" width="100">
              <template #default="{ row }">
                {{ row.score?.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="重排序" name="rerank">
          <el-table :data="currentDebugMsg.retrieval_debug?.reranked || []" size="small">
            <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
            <el-table-column prop="document_title" label="文档" width="150" />
            <el-table-column prop="content" label="内容" show-overflow-tooltip />
            <el-table-column prop="score" label="重排得分" width="100">
              <template #default="{ row }">
                {{ row.score?.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="可视化" name="visualization" v-if="visualizationData">
          <RetrievalVisualization :data="visualizationData" />
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <el-dialog v-model="showABCompare" title="检索策略A/B对比" width="1000px" :close-on-click-modal="false">
      <ABComparePanel
        :knowledge-base-id="store.currentKnowledgeBaseId || 0"
        :conversation-id="store.currentConversationId || undefined"
        @cancel="showABCompare = false"
        @result="handleABCompareResult"
      />
    </el-dialog>

    <el-dialog v-model="citationDialogVisible" title="引用详情" width="700px">
      <div v-if="currentCitation">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="知识库" v-if="currentCitation.kb_name">
            {{ currentCitation.kb_name }}
          </el-descriptions-item>
          <el-descriptions-item label="文档">
            {{ currentCitation.document_title }}
          </el-descriptions-item>
          <el-descriptions-item label="页码" v-if="currentCitation.page_number">
            {{ currentCitation.page_number }}
          </el-descriptions-item>
          <el-descriptions-item label="块索引">
            {{ currentCitation.chunk_index }}
          </el-descriptions-item>
          <el-descriptions-item label="语义得分" v-if="currentCitation.semantic_score">
            {{ currentCitation.semantic_score.toFixed(4) }}
          </el-descriptions-item>
          <el-descriptions-item label="BM25得分" v-if="currentCitation.bm25_score">
            {{ currentCitation.bm25_score.toFixed(4) }}
          </el-descriptions-item>
          <el-descriptions-item label="重排得分" v-if="currentCitation.rerank_score">
            {{ currentCitation.rerank_score.toFixed(4) }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="citation-content">
          <h4>原文内容:</h4>
          <p>{{ currentCitation.content }}</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores'
import { chatApi } from '@/api'
import type { Message, Citation, KnowledgeBaseRetrievalResult, VisualizationData, CompareChatResponse } from '@/types'
import RetrievalVisualization from '@/components/RetrievalVisualization.vue'
import ABComparePanel from '@/components/ABComparePanel.vue'

const store = useAppStore()
const messagesContainer = ref<HTMLElement | null>(null)
const question = ref('')
const isSending = ref(false)
const isTyping = ref(false)
const streamEnabled = ref(true)
const topK = ref(10)
const debugPanelVisible = ref(false)
const citationDialogVisible = ref(false)
const currentDebugMsg = ref<Message | null>(null)
const currentCitation = ref<Citation | null>(null)
const showABCompare = ref(false)
const visualizationData = ref<VisualizationData | null>(null)
const activeCompareTab = ref('analysis')

const compareModeEnabled = ref(false)
const selectedCompareKbIds = ref<number[]>([])

const kbTagColors = ['#5470c6', '#91cc75', '#fac858']

function getKbName(kbId: number): string {
  const kb = store.knowledgeBases.find(k => k.id === kbId)
  return kb?.name || `知识库${kbId}`
}

function getKbTagType(kbId: number): string {
  const idx = selectedCompareKbIds.value.indexOf(kbId)
  const types = ['', 'success', 'warning', 'danger', 'info']
  return types[(idx + 1) % types.length] || ''
}

watch(() => store.messages, () => {
  nextTick(() => {
    scrollToBottom()
  })
}, { deep: true })

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function formatTime(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatMessageContent(content: string) {
  return content.replace(/\[(\d+)\](?:\[([^\]]+)\])?/g, '<span class="citation-link" data-index="$1">[$1]$2</span>')
}

function getMetricColor(value: number) {
  if (value >= 0.8) return 'success'
  if (value >= 0.5) return 'warning'
  return 'danger'
}

function showDebugPanel(msg: Message) {
  currentDebugMsg.value = msg
  debugPanelVisible.value = true
}

function showCitationDetail(cite: Citation) {
  currentCitation.value = cite
  citationDialogVisible.value = true
}

async function loadVisualization(msg: Message) {
  if (!store.currentKnowledgeBaseId) return

  try {
    const userQuestion = getQuestionForMessage(msg)
    if (!userQuestion) return

    const res = await chatApi.getVisualization({
      question: userQuestion,
      knowledge_base_id: store.currentKnowledgeBaseId,
      top_k: topK.value
    })

    visualizationData.value = res.data.visualization
    currentDebugMsg.value = msg
    debugPanelVisible.value = true
  } catch (e) {
    ElMessage.error('加载可视化数据失败')
    console.error(e)
  }
}

function getQuestionForMessage(msg: Message): string | null {
  const msgIndex = store.messages.findIndex(m => m.id === msg.id)
  if (msgIndex > 0) {
    const prevMsg = store.messages[msgIndex - 1]
    if (prevMsg.role === 'user') {
      return prevMsg.content
    }
  }
  return null
}

function handleABCompareResult(result: any) {
  showABCompare.value = false
  ElMessage.success('A/B对比完成')
}

async function sendMessage() {
  if (!question.value.trim()) return

  if (compareModeEnabled.value) {
    if (selectedCompareKbIds.value.length < 2 || selectedCompareKbIds.value.length > 3) {
      ElMessage.warning('对比模式需要选择2-3个知识库')
      return
    }
    await sendCompareMessage()
  } else {
    if (!store.currentKnowledgeBaseId) {
      ElMessage.warning('请先选择知识库')
      return
    }
    await sendNormalMessage()
  }
}

async function sendCompareMessage() {
  const userQuestion = question.value.trim()
  question.value = ''
  isSending.value = true

  const userMsg: any = {
    id: Date.now(),
    conversation_id: store.currentConversationId || 0,
    role: 'user',
    content: userQuestion,
    created_at: new Date().toISOString(),
    is_compare: true,
    compare_kb_ids: [...selectedCompareKbIds.value]
  }
  store.addMessage(userMsg)

  try {
    isTyping.value = true

    const res = await chatApi.sendCompareMessage({
      question: userQuestion,
      knowledge_base_ids: selectedCompareKbIds.value,
      conversation_id: store.currentConversationId || undefined,
      top_k: topK.value,
      stream: false
    })

    const compareData = res.data as CompareChatResponse

    const assistantMsg: any = {
      id: Date.now() + 1,
      conversation_id: compareData.conversation_id,
      role: 'assistant',
      content: compareData.answer,
      citations: compareData.citations,
      retrieval_debug: {},
      evaluation: compareData.evaluation,
      created_at: new Date().toISOString(),
      is_compare: true,
      compare_results: {
        kb_results: compareData.kb_results,
        analysis: compareData.analysis
      }
    }
    store.addMessage(assistantMsg)

    if (!store.currentConversationId) {
      store.currentConversationId = compareData.conversation_id
      await store.loadConversations()
    }
  } catch (e) {
    ElMessage.error('对比问答失败')
    console.error(e)
  } finally {
    isSending.value = false
    isTyping.value = false
  }
}

async function sendNormalMessage() {
  const userQuestion = question.value.trim()
  question.value = ''
  isSending.value = true

  const userMsg: Message = {
    id: Date.now(),
    conversation_id: store.currentConversationId || 0,
    role: 'user',
    content: userQuestion,
    created_at: new Date().toISOString()
  }
  store.addMessage(userMsg)

  if (!store.currentConversationId) {
    try {
      const convRes = await chatApi.createConversation({
        knowledge_base_id: store.currentKnowledgeBaseId
      })
      store.conversations.unshift(convRes.data)
      store.currentConversationId = convRes.data.id
      await store.loadConversations()
    } catch (e) {
      ElMessage.error('创建会话失败')
      isSending.value = false
      return
    }
  }

  try {
    isTyping.value = true

    if (streamEnabled.value) {
      await sendStreamMessage(userQuestion)
    } else {
      await sendNormalApiMessage(userQuestion)
    }
  } catch (e) {
    ElMessage.error('发送消息失败')
    console.error(e)
  } finally {
    isSending.value = false
    isTyping.value = false
  }
}

async function sendNormalApiMessage(questionText: string) {
  const res = await chatApi.sendMessage({
    question: questionText,
    conversation_id: store.currentConversationId || undefined,
    knowledge_base_id: store.currentKnowledgeBaseId || undefined,
    top_k: topK.value,
    stream: false
  })

  const assistantMsg: Message = {
    id: Date.now() + 1,
    conversation_id: store.currentConversationId || 0,
    role: 'assistant',
    content: res.data.answer,
    citations: res.data.citations,
    retrieval_debug: res.data.retrieval_debug,
    evaluation: res.data.evaluation,
    created_at: new Date().toISOString()
  }
  store.addMessage(assistantMsg)
  await store.loadConversations()
}

async function sendStreamMessage(questionText: string) {
  const response = await chatApi.sendMessageStream({
    question: questionText,
    conversation_id: store.currentConversationId || undefined,
    knowledge_base_id: store.currentKnowledgeBaseId || undefined,
    top_k: topK.value,
    stream: true
  })

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  let fullAnswer = ''
  let buffer = ''
  let citations: Citation[] = []
  let evaluation: any = null
  let retrievalDebug: any = null

  const assistantMsg: Message = {
    id: Date.now() + 1,
    conversation_id: store.currentConversationId || 0,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString()
  }
  store.addMessage(assistantMsg)

  if (reader) {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') continue

          try {
            const parsed = JSON.parse(data)
            if (parsed.type === 'content') {
              fullAnswer += parsed.content
              store.updateLastMessage({ content: fullAnswer })
            } else if (parsed.type === 'citations') {
              citations = parsed.citations
              store.updateLastMessage({ citations })
            } else if (parsed.type === 'evaluation') {
              evaluation = parsed.evaluation
              store.updateLastMessage({ evaluation })
            } else if (parsed.type === 'debug') {
              retrievalDebug = parsed.debug
              store.updateLastMessage({ retrieval_debug: retrievalDebug })
            }
          } catch (e) {
            console.error('Parse SSE error:', e)
          }
        }
      }
    }
  }

  await store.loadConversations()
}
</script>

<style lang="scss" scoped>
.chat-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #909399;

  .empty-icon {
    font-size: 64px;
    margin-bottom: 16px;
  }

  h3 {
    margin: 0 0 8px 0;
    color: #606266;
  }
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;

  &.message-user {
    flex-direction: row-reverse;

    .message-content {
      align-items: flex-end;
    }

    .message-bubble {
      background: #409eff;
      color: white;
    }
  }
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.message-user .message-avatar {
  background: #409eff;
  color: white;
}

.message-assistant .message-avatar {
  background: #67c23a;
  color: white;
}

.message-content {
  display: flex;
  flex-direction: column;
  max-width: 75%;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  word-wrap: break-word;
}

.assistant-bubble {
  background: white;
  border: 1px solid #e4e7ed;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;

  .kb-list {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .kb-tag {
    font-size: 11px;
  }
}

.message-text {
  :deep(.citation-link) {
    color: #409eff;
    cursor: pointer;
    text-decoration: underline;
  }
}

.answer-content {
  line-height: 1.8;
  color: #303133;

  :deep(.citation-link) {
    color: #409eff;
    cursor: pointer;
  }

  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 13px;

    th, td {
      border: 1px solid #e4e7ed;
      padding: 8px 12px;
      text-align: left;
    }

    th {
      background: #f5f7fa;
      font-weight: 600;
    }
  }
}

.compare-results {
  .compare-header {
    margin-bottom: 12px;
  }
}

.compare-results :deep(.el-tabs__content) {
  padding-top: 12px;
}

.viewpoints-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;

  h4 {
    margin: 0 0 12px 0;
    color: #606266;
    font-size: 14px;
  }
}

.viewpoint-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 13px;

  .viewpoint-doc {
    color: #606266;
  }
}

.kb-retrieval-section {
  .score-row {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 11px;

    .score-item {
      color: #606266;
    }
  }
}

.message-time {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 4px;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;

  span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #c0c4cc;
    animation: typing 1.4s infinite;

    &:nth-child(2) {
      animation-delay: 0.2s;
    }

    &:nth-child(3) {
      animation-delay: 0.4s;
    }
  }
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.6;
  }
  30% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

.citations-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;

  .citations-title {
    font-weight: 600;
    color: #606266;
    margin-bottom: 8px;
    font-size: 13px;
  }

  .citation-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    background: #f5f7fa;
    border-radius: 6px;
    margin-bottom: 4px;
    cursor: pointer;
    font-size: 13px;
    transition: background 0.2s;

    &:hover {
      background: #ecf5ff;
    }

    .cite-index {
      color: #409eff;
      font-weight: 600;
    }

    .cite-kb {
      color: #67c23a;
      font-size: 12px;
      padding: 0 4px;
      background: #f0f9eb;
      border-radius: 3px;
    }

    .cite-doc {
      flex: 1;
      color: #606266;
    }

    .cite-page {
      color: #909399;
      font-size: 12px;
    }
  }
}

.evaluation-section {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;

  .metric-tag {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.chat-input-area {
  padding: 16px 20px;
  background: white;
  border-top: 1px solid #e4e7ed;

  .input-options {
    display: flex;
    gap: 12px;
    margin-bottom: 8px;
    align-items: center;
    flex-wrap: wrap;
  }

  .input-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;

    .hint {
      color: #c0c4cc;
      font-size: 12px;
    }

    .mode-hint {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #606266;
      font-size: 12px;
    }
  }
}

.citation-content {
  margin-top: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;

  h4 {
    margin: 0 0 8px 0;
    color: #606266;
  }

  p {
    margin: 0;
    line-height: 1.8;
    color: #303133;
  }
}
</style>