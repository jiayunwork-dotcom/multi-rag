<template>
  <div class="kb-page">
    <div class="page-header">
      <h2>知识库管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        新建知识库
      </el-button>
    </div>

    <el-row :gutter="20" class="kb-grid">
      <el-col :span="8" v-for="kb in store.knowledgeBases" :key="kb.id">
        <el-card class="kb-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <div class="kb-title">
                <el-icon class="kb-icon"><FolderOpened /></el-icon>
                <span>{{ kb.name }}</span>
              </div>
              <el-dropdown @command="(cmd) => handleMenuCommand(cmd, kb)">
                <el-button size="small" text>
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename">
                      <el-icon><Edit /></el-icon>重命名
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <el-icon><Delete /></el-icon>删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
          <div class="kb-content">
            <p class="kb-desc" v-if="kb.description">{{ kb.description }}</p>
            <p class="kb-desc empty" v-else>暂无描述</p>
            <div class="kb-stats">
              <div class="stat-item">
                <el-icon><Document /></el-icon>
                <span>{{ kb.document_count }} 个文档</span>
              </div>
              <div class="stat-item">
                <el-icon><Clock /></el-icon>
                <span>{{ formatDate(kb.created_at) }}</span>
              </div>
            </div>
          </div>
          <div class="kb-actions">
            <el-button
              size="small"
              @click="viewDetail(kb)"
            >
              <el-icon><View /></el-icon>
              详情
            </el-button>
            <el-button
              type="primary"
              size="small"
              @click="selectKb(kb)"
            >
              {{ kb.id === store.currentKnowledgeBaseId ? '当前使用' : '选择使用' }}
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8" v-if="store.knowledgeBases.length === 0">
        <div class="empty-state">
          <el-icon class="empty-icon"><FolderOpened /></el-icon>
          <p>还没有知识库</p>
          <el-button type="primary" @click="showCreateDialog = true">
            创建第一个知识库
          </el-button>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="showCreateDialog" title="新建知识库" width="500px">
      <el-form :model="createForm" label-width="80px" ref="createFormRef">
        <el-form-item label="名称" prop="name" :rules="[{ required: true, message: '请输入知识库名称', trigger: 'blur' }]">
          <el-input v-model="createForm.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入知识库描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createKnowledgeBase">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRenameDialog" title="重命名知识库" width="500px">
      <el-form :model="renameForm" label-width="80px" ref="renameFormRef">
        <el-form-item label="名称" prop="name" :rules="[{ required: true, message: '请输入知识库名称', trigger: 'blur' }]">
          <el-input v-model="renameForm.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="renameForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入知识库描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="renameKnowledgeBase">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { useAppStore } from '@/stores'
import { knowledgeBaseApi } from '@/api'
import type { KnowledgeBase } from '@/types'

const router = useRouter()

const store = useAppStore()

const showCreateDialog = ref(false)
const showRenameDialog = ref(false)
const currentKb = ref<KnowledgeBase | null>(null)

const createForm = reactive({
  name: '',
  description: ''
})

const renameForm = reactive({
  name: '',
  description: ''
})

const createFormRef = ref<FormInstance>()
const renameFormRef = ref<FormInstance>()

function formatDate(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

function handleMenuCommand(cmd: string, kb: KnowledgeBase) {
  if (cmd === 'rename') {
    currentKb.value = kb
    renameForm.name = kb.name
    renameForm.description = kb.description || ''
    showRenameDialog.value = true
  } else if (cmd === 'delete') {
    deleteKnowledgeBase(kb)
  }
}

function selectKb(kb: KnowledgeBase) {
  store.currentKnowledgeBaseId = kb.id
  ElMessage.success(`已切换到知识库: ${kb.name}`)
}

function viewDetail(kb: KnowledgeBase) {
  router.push(`/knowledge-base/${kb.id}`)
}

async function createKnowledgeBase() {
  try {
    await createFormRef?.value?.validate()
    const res = await knowledgeBaseApi.create({
      name: createForm.name,
      description: createForm.description
    })
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    createForm.name = ''
    createForm.description = ''
    await store.loadKnowledgeBases()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

async function renameKnowledgeBase() {
  if (!currentKb.value) return
  try {
    await renameFormRef?.value?.validate()
    await knowledgeBaseApi.update(currentKb.value.id, {
      name: renameForm.name,
      description: renameForm.description
    })
    ElMessage.success('更新成功')
    showRenameDialog.value = false
    await store.loadKnowledgeBases()
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

async function deleteKnowledgeBase(kb: KnowledgeBase) {
  try {
    await ElMessageBox.confirm(
      `确定要删除知识库 "${kb.name}" 吗？该知识库下的所有文档和数据都将被删除，此操作不可恢复。`,
      '删除确认',
      { type: 'warning' }
    )
    await knowledgeBaseApi.delete(kb.id)
    ElMessage.success('删除成功')
    if (store.currentKnowledgeBaseId === kb.id) {
      store.currentKnowledgeBaseId = null
    }
    await store.loadKnowledgeBases()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}
</script>

<style lang="scss" scoped>
.kb-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow-y: auto;
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

.kb-grid {
  flex: 1;
}

.kb-card {
  margin-bottom: 20px;
  transition: transform 0.2s, box-shadow 0.2s;

  &:hover {
    transform: translateY(-4px);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .kb-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    font-size: 16px;

    .kb-icon {
      color: #409eff;
      font-size: 20px;
    }
  }

  .kb-content {
    min-height: 120px;

    .kb-desc {
      color: #606266;
      margin-bottom: 16px;
      line-height: 1.6;
      min-height: 48px;

      &.empty {
        color: #c0c4cc;
        font-style: italic;
      }
    }

    .kb-stats {
      display: flex;
      flex-direction: column;
      gap: 8px;
      color: #909399;
      font-size: 13px;

      .stat-item {
        display: flex;
        align-items: center;
        gap: 6px;
      }
    }
  }

  .kb-actions {
    padding-top: 16px;
    border-top: 1px solid #ebeef5;
    display: flex;
    justify-content: flex-end;
  }
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #909399;
  border: 2px dashed #dcdfe6;
  border-radius: 12px;

  .empty-icon {
    font-size: 64px;
    margin-bottom: 16px;
  }

  p {
    margin-bottom: 16px;
  }
}
</style>
