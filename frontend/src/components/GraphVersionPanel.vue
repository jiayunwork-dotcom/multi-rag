<template>
  <div class="version-panel">
    <div class="panel-header">
      <h3>版本历史</h3>
      <div class="header-actions">
        <el-button size="small" type="primary" @click="createVersion">
          <el-icon><Plus /></el-icon>
          创建版本
        </el-button>
      </div>
    </div>

    <div class="compare-section" v-if="versions.length > 0">
      <div class="compare-title">版本对比:</div>
      <div class="compare-controls">
        <el-select v-model="compareVersionA" placeholder="选择版本A" size="small" style="width: 120px;">
          <el-option label="当前版本" :value="null" />
          <el-option
            v-for="v in versions"
            :key="v.id"
            :label="`v${v.version_number}`"
            :value="v.id"
          />
        </el-select>
        <span class="compare-arrow">VS</span>
        <el-select v-model="compareVersionB" placeholder="选择版本B" size="small" style="width: 120px;">
          <el-option
            v-for="v in versions"
            :key="v.id"
            :label="`v${v.version_number}`"
            :value="v.id"
          />
        </el-select>
        <el-button
          size="small"
          type="primary"
          :disabled="!compareVersionB"
          @click="compareVersions"
        >
          对比
        </el-button>
        <el-button
          size="small"
          @click="clearComparison"
          v-if="hasComparison"
        >
          清除对比
        </el-button>
      </div>
    </div>

    <div class="version-list" v-loading="loading">
      <div
        v-for="version in versions"
        :key="version.id"
        class="version-item"
        :class="{ active: selectedVersionId === version.id, compared: isCompared(version.id) }"
        @click="selectVersion(version)"
      >
        <div class="version-header">
          <span class="version-badge">v{{ version.version_number }}</span>
          <span class="version-date">{{ formatDate(version.created_at) }}</span>
        </div>
        <div class="version-stats">
          <span class="stat-item">
            <span class="stat-icon">👤</span>
            {{ version.entity_count }} 实体
          </span>
          <span class="stat-item">
            <span class="stat-icon">🔗</span>
            {{ version.relation_count }} 关系
          </span>
          <span class="stat-item">
            <span class="stat-icon">📦</span>
            {{ version.connected_components }} 分量
          </span>
        </div>
        <div class="version-desc" v-if="version.description">
          {{ version.description }}
        </div>
      </div>

      <div v-if="!loading && versions.length === 0" class="empty-state">
        <div class="empty-icon">📜</div>
        <p>暂无版本记录</p>
        <p class="empty-hint">构建图谱后会自动创建版本</p>
      </div>
    </div>

    <div v-if="versionDiff" class="diff-panel">
      <div class="diff-header">
        <h4>
          版本差异
          <span class="diff-versions">
            v{{ versionDiff.version_a_number }} → v{{ versionDiff.version_b_number }}
          </span>
        </h4>
        <el-button size="small" text @click="closeDiff">关闭</el-button>
      </div>
      <div class="diff-stats">
        <div class="diff-stat added">
          <span class="diff-icon">➕</span>
          <span class="diff-count">{{ versionDiff.added_entity_count }}</span>
          <span class="diff-label">新增实体</span>
        </div>
        <div class="diff-stat removed">
          <span class="diff-icon">➖</span>
          <span class="diff-count">{{ versionDiff.removed_entity_count }}</span>
          <span class="diff-label">删除实体</span>
        </div>
        <div class="diff-stat added">
          <span class="diff-icon">➕</span>
          <span class="diff-count">{{ versionDiff.added_relation_count }}</span>
          <span class="diff-label">新增关系</span>
        </div>
        <div class="diff-stat removed">
          <span class="diff-icon">➖</span>
          <span class="diff-count">{{ versionDiff.removed_relation_count }}</span>
          <span class="diff-label">删除关系</span>
        </div>
      </div>
      <div class="diff-details">
        <div v-if="versionDiff.added_entities.length > 0" class="diff-section">
          <h5>新增实体</h5>
          <div class="diff-list">
            <div
              v-for="entity in versionDiff.added_entities"
              :key="entity.entity_id"
              class="diff-item added"
            >
              <span class="entity-name">{{ entity.name }}</span>
              <el-tag size="small" :type="getEntityTagType(entity.entity_type)">
                {{ getEntityTypeLabel(entity.entity_type) }}
              </el-tag>
            </div>
          </div>
        </div>
        <div v-if="versionDiff.removed_entities.length > 0" class="diff-section">
          <h5>删除实体</h5>
          <div class="diff-list">
            <div
              v-for="entity in versionDiff.removed_entities"
              :key="entity.entity_id"
              class="diff-item removed"
            >
              <span class="entity-name">{{ entity.name }}</span>
              <el-tag size="small" :type="getEntityTagType(entity.entity_type)">
                {{ getEntityTypeLabel(entity.entity_type) }}
              </el-tag>
            </div>
          </div>
        </div>
        <div v-if="versionDiff.added_relations.length > 0" class="diff-section">
          <h5>新增关系</h5>
          <div class="diff-list">
            <div
              v-for="rel in versionDiff.added_relations"
              :key="rel.relation_id"
              class="diff-item added"
            >
              <span class="entity-name">{{ rel.source_entity_name }} → {{ rel.target_entity_name }}</span>
              <el-tag size="small" type="warning">{{ getRelationTypeLabel(rel.relation_type) }}</el-tag>
            </div>
          </div>
        </div>
        <div v-if="versionDiff.removed_relations.length > 0" class="diff-section">
          <h5>删除关系</h5>
          <div class="diff-list">
            <div
              v-for="rel in versionDiff.removed_relations"
              :key="rel.relation_id"
              class="diff-item removed"
            >
              <span class="entity-name">{{ rel.source_entity_name }} → {{ rel.target_entity_name }}</span>
              <el-tag size="small" type="warning">{{ getRelationTypeLabel(rel.relation_type) }}</el-tag>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { graphApi } from '@/api'
