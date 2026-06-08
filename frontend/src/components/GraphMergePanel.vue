<template>
  <div class="merge-panel">
    <div class="panel-header">
      <h3>合并图谱</h3>
      <div class="header-actions">
        <el-button size="small" @click="showMergeDialog = true" type="primary">
          <el-icon><Promotion /></el-icon>
          选择知识库合并
        </el-button>
      </div>
    </div>

    <div class="merge-content">
      <div v-if="!mergePreview" class="empty-state">
        <div class="empty-icon">🔄</div>
        <p>选择另一个知识库进行合并</p>
        <p class="empty-hint">同名同类型的实体会自动消歧合并</p>
      </div>

      <div v-else class="preview-content">
        <div class="preview-header">
          <div class="preview-info">
            <h4>合并预览</h4>
            <p>
              将 <strong>{{ sourceKnowledgeBase?.name }}</strong> 的图谱合并到
              <strong>{{ currentKnowledgeBase?.name }}</strong>
            </p>
          </div>
          <el-button size="small" text @click="resetMerge">
            重新选择
          </el-button>
        </div>

        <div class="preview-stats">
          <div class="stat-card">
            <div class="stat-label">源知识库</div>
            <div class="stat-value">{{ sourceKnowledgeBase?.name }}</div>
            <div class="stat-meta">
              <span>{{ mergePreview.source_entity_count }} 实体</span>
              <span>{{ mergePreview.source_relation_count }} 关系</span>
            </div>
          </div>
          <div class="stat-arrow">→</div>
          <div class="stat-card">
            <div class="stat-label">目标知识库</div>
            <div class="stat-value">{{ currentKnowledgeBase?.name }}</div>
            <div class="stat-meta">
              <span>{{ mergePreview.target_entity_count }} 实体</span>
              <span>{{ mergePreview.target_relation_count }} 关系</span>
            </div>
          </div>
        </div>

        <div class="preview-summary">
          <div class="summary-item">
            <span class="summary-icon auto">✅</span>
            <span class="summary-text">
              将自动合并 <strong>{{ mergePreview.auto_merged_count }}</strong> 个相似实体
            </span>
          </div>
          <div v-if="mergePreview.pending_count > 0" class="summary-item">
            <span class="summary-icon pending">⚠️</span>
            <span class="summary-text">
              <strong>{{ mergePreview.pending_count }}</strong> 个实体待确认
            </span>
          </div>
        </div>

        <div v-if="mergePreview.pending_count > 0" class="conflicts-section">
          <div class="conflicts-header">
            <h4>待确认冲突 ({{ mergePreview.pending_count }})</h4>
            <span class="conflicts-progress">
              {{ resolvedCount }} / {{ mergePreview.pending_count }} 已处理
            </span>
          </div>
          
          <div class="conflict-list">
            <div
              v-for="(conflict, index) in mergePreview.pending_conflicts"
              :key="index"
              class="conflict-item"
              :class="{ resolved: conflict.action !== undefined }"
            >
              <div class="conflict-entities">
                <div class="entity-card">
                  <div class="entity-header">
                    <el-tag size="small" :type="getEntityTagType(conflict.entity_a.entity_type)">
                      {{ getEntityTypeLabel(conflict.entity_a.entity_type) }}
                    </el-tag>
                    <span class="entity-source">{{ conflict.entity_a.source_kb_name }}</span>
                  </div>
                  <div class="entity-name">{{ conflict.entity_a.name }}</div>
                  <div class="entity-context">{{ conflict.entity_a.context_summary }}</div>
                </div>

                <div class="conflict-info">
                  <div class="conflict-score">
                    相似度: <strong>{{ (conflict.score * 100).toFixed(0) }}%</strong>
                  </div>
                  <div class="conflict-hint">
                    {{ getConflictHint(conflict.score) }}
                  </div>
                </div>

                <div class="entity-card">
                  <div class="entity-header">
                    <el-tag size="small" :type="getEntityTagType(conflict.entity_b.entity_type)">
                      {{ getEntityTypeLabel(conflict.entity_b.entity_type) }}
                    </el-tag>
                    <span class="entity-source">{{ conflict.entity_b.source_kb_name }}</span>
                  </div>
                  <div class="entity-name">{{ conflict.entity_b.name }}</div>
                  <div class="entity-context">{{ conflict.entity_b.context_summary }}</div>
                </div>
              </div>

              <div class="conflict-actions">
                <el-button-group v-if="conflict.action === undefined">
                  <el-button
                    size="small"
                    type="success"
                    @click="setConflictAction(index, 'merge')"
                  >
                    <el-icon><Check /></el-icon>
                    合并为同一实体
                  </el-button>
                  <el-button
                    size="small"
                    type="info"
                    @click="setConflictAction(index, 'keep')"
                  >
                    <el-icon><Close /></el-icon>
                    保留为独立实体
                  </el-button>
                </el-button-group>
                <div v-else class="action-result">
                  <el-tag v-if="conflict.action === 'merge'" type="success" size="small">
                    ✓ 将合并
                  </el-tag>
                  <el-tag v-else type="info" size="small">
                    ✗ 保持独立
                  </el-tag>
                  <el-button size="small" text @click="setConflictAction(index, undefined)">
                    修改
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="merge-actions">
          <el-button @click="resetMerge">取消</el-button>
          <el-button
            type="primary"
            :loading="merging"
            :disabled="!canExecute"
            @click="executeMerge"
          >
            <el-icon><Check /></el-icon>
            {{ mergePreview.pending_count > 0 ? '处理完所有冲突后合并' : '确认合并' }}
          </el-button>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="showMergeDialog"
      title="选择要合并的知识库"
      width="500px"
      :close-on-click-modal="false"
    >
      <div class="select-kb-dialog">
        <div class="kb-list">
          <div
            v-for="kb in availableKnowledgeBases"
            :key="kb.id"
            class="kb-item"
            :class="{ selected: selectedSourceKbId === kb.id }"
            @click="selectedSourceKbId = kb.id"
          >
            <div class="kb-name">{{ kb.name }}</div>
            <div class="kb-stats">
              <span>{{ kb.document_count || 0 }} 文档</span>
            </div>
          </div>
        </div>

        <div v-if="availableKnowledgeBases.length === 0" class="empty-kb">
          没有可合并的知识库
        </div>
      </div>

      <template #footer>
        <el-button @click="showMergeDialog = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!selectedSourceKbId"
          :loading="previewLoading"
          @click="previewMerge"
        >
          预览合并
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { graphApi, knowledgeBaseApi } from '@/api'
import type { KnowledgeBase, GraphMergePreview, GraphMergeResult } from '@/types'

