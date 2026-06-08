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
            {{ msg.content }}
          </div>
          <div class="message-bubble assistant-bubble" v-else>
            <div class="message-text" v-html="formatMessageContent(msg.content)"></div>
            
            <div v-if="msg.citations && msg.citations.length > 0" class="citations-section">
              <div class="citations-title">引用来源:</div>
              <div
                v-for="cite in msg.citations"
                :key="cite.index"
                class="citation-item"
                @click="showCitationDetail(cite)"
              >
                <span class="cite-index">[{{ cite.index }}]</span>
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
      </div>
      <el-input
        v-model="question"
        type="textarea"
        :rows="2"
        placeholder="请输入您的问题..."
        @keydown.enter.ctrl="sendMessage"
        resize="none"
      />
      <div class="input-actions">
        <span class="hint">Ctrl + Enter 发送</span>
        <el-button type="primary" :loading="isSending" @click="sendMessage">
          <el-icon><Promotion /></el-icon>
          发送
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
            <el-table-column prop="semantic_score" label="语义得分" width="100">
              <template #default="{ row }">
                {{ row.semantic_score?.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="BM25检索" name="bm25">
          <el-table :data="currentDebugMsg.retrieval_debug?.bm25_retrieval || []" size="small">
            <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
            <el-table-column prop="document_title" label="文档" width="150" />
            <el-table-column prop="content" label="内容" show-overflow-tooltip />
            <el-table-column prop="bm25_score" label="BM25得分" width="100">
              <template #default="{ row }">
                {{ row.bm25_score?.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="RRF融合" name="rrf">
          <el-table :data="currentDebugMsg.retrieval_debug?.rrf_fusion || []" size="small">
            <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
            <el-table-column prop="document_title" label="文档" width="150" />
            <el-table-column prop="rrf_score" label="RRF得分" width="100">
              <template #default="{ row }">
                {{ row.rrf_score?.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="重排序" name="rerank">
          <el-table :data="currentDebugMsg.retrieval_debug?.reranked || []" size="small">
            <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
            <el-table-column prop="document_title" label="文档" width="150" />
            <el-table-column prop="content" label="内容" show-overflow-tooltip />
            <el-table-column prop="rerank_score" label="重排得分" width="100">
              <template #default="{ row }">
                {{ row.rerank_score?.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <el-dialog v-model="citationDialogVisible" title="引用详情" width="700px">
      <div v-if="currentCitation">
        <el-descriptions :column="1" border>
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
import { ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores'
import { chatApi } from '@/api'
import type { Message, Citation } from '@/types'

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
  return content.replace(/\[(\d+)\]/g, '<span class="citation-link" data-index="$1">[$1]</span>')
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

async function sendMessage() {
  if (!question.value.trim()) return
  if (!store.currentKnowledgeBaseId) {
    ElMessage.warning('请先选择知识库')
    return
  }

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
      await sendNormalMessage(userQuestion)
    }
  } catch (e) {
    ElMessage.error('发送消息失败')
    console.error(e)
  } finally {
    isSending.value = false
    isTyping.value = false
  }
}

async function sendNormalMessage(questionText: string) {
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
  max-width: 70%;
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

.message-text {
  :deep(.citation-link) {
    color: #409eff;
    cursor: pointer;
    text-decoration: underline;
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