import type { GraphVersionBase, GraphVersionDiff } from '@/types'

const props = defineProps<{
  knowledgeBaseId: number
}>()

const emit = defineEmits<{
  (e: 'version-selected', version: GraphVersionBase): void
  (e: 'comparison-changed', diff: GraphVersionDiff | null): void
  (e: 'highlight-changed', data: {
    addedEntityIds: Set<string>
    removedEntityIds: Set<string>
  }): void
}>()

const loading = ref(false)
const versions = ref<GraphVersionBase[]>([])
const selectedVersionId = ref<number | null>(null)
const compareVersionA = ref<number | null>(null)
const compareVersionB = ref<number | null>(null)
const versionDiff = ref<GraphVersionDiff | null>(null)

const entityTypes = [
  { value: 'person', label: '人物' },
  { value: 'organization', label: '组织' },
  { value: 'location', label: '地点' },
  { value: 'tech_concept', label: '技术' },
  { value: 'event', label: '事件' }
]

const hasComparison = ref(false)

onMounted(() => {
  loadVersions()
})

watch(() => props.knowledgeBaseId, () => {
  loadVersions()
})

async function loadVersions() {
  loading.value = true
  try {
    const res = await graphApi.listVersions(props.knowledgeBaseId)
    versions.value = res.data
  } catch (e) {
    console.error('Failed to load versions:', e)
  } finally {
    loading.value = false
  }
}

async function createVersion() {
  try {
    await graphApi.createVersion(props.knowledgeBaseId)
    ElMessage.success('版本创建成功')
    loadVersions()
  } catch (e) {
    ElMessage.error('创建版本失败')
  }
}

function selectVersion(version: GraphVersionBase) {
  selectedVersionId.value = version.id
  emit('version-selected', version)
}

function isCompared(versionId: number) {
  return compareVersionA.value === versionId || compareVersionB.value === versionId
}