const props = defineProps<{
  knowledgeBaseId: number
  knowledgeBaseName?: string
}>()

const emit = defineEmits<{
  (e: 'merge-complete', result: GraphMergeResult): void
}>()

const showMergeDialog = ref(false)
const selectedSourceKbId = ref<number | null>(null)
const availableKnowledgeBases = ref<KnowledgeBase[]>([])
const allKnowledgeBases = ref<KnowledgeBase[]>([])

const currentKnowledgeBase = ref<KnowledgeBase | null>(null)
const sourceKnowledgeBase = ref<KnowledgeBase | null>(null)

const mergePreview = ref<GraphMergePreview | null>(null)
const previewLoading = ref(false)
const merging = ref(false)

const entityTypes = [
  { value: 'person', label: '人物' },
  { value: 'organization', label: '组织' },
  { value: 'location', label: '地点' },
  { value: 'tech_concept', label: '技术' },
  { value: 'event', label: '事件' }
]

const canExecute = computed(() => {
  if (!mergePreview.value) return false
  if (mergePreview.value.pending_count === 0) return true
  return mergePreview.value.pending_conflicts.every(c => c.action !== undefined)
})

const resolvedCount = computed(() => {
  if (!mergePreview.value) return 0
  return mergePreview.value.pending_conflicts.filter(c => c.action !== undefined).length
})

onMounted(() => {
  loadKnowledgeBases()
})

async function loadKnowledgeBases() {
  try {
    const [allRes, currentRes] = await Promise.all([
      knowledgeBaseApi.list(),
      knowledgeBaseApi.get(props.knowledgeBaseId)
    ])
    
    allKnowledgeBases.value = allRes.data
    currentKnowledgeBase.value = currentRes.data
    filterAvailableKnowledgeBases()
  } catch (e) {
    console.error('Failed to load knowledge bases:', e)
  }
}

function filterAvailableKnowledgeBases() {
  availableKnowledgeBases.value = allKnowledgeBases.value.filter(
    kb => kb.id !== props.knowledgeBaseId
  )
}

async function previewMerge() {
  if (!selectedSourceKbId.value) return

  previewLoading.value = true
  try {
    const res = await graphApi.previewMerge({
      target_kb_id: props.knowledgeBaseId,
      source_kb_id: selectedSourceKbId.value,
      resolutions: []
    })

    mergePreview.value = res.data
    sourceKnowledgeBase.value = allKnowledgeBases.value.find(
      kb => kb.id === selectedSourceKbId.value
    ) || null
    showMergeDialog.value = false
  } catch (e) {
    ElMessage.error('获取合并预览失败')
  } finally {
    previewLoading.value = false
  }
}

function setConflictAction(index: number, action: 'merge' | 'keep' | undefined) {
  if (!mergePreview.value) return
  mergePreview.value.pending_conflicts[index].action = action
}

