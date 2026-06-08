<template>
  <div class="admin-page">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="使用统计" name="stats">
        <div class="stats-section">
          <el-row :gutter="20">
            <el-col :span="6">
              <el-card class="stat-card">
                <div class="stat-icon qa">
                  <el-icon><ChatDotRound /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-value">{{ store.usageStats?.total_qa_count || 0 }}</div>
                  <div class="stat-label">总问答次数</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card">
                <div class="stat-icon time">
                  <el-icon><Timer /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-value">{{ (store.usageStats?.avg_response_time || 0).toFixed(1) }}s</div>
                  <div class="stat-label">平均响应时间</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card">
                <div class="stat-icon hit">
                  <el-icon><Target /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-value">{{ ((store.usageStats?.retrieval_hit_rate || 0) * 100).toFixed(1) }}%</div>
                  <div class="stat-label">检索命中率</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card">
                <div class="stat-icon doc">
                  <el-icon><Document /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-value">{{ store.usageStats?.total_documents || 0 }}</div>
                  <div class="stat-label">总文档数</div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="20" style="margin-top: 20px;">
            <el-col :span="8">
              <el-card class="stat-card">
                <div class="stat-icon kb">
                  <el-icon><FolderOpened /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-value">{{ store.usageStats?.total_knowledge_bases || 0 }}</div>
                  <div class="stat-label">知识库数量</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card class="stat-card">
                <div class="stat-icon chunk">
                  <el-icon><Grid /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-value">{{ store.usageStats?.total_chunks || 0 }}</div>
                  <div class="stat-label">总分块数</div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <div class="refresh-btn">
            <el-button type="primary" @click="refreshStats">
              <el-icon><Refresh /></el-icon>
              刷新数据
            </el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="系统配置" name="config">
        <div class="config-section">
          <el-form :model="configForm" label-width="180px" class="config-form">
            <el-divider content-position="left">LLM 接口配置</el-divider>
            <el-form-item label="API Endpoint">
              <el-input v-model="configForm.llm_endpoint" placeholder="https://api.openai.com/v1" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="configForm.llm_api_key" type="password" show-password placeholder="sk-..." />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="configForm.llm_model" placeholder="gpt-3.5-turbo" />
            </el-form-item>

            <el-divider content-position="left">嵌入模型配置</el-divider>
            <el-form-item label="文本嵌入模型">
              <el-select v-model="configForm.embedding_model" style="width: 100%">
                <el-option label="all-MiniLM-L6-v2 (384维)" value="all-MiniLM-L6-v2" />
                <el-option label="all-mpnet-base-v2 (768维)" value="all-mpnet-base-v2" />
                <el-option label="multi-qa-MiniLM-L6-cos-v1" value="multi-qa-MiniLM-L6-cos-v1" />
              </el-select>
            </el-form-item>
            <el-form-item label="Cross-Encoder模型">
              <el-select v-model="configForm.cross_encoder_model" style="width: 100%">
                <el-option label="cross-encoder/ms-marco-MiniLM-L-6-v2" value="cross-encoder/ms-marco-MiniLM-L-6-v2" />
                <el-option label="cross-encoder/ms-marco-MiniLM-L-12-v2" value="cross-encoder/ms-marco-MiniLM-L-12-v2" />
              </el-select>
            </el-form-item>

            <el-divider content-position="left">分块策略默认值</el-divider>
            <el-form-item label="默认分块策略">
              <el-radio-group v-model="configForm.default_chunk_strategy">
                <el-radio value="token">固定Token</el-radio>
                <el-radio value="paragraph">按段落</el-radio>
                <el-radio value="semantic">语义分割</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="默认块大小(Token)">
              <el-input-number v-model="configForm.default_chunk_size" :min="128" :max="2048" :step="128" />
            </el-form-item>
            <el-form-item label="默认重叠Token">
              <el-input-number v-model="configForm.default_chunk_overlap" :min="0" :max="512" :step="10" />
            </el-form-item>

            <el-divider content-position="left">检索参数</el-divider>
            <el-form-item label="默认Top-K">
              <el-input-number v-model="configForm.retrieval_top_k" :min="1" :max="50" />
            </el-form-item>
            <el-form-item label="重排序Top-N">
              <el-input-number v-model="configForm.rerank_top_n" :min="1" :max="20" />
            </el-form-item>

            <el-divider content-position="left">Prompt模板</el-divider>
            <el-form-item label="系统Prompt">
              <el-input
                v-model="configForm.prompt_template"
                type="textarea"
                :rows="6"
                placeholder="基于以下参考资料回答用户问题... {context} {question}"
              />
              <div class="form-tip">
                可用变量: {context} - 检索到的上下文, {question} - 用户问题
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="savingConfig" @click="saveConfig">
                <el-icon><Check /></el-icon>
                保存配置
              </el-button>
              <el-button @click="loadConfig">
                <el-icon><Refresh /></el-icon>
                重置
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <el-tab-pane label="文档管理" name="documents">
        <div class="admin-docs-section">
          <div class="section-header">
            <h3>所有文档</h3>
            <el-button type="primary" @click="loadAllDocuments">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
          <el-table :data="allDocuments" v-loading="loadingDocs" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="title" label="标题" min-width="200" />
            <el-table-column prop="knowledge_base_id" label="知识库ID" width="100" />
            <el-table-column prop="file_type" label="类型" width="80">
              <template #default="{ row }">
                <el-tag size="small">{{ row.file_type.toUpperCase() }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="parse_status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusTag(row.parse_status)" size="small">
                  {{ getStatusText(row.parse_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="total_chunks" label="分块数" width="80" />
            <el-table-column prop="created_at" label="创建时间" width="160">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="adminDeleteDoc(row)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="对话管理" name="conversations">
        <div class="admin-conv-section">
          <div class="section-header">
            <h3>所有对话</h3>
            <el-button type="primary" @click="loadAllConversations">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
          <el-table :data="allConversations" v-loading="loadingConvs" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="title" label="标题" min-width="200">
              <template #default="{ row }">
                {{ row.title || '新对话' }}
              </template>
            </el-table-column>
            <el-table-column prop="knowledge_base_id" label="知识库ID" width="100" />
            <el-table-column prop="message_count" label="消息数" width="100" />
            <el-table-column prop="created_at" label="创建时间" width="160">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="160">
              <template #default="{ row }">
                {{ row.updated_at ? formatDate(row.updated_at) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="adminDeleteConv(row)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores'
import { adminApi, documentApi, chatApi } from '@/api'
import type { SystemConfig, Document, Conversation } from '@/types'

const store = useAppStore()
const activeTab = ref('stats')
const savingConfig = ref(false)
const loadingDocs = ref(false)
const loadingConvs = ref(false)

const configForm = reactive<Partial<SystemConfig>>({
  llm_endpoint: '',
  llm_api_key: '',
  llm_model: '',
  embedding_model: '',
  cross_encoder_model: '',
  default_chunk_strategy: 'token',
  default_chunk_size: 512,
  default_chunk_overlap: 50,
  retrieval_top_k: 10,
  rerank_top_n: 5,
  prompt_template: ''
})

const allDocuments = ref<Document[]>([])
const allConversations = ref<Conversation[]>([])

onMounted(async () => {
  await Promise.all([
    store.loadUsageStats(),
    loadConfig()
  ])
})

async function refreshStats() {
  await store.loadUsageStats()
  ElMessage.success('数据已刷新')
}

async function loadConfig() {
  try {
    const res = await adminApi.getConfig()
    Object.assign(configForm, res.data)
  } catch (e) {
    ElMessage.error('加载配置失败')
  }
}

async function saveConfig() {
  savingConfig.value = true
  try {
    await adminApi.updateConfig(configForm)
    ElMessage.success('配置保存成功')
    await loadConfig()
  } catch (e) {
    ElMessage.error('保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

async function loadAllDocuments() {
  loadingDocs.value = true
  try {
    const res = await adminApi.listAllDocuments()
    allDocuments.value = res.data
  } catch (e) {
    ElMessage.error('加载文档失败')
  } finally {
    loadingDocs.value = false
  }
}

async function loadAllConversations() {
  loadingConvs.value = true
  try {
    const res = await adminApi.listAllConversations()
    allConversations.value = res.data
  } catch (e) {
    ElMessage.error('加载对话失败')
  } finally {
    loadingConvs.value = false
  }
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

async function adminDeleteDoc(doc: Document) {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${doc.title}" 吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await documentApi.delete(doc.id)
    ElMessage.success('删除成功')
    await loadAllDocuments()
    await store.loadUsageStats()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

async function adminDeleteConv(conv: Conversation) {
  try {
    await ElMessageBox.confirm(
      `确定要删除对话 "${conv.title || '新对话'}" 吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await chatApi.deleteConversation(conv.id)
    ElMessage.success('删除成功')
    await loadAllConversations()
    await store.loadUsageStats()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}
</script>

<style lang="scss" scoped>
.admin-page {
  height: 100%;
  padding: 20px;
  overflow-y: auto;
}

.stats-section {
  .stat-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px;

    .stat-icon {
      width: 60px;
      height: 60px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      color: white;

      &.qa {
        background: linear-gradient(135deg, #409eff, #66b1ff);
      }

      &.time {
        background: linear-gradient(135deg, #67c23a, #85ce61);
      }

      &.hit {
        background: linear-gradient(135deg, #e6a23c, #f0c78a);
      }

      &.doc {
        background: linear-gradient(135deg, #f56c6c, #f89898);
      }

      &.kb {
        background: linear-gradient(135deg, #909399, #b1b3b8);
      }

      &.chunk {
        background: linear-gradient(135deg, #9b59b6, #bb77d4);
      }
    }

    .stat-content {
      .stat-value {
        font-size: 28px;
        font-weight: 700;
        color: #303133;
        line-height: 1.2;
      }

      .stat-label {
        font-size: 13px;
        color: #909399;
        margin-top: 4px;
      }
    }
  }

  .refresh-btn {
    text-align: center;
    margin-top: 24px;
  }
}

.config-section {
  max-width: 900px;
  margin: 0 auto;

  .config-form {
    .form-tip {
      color: #909399;
      font-size: 12px;
      margin-top: 4px;
    }
  }
}

.admin-docs-section,
.admin-conv-section {
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    h3 {
      margin: 0;
      color: #303133;
    }
  }
}
</style>