async function compareVersions() {
  if (!compareVersionB.value) return

  try {
    const res = await graphApi.compareVersions(props.knowledgeBaseId, {
      knowledge_base_id: props.knowledgeBaseId,
      version_a_id: compareVersionA.value || undefined,
      version_b_id: compareVersionB.value
    })

    versionDiff.value = res.data
    hasComparison.value = true

    const addedEntityIds = new Set(
      res.data.added_entities.map(e => e.entity_id.toString())
    )
    const removedEntityIds = new Set(
      res.data.removed_entities.map(e => e.entity_id.toString())
    )

    emit('comparison-changed', res.data)
    emit('highlight-changed', { addedEntityIds, removedEntityIds })
  } catch (e) {
    ElMessage.error('版本对比失败')
  }
}

function clearComparison() {
  versionDiff.value = null
  hasComparison.value = false
  compareVersionA.value = null
  compareVersionB.value = null
  emit('comparison-changed', null)
  emit('highlight-changed', {
    addedEntityIds: new Set(),
    removedEntityIds: new Set()
  })
}

function closeDiff() {
  clearComparison()
}

function formatDate(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function getEntityTypeLabel(type: string) {
  const t = entityTypes.find(t => t.value === type)
  return t?.label || type
}

const relationTypes = [
  { value: 'belongs_to', label: '属于' },
  { value: 'located_in', label: '位于' },
  { value: 'created_by', label: '由...创建' },
  { value: 'uses', label: '使用' },
  { value: 'depends_on', label: '依赖' },
  { value: 'contains', label: '包含' }
]

function getRelationTypeLabel(type: string) {
  const r = relationTypes.find(r => r.value === type)
  return r?.label || type
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

defineExpose({
  loadVersions,
  clearComparison
})
</script>

<style scoped>
.version-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-right: 1px solid #e2e8f0;
  width: 320px;
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

.compare-section {
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f1f5f9;
}

.compare-title {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.compare-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.compare-arrow {
  font-weight: 600;
  color: #64748b;
  font-size: 12px;
}

.version-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.version-item {
  padding: 12px;
  margin-bottom: 8px;
  background: #f8fafc;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.version-item:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.version-item.active {
  background: #eff6ff;
  border-color: #3b82f6;
}

.version-item.compared {
  border-color: #f59e0b;
  background: #fffbeb;
}

.version-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.version-badge {
  background: #3b82f6;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.version-date {
  font-size: 12px;
  color: #64748b;
}

.version-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #475569;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-icon {
  font-size: 14px;
}

.version-desc {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #94a3b8;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-state p {
  margin: 4px 0;
}

.empty-hint {
  font-size: 12px;
}

.diff-panel {
  border-top: 2px solid #e2e8f0;
  background: #fafafa;
}

.diff-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: white;
}

.diff-header h4 {
  margin: 0;
  font-size: 14px;
  color: #1e293b;
}

.diff-versions {
  font-size: 12px;
  color: #64748b;
  font-weight: normal;
  margin-left: 8px;
}

.diff-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 12px 16px;
  background: white;
  border-bottom: 1px solid #e2e8f0;
}

.diff-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border-radius: 6px;
  background: #f8fafc;
}

.diff-stat.added {
  background: #f0fdf4;
}

.diff-stat.removed {
  background: #fef2f2;
}

.diff-icon {
  font-size: 14px;
}

.diff-count {
  font-weight: 600;
  font-size: 16px;
  color: #1e293b;
}

.diff-label {
  font-size: 11px;
  color: #64748b;
}

.diff-details {
  max-height: 250px;
  overflow-y: auto;
  padding: 8px 16px;
}

.diff-section {
  margin-bottom: 12px;
}

.diff-section h5 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #475569;
}

.diff-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.diff-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.diff-item.added {
  background: #dcfce7;
  color: #166534;
}

.diff-item.removed {
  background: #fee2e2;
  color: #991b1b;
}

.entity-name {
  font-weight: 500;
}
</style>