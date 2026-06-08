<template>
  <div class="documents-page">
    <div class="page-header">
      <h2>文档管理</h2>
      <div class="header-actions">
        <el-select
          v-model="filterStatus"
          placeholder="解析状态"
          clearable
          size="default"
          style="width: 140px; margin-right: 12px;"
        >
          <el-option label="排队中" value="pending" />
          <el-option label="解析中" value="parsing" />
          <el-option label="已完成" value="completed" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传文档
        </el-button>
      </div>
    </div>

    <el-table
      :data="store.documents"
      v-loading="loading"
      stripe
      style="width: 100%"
    >
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="文档标题" min-width="200">
        <template #default="{ row }">
          <div class="doc-title">
            <el-icon class="doc-icon"><Document /></el-icon>
            <span>{{ row.title }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="file_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="getFileTypeTag(row.file_type)" size="small">
            {{ row.file_type.toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="file_size" label="大小" width="100">
        <template #default="{ row }">
          {{ formatFileSize(row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column prop="page_count" label="页数" width="80" />
      <el-table-column prop="parse_status" label="解析状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusTag(row.parse_status)" size="small">
            {{ getStatusText(row.parse_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_chunks" label="分块数" width="90" />
      <el-table-column prop="avg_chunk_length" label="平均块长" width="100" />
      <el-table-column prop="created_at" label="上传时间" width="170">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewParseStatus(row)">
            <el-icon><View /></el-icon>
            状态
          </el-button>
          <el-button size="small" @click="viewChunks(row)">
            <el-icon><Grid /></el-icon>
            分块
          </el-button>
          <el-button size="small" type="success" @click="reparseDocument(row)">
            <el-icon><Refresh /></el-icon>
            重解析
          </el-button>
          <el-button size="small" type="danger" @click="deleteDocument(row)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showUploadDialog" title="上传文档" width="600px">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="知识库">
          <el-select v-model="uploadForm.knowledge_base_id" placeholder="选择知识库" style="width: 100%">
            <el-option
              v-for="kb in store.knowledgeBases"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="分块策略">
          <el-radio-group v-model="uploadForm.chunk_strategy">
            <el-radio value="token">固定Token</el-radio>
            <el-radio value="paragraph">按段落</el-radio>
            <el-radio value="semantic">语义分割</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="块大小" v-if="uploadForm.chunk_strategy === 'token'">
          <el-select v-model="uploadForm.chunk_size">
            <el-option :label="256" :value="256" />
            <el-option :label="512" :value="512" />
            <el-option :label="1024" :value="1024" />
          </el-select>
        </el-form-item>
        <el-form-item label="重叠Token" v-if="uploadForm.chunk_strategy === 'token'">
          <el-input-number v-model="uploadForm.chunk_overlap" :min="0" :max="200" />
        </el-form-item>
        <el-form-item label="语义阈值" v-if="uploadForm.chunk_strategy === 'semantic'">
          <el-slider
            v-model="uploadForm.semantic_threshold"
            :min="0.3"
            :max="0.7"
            :step="0.1"
            show-input
          />
        </el-form-item>
        <el-form-item label="选择文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :multiple="true"
            :limit="20"
            :file-list="fileList"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".pdf,.doc,.docx,.md,.txt,.png,.jpg,.jpeg,.gif,.bmp"
            drag
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="upload-tip">
                支持 PDF/Word/Markdown/纯文本/图片，最多20个文件
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="uploadDocuments">
          开始上传
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showStatusDialog" title="解析状态" width="600px">
      <div v-if="currentParseTask">
        <el-steps :active="getStepIndex(currentParseTask.stage)" finish-status="success">
          <el-step title="排队中" />
          <el-step title="解析文档" />
          <el-step title="分块处理" />
          <el-step title="向量索引" />
          <el-step title="完成" />
        </el-steps>

        <div class="progress-info">
          <el-progress
            :percentage="currentParseTask.progress"
            :status="currentParseTask.status === 'failed' ? 'exception' : undefined"
          />
          <div class="progress-detail">
            <span>已处理: {{ currentParseTask.processed_chunks }} / {{ currentParseTask.total_chunks }} 块</span>
            <span v-if="currentParseTask.estimated_remaining">
              预计剩余: {{ formatTimeRemaining(currentParseTask.estimated_remaining) }}
            </span>
          </div>
        </div>

        <el-alert
          v-if="currentParseTask.error_message"
          :title="currentParseTask.error_message"
          type="error"
          show-icon
          class="error-alert"
        />
      </div>
    </el-dialog>

    <el-dialog v-model="showChunksDialog" title="分块预览" width="800px">
      <div v-if="currentDocument">
        <el-descriptions :column="3" border size="small" class="chunk-stats">
          <el-descriptions-item label="总分块数">
            {{ currentDocument.total_chunks || 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="平均块长">
            {{ currentDocument.avg_chunk_length || 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="分块策略">
            {{ currentDocument.chunk_strategy || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="chunk-preview">
          <div class="chunk-nav">
            <el-button size="small" :disabled="chunkIndex <= 0" @click="chunkIndex--">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span>第 {{ chunkIndex + 1 }} / {{ currentDocument.total_chunks || 0 }} 块</span>
            <el-button
              size="small"
              :disabled="chunkIndex >= (currentDocument.total_chunks || 1) - 1"
              @click="chunkIndex++"
            >
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
          <div class="chunk-content" v-if="currentChunk">
            <div class="chunk-meta">
              <el-tag size="small">Token: {{ currentChunk.token_count }}</el-tag>
              <el-tag size="small" type="success" v-if="currentChunk.page_number">
                页码: {{ currentChunk.page_number }}
              </el-tag>
              <el-tag size="small" type="info">
                类型: {{ currentChunk.content_type }}
              </el-tag>
            </div>
            <div class="chunk-text">{{ currentChunk.content }}</div>
            <div class="chunk-keywords" v-if="currentChunk.keywords && currentChunk.keywords.length > 0">
              <span class="keywords-label">关键词:</span>
              <el-tag
                v-for="kw in currentChunk.keywords"
                :key="kw"
                size="small"
                type="warning"
                effect="plain"
                class="keyword-tag"
              >
                {{ kw }}
              </el-tag>
            </div>
          </div>
          <div v-else class="chunk-loading">
            <el-icon class="loading-icon"><Loading /></el-icon>
            加载中...
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="showReparseDialog" title="重新解析" width="500px">
      <el-form :model="reparseForm" label-width="100px">
        <el-form-item label="分块策略">
          <el-radio-group v-model="reparseForm.chunk_strategy">
            <el-radio value="token">固定Token</el-radio>
            <el-radio value="paragraph">按段落</el-radio>
            <el-radio value="semantic">语义分割</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="块大小" v-if="reparseForm.chunk_strategy === 'token'">
          <el-select v-model="reparseForm.chunk_size">
            <el-option :label="256" :value="256" />
            <el-option :label="512" :value="512" />
            <el-option :label="1024" :value="1024" />
          </el-select>
        </el-form-item>
        <el-form-item label="重叠Token" v-if="reparseForm.chunk_strategy === 'token'">
          <el-input-number v-model="reparseForm.chunk_overlap" :min="0" :max="200" />
        </el-form-item>
        <el-form-item label="语义阈值" v-if="reparseForm.chunk_strategy === 'semantic'">
          <el-slider
            v-model="reparseForm.semantic_threshold"
            :min="0.3"
            :max="0.7"
            :step="0.1"
            show-input
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReparseDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmReparse">确认重解析</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile, type UploadFiles } from 'element-plus'
import { useAppStore } from '@/stores'
import { documentApi } from '@/api'
import type { Document, ParseTask, Chunk } from '@/types'

const store = useAppStore()
const loading = ref(false)
const filterStatus = ref<string>('')

const showUploadDialog = ref(false)
const uploading = ref(false)
const fileList = ref<UploadFile[]>([])
const uploadForm = ref({
  knowledge_base_id: null as number | null,
  chunk_strategy: 'token',
  chunk_size: 512,
  chunk_overlap: 50,
  semantic_threshold: 0.5
})

const showStatusDialog = ref(false)
const currentParseTask = ref<ParseTask | null>(null)
let statusPollingTimer: number | null = null

const showChunksDialog = ref(false)
const currentDocument = ref<Document | null>(null)
const currentChunk = ref<Chunk | null>(null)
const chunkIndex = ref(0)

const showReparseDialog = ref(false)
const reparseForm = ref({
  chunk_strategy: 'token',
  chunk_size: 512,
  chunk_overlap: 50,
  semantic_threshold: 0.5
})

onMounted(async () => {
  if (store.currentKnowledgeBaseId) {
    await loadDocuments()
  }
})

watch(filterStatus, () => {
  loadDocuments()
})

async function loadDocuments() {
  if (!store.currentKnowledgeBaseId) return
  loading.value = true
  try {
    const params: any = { knowledge_base_id: store.currentKnowledgeBaseId }
    if (filterStatus.value) {
      params.parse_status = filterStatus.value
    }
    await store.loadDocuments(store.currentKnowledgeBaseId)
  } finally {
    loading.value = false
  }
}

function getFileTypeTag(type: string) {
  const map: Record<string, string> = {
    pdf: 'danger',
    doc: 'primary',
    docx: 'primary',
    md: 'success',
    txt: 'info',
    png: 'warning',
    jpg: 'warning',
    jpeg: 'warning',
    gif: 'warning',
    bmp: 'warning'
  }
  return map[type] || 'info'
}

function getStatusTag(status: string) {
  const map: Record<string, string> = {
    pending: 'info',
    parsing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    pending: '排队中',
    parsing: '解析中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function handleFileChange(uploadFile: UploadFile, uploadFiles: UploadFiles) {
  fileList.value = uploadFiles
}

function handleFileRemove(uploadFile: UploadFile, uploadFiles: UploadFiles) {
  fileList.value = uploadFiles
}

async function uploadDocuments() {
  if (!uploadForm.value.knowledge_base_id) {
    ElMessage.warning('请选择知识库')
    return
  }
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }
  if (fileList.value.length > 20) {
    ElMessage.warning('最多上传20个文件')
    return
  }

  uploading.value = true
  try {
    const files = fileList.value.map(f => f.raw!).filter(Boolean)
    await documentApi.upload(
      uploadForm.value.knowledge_base_id!,
      files,
      {
        chunk_strategy: uploadForm.value.chunk_strategy,
        chunk_size: uploadForm.value.chunk_size,
        chunk_overlap: uploadForm.value.chunk_overlap,
        semantic_threshold: uploadForm.value.semantic_threshold
      }
    )
    ElMessage.success('上传成功，开始解析...')
    showUploadDialog.value = false
    fileList.value = []
    await loadDocuments()
  } catch (e) {
    ElMessage.error('上传失败')
    console.error(e)
  } finally {
    uploading.value = false
  }
}

async function viewParseStatus(doc: Document) {
  showStatusDialog.value = true
  currentParseTask.value = null
  await pollParseStatus(doc.id)
}

async function pollParseStatus(docId: number) {
  if (statusPollingTimer) {
    clearInterval(statusPollingTimer)
  }

  const fetchStatus = async () => {
    try {
      const res = await documentApi.getParseStatus(docId)
      currentParseTask.value = res.data
      if (res.data.status === 'completed' || res.data.status === 'failed') {
        if (statusPollingTimer) {
          clearInterval(statusPollingTimer)
          statusPollingTimer = null
        }
        await loadDocuments()
      }
    } catch (e) {
      console.error('获取解析状态失败:', e)
    }
  }

  await fetchStatus()
  statusPollingTimer = window.setInterval(fetchStatus, 2000)
}

function getStepIndex(stage?: string) {
  const stages = ['pending', 'parsing', 'chunking', 'indexing', 'completed']
  return stages.indexOf(stage || 'pending')
}

function formatTimeRemaining(seconds: number) {
  if (seconds < 60) return `${seconds}秒`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}分${secs}秒`
}

async function viewChunks(doc: Document) {
  currentDocument.value = doc
  chunkIndex.value = 0
  showChunksDialog.value = true
  await loadChunk()
}

async function loadChunk() {
  if (!currentDocument.value) return
  try {
    const res = await documentApi.getChunk(currentDocument.value.id, chunkIndex.value)
    currentChunk.value = res.data
  } catch (e) {
    currentChunk.value = null
  }
}

watch(chunkIndex, () => {
  loadChunk()
})

function reparseDocument(doc: Document) {
  currentDocument.value = doc
  reparseForm.value = {
    chunk_strategy: doc.chunk_strategy || 'token',
    chunk_size: doc.chunk_size || 512,
    chunk_overlap: 50,
    semantic_threshold: 0.5
  }
  showReparseDialog.value = true
}

async function confirmReparse() {
  if (!currentDocument.value) return
  try {
    await documentApi.reparse(currentDocument.value.id, {
      chunk_strategy: reparseForm.value.chunk_strategy,
      chunk_size: reparseForm.value.chunk_size,
      chunk_overlap: reparseForm.value.chunk_overlap,
      semantic_threshold: reparseForm.value.semantic_threshold
    })
    ElMessage.success('重新解析任务已启动')
    showReparseDialog.value = false
    await loadDocuments()
  } catch (e) {
    ElMessage.error('重新解析失败')
  }
}

async function deleteDocument(doc: Document) {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${doc.title}" 吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning' }
    )
    await documentApi.delete(doc.id)
    ElMessage.success('删除成功')
    await loadDocuments()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}
</script>

<style lang="scss" scoped>
.documents-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  h2 {
    margin: 0;
    color: #303133;
  }
}

.doc-title {
  display: flex;
  align-items: center;
  gap: 8px;

  .doc-icon {
    color: #409eff;
  }
}

.progress-info {
  margin-top: 24px;

  .progress-detail {
    display: flex;
    justify-content: space-between;
    margin-top: 12px;
    color: #606266;
    font-size: 14px;
  }
}

.error-alert {
  margin-top: 16px;
}

.upload-icon {
  font-size: 64px;
  color: #409eff;
  margin-bottom: 16px;
}

.upload-text {
  color: #606266;
  margin-bottom: 8px;

  em {
    color: #409eff;
    font-style: normal;
  }
}

.upload-tip {
  color: #909399;
  font-size: 12px;
}

.chunk-stats {
  margin-bottom: 16px;
}

.chunk-preview {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;

  .chunk-nav {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #e4e7ed;
  }

  .chunk-meta {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .chunk-text {
    background: white;
    padding: 16px;
    border-radius: 6px;
    line-height: 1.8;
    color: #303133;
    min-height: 150px;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .chunk-keywords {
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;

    .keywords-label {
      color: #606266;
      font-size: 13px;
    }

    .keyword-tag {
      margin-right: 4px;
    }
  }

  .chunk-loading {
    text-align: center;
    padding: 40px;
    color: #909399;

    .loading-icon {
      font-size: 32px;
      margin-bottom: 8px;
      animation: spin 1s linear infinite;
    }
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