function getConflictHint(score: number) {
  if (score >= 0.75) return '相似度较高，建议合并'
  if (score >= 0.65) return '相似度中等，请谨慎判断'
  return '相似度较低，建议保持独立'
}

async function executeMerge() {
  if (!mergePreview.value || !canExecute.value) return

  try {
    await ElMessageBox.confirm(
      '确认执行合并操作？合并后会自动生成新版本快照。',
      '确认合并',
      {
        confirmButtonText: '确认合并',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    merging.value = true
    const resolutions = mergePreview.value.pending_conflicts
      .filter(c => c.action !== undefined)
      .map(c => ({
        source_entity_id: c.entity_a.entity_id,
        target_entity_id: c.entity_b.entity_id,
        action: c.action === 'merge' ? 'merge' : 'keep_separate' as 'merge' | 'keep_separate'
      }))

    const res = await graphApi.executeMerge({
      target_kb_id: props.knowledgeBaseId,
      source_kb_id: selectedSourceKbId.value!,
      resolutions: resolutions
    })

    ElMessage.success('合并成功！已自动创建新版本')
    emit('merge-complete', res.data)
    resetMerge()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('合并失败')
    }
  } finally {
    merging.value = false
  }
}

function resetMerge() {
  mergePreview.value = null
  selectedSourceKbId.value = null
  sourceKnowledgeBase.value = null
}

function getEntityTypeLabel(type: string) {
  const t = entityTypes.find(t => t.value === type)
  return t?.label || type
}

function getEntityTagType(type: string) {
  const map: Record<string, string> = {
    person: 'danger',
    organization: 'success',
    location: 'info',
    tech_concept: 'warning',
    event: ''
  }
  return map[type] || ''
}
</script>

<style scoped>
.merge-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-left: 1px solid #e2e8f0;
  width: 420px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #1e293b;
}

.merge-content {
  flex: 1;
  overflow-y: auto;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-state p {
  margin: 4px 0;
}

.empty-hint {
  font-size: 13px;
}

.preview-content {
  padding: 16px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.preview-info h4 {
  margin: 0 0 4px 0;
  font-size: 15px;
  color: #1e293b;
}

.preview-info p {
  margin: 0;
  font-size: 13px;
  color: #64748b;
}

.preview-info strong {
  color: #3b82f6;
}

.preview-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  flex: 1;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 8px;
}

.stat-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #475569;
}

.stat-arrow {
  font-size: 24px;
  color: #94a3b8;
  font-weight: bold;
}

.preview-summary {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: #f1f5f9;
  font-size: 13px;
}

.summary-icon.auto {
  font-size: 18px;
}

.summary-icon.pending {
  font-size: 18px;
}

.summary-text strong {
  color: #ef4444;
}

.conflicts-section {
  border-top: 1px solid #e2e8f0;
  padding-top: 16px;
}

.conflicts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.conflicts-header h4 {
  margin: 0;
  font-size: 14px;
  color: #1e293b;
}

.conflicts-progress {
  font-size: 12px;
  color: #64748b;
}

.conflict-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.conflict-item {
  background: #fffbeb;
  border: 2px solid #fcd34d;
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s;
}

.conflict-item.resolved {
  background: #f0fdf4;
  border-color: #86efac;
}

.conflict-entities {
  display: flex;
  align-items: stretch;
  gap: 8px;
  margin-bottom: 12px;
}

.entity-card {
  flex: 1;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px;
}

.entity-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.entity-source {
  font-size: 11px;
  color: #94a3b8;
}

.entity-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
}

.entity-context {
  font-size: 12px;
  color: #64748b;
  line-height: 1.4;
  max-height: 48px;
  overflow: hidden;
}

.conflict-info {
  width: 80px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: #fef3c7;
  border-radius: 6px;
  padding: 8px;
  text-align: center;
}

.conflict-score {
  font-size: 12px;
  color: #78350f;
  margin-bottom: 4px;
}

.conflict-score strong {
  font-size: 14px;
  color: #92400e;
}

.conflict-hint {
  font-size: 10px;
  color: #92400e;
  line-height: 1.3;
}

.conflict-actions {
  display: flex;
  justify-content: flex-end;
}

.action-result {
  display: flex;
  align-items: center;
  gap: 8px;
}

.merge-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.select-kb-dialog {
  max-height: 300px;
  overflow-y: auto;
}

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kb-item {
  padding: 12px;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.kb-item:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.kb-item.selected {
  border-color: #3b82f6;
  background: #eff6ff;
}

.kb-name {
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 4px;
}

.kb-stats {
  font-size: 12px;
  color: #64748b;
}

.empty-kb {
  text-align: center;
  padding: 40px;
  color: #94a3b8;
}
</style>