<template>
  <div class="graph-editor">
    <div class="editor-header">
      <h3>📊 图谱管理</h3>
    </div>

    <div class="editor-tabs">
      <button :class="['tab-btn', { active: activeTab === 'entities' }]" @click="activeTab = 'entities'">
        实体管理
      </button>
      <button :class="['tab-btn', { active: activeTab === 'relations' }]" @click="activeTab = 'relations'">
        关系管理
      </button>
      <button :class="['tab-btn', { active: activeTab === 'actions' }]" @click="activeTab = 'actions'">
        图谱操作
      </button>
    </div>

    <div class="editor-content">
      <div v-if="activeTab === 'entities'" class="tab-content">
        <div class="entity-form">
          <h4>添加实体</h4>
          <div class="form-group">
            <label>实体名称</label>
            <input v-model="newEntity.name" type="text" placeholder="输入实体名称" />
          </div>
          <div class="form-group">
            <label>实体类型</label>
            <select v-model="newEntity.entity_type">
              <option v-for="type in entityTypes" :key="type.value" :value="type.value">
                {{ type.icon }} {{ type.label }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="newEntity.description" placeholder="实体描述（可选）" rows="2"></textarea>
          </div>
          <button class="add-btn" @click="createEntity" :disabled="!newEntity.name">
            + 添加实体
          </button>
        </div>

        <div class="entity-list">
          <h4>现有实体 ({{ entities.length }})</h4>
          <div class="search-box">
            <input v-model="entitySearch" type="text" placeholder="搜索实体..." />
          </div>
          <div class="entity-items">
            <div v-for="entity in filteredEntities" :key="entity.id" class="entity-item">
              <div class="entity-info">
                <span class="entity-type-icon">{{ getEntityIcon(entity.entity_type) }}</span>
                <span class="entity-name">{{ entity.name }}</span>
                <span class="entity-type-tag" :class="`tag-${entity.entity_type}`">
                  {{ getEntityLabel(entity.entity_type) }}
                </span>
              </div>
              <div class="entity-actions">
                <button class="action-icon" @click="editEntity(entity)" title="编辑">✏️</button>
                <button class="action-icon delete" @click="deleteEntity(entity.id)" title="删除">🗑️</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'relations'" class="tab-content">
        <div class="relation-form">
          <h4>添加关系</h4>
          <div class="form-group">
            <label>源实体</label>
            <select v-model="newRelation.source_entity_id">
              <option :value="null">请选择源实体</option>
              <option v-for="entity in entities" :key="entity.id" :value="entity.id">
                {{ entity.name }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>关系类型</label>
            <select v-model="newRelation.relation_type">
              <option v-for="rel in relationTypes" :key="rel.value" :value="rel.value">
                {{ rel.label }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>目标实体</label>
            <select v-model="newRelation.target_entity_id">
              <option :value="null">请选择目标实体</option>
              <option v-for="entity in entities" :key="entity.id" :value="entity.id">
                {{ entity.name }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="newRelation.description" placeholder="关系描述（可选）" rows="2"></textarea>
          </div>
          <button class="add-btn" @click="createRelation" :disabled="!newRelation.source_entity_id || !newRelation.target_entity_id">
            + 添加关系
          </button>
        </div>

        <div class="relation-list">
          <h4>现有关系 ({{ relations.length }})</h4>
          <div class="relation-items">
            <div v-for="relation in relations" :key="relation.id" class="relation-item">
              <div class="relation-info">
                <span class="entity-name">{{ relation.source_entity_name }}</span>
                <span class="relation-arrow" :class="`rel-${relation.relation_type}`">
                  {{ getRelationLabel(relation.relation_type) }} →
                </span>
                <span class="entity-name">{{ relation.target_entity_name }}</span>
                <span class="freq-badge">×{{ relation.frequency }}</span>
              </div>
              <div class="relation-actions">
                <button class="action-icon delete" @click="deleteRelation(relation.id)" title="删除">🗑️</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'actions'" class="tab-content">
        <div class="action-section">
          <h4>构建图谱</h4>
          <p class="help-text">从文档中自动提取实体和关系构建知识图谱</p>
          <div class="action-options">
            <label>
              <input v-model="rebuildGraph" type="checkbox" />
              重新构建（覆盖现有数据）
            </label>
          </div>
          <button class="action-btn primary" @click="buildGraph" :disabled="isBuilding">
            {{ isBuilding ? '构建中...' : '🔨 开始构建' }}
          </button>
          <div v-if="buildProgress" class="progress-bar">
            <div class="progress-fill" :style="{ width: buildProgress.progress + '%' }"></div>
            <span class="progress-text">{{ Math.round(buildProgress.progress) }}%</span>
          </div>
        </div>

        <div class="action-section">
          <h4>导出图谱</h4>
          <p class="help-text">将图谱导出为 GraphML 格式文件</p>
          <button class="action-btn" @click="exportGraph">
            📤 导出 GraphML
          </button>
        </div>

        <div class="action-section danger">
          <h4>危险操作</h4>
          <p class="help-text">清除该知识库的所有图谱数据</p>
          <button class="action-btn danger" @click="clearGraph" :disabled="isClearing">
            {{ isClearing ? '清除中...' : '⚠️ 清除图谱' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="editingEntity" class="edit-modal-overlay" @click.self="editingEntity = null">
      <div class="edit-modal">
        <h3>编辑实体</h3>
        <div class="form-group">
          <label>实体名称</label>
          <input v-model="editingEntity.name" type="text" />
        </div>
        <div class="form-group">
          <label>实体类型</label>
          <select v-model="editingEntity.entity_type">
            <option v-for="type in entityTypes" :key="type.value" :value="type.value">
              {{ type.icon }} {{ type.label }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>描述</label>
          <textarea v-model="editingEntity.description" rows="3"></textarea>
        </div>
        <div class="modal-actions">
          <button class="cancel-btn" @click="editingEntity = null">取消</button>
          <button class="save-btn" @click="updateEntity">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { GraphEntity, GraphRelation, EntityType, RelationType, GraphEntityCreate, GraphRelationCreate, GraphBuildProgress } from '@/types'
import { graphApi } from '@/api'

const props = defineProps<{
  knowledgeBaseId: number
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const activeTab = ref<'entities' | 'relations' | 'actions'>('entities')
const entities = ref<GraphEntity[]>([])
const relations = ref<GraphRelation[]>([])
const entitySearch = ref('')
const editingEntity = ref<GraphEntity | null>(null)

const newEntity = ref<GraphEntityCreate>({
  knowledge_base_id: props.knowledgeBaseId,
  name: '',
  entity_type: 'tech_concept' as EntityType,
  description: ''
})

const newRelation = ref<GraphRelationCreate>({
  knowledge_base_id: props.knowledgeBaseId,
  source_entity_id: 0,
  target_entity_id: 0,
  relation_type: 'uses' as RelationType,
  description: ''
})

const rebuildGraph = ref(false)
const isBuilding = ref(false)
const isClearing = ref(false)
const buildProgress = ref<GraphBuildProgress | null>(null)

const entityTypes = [
  { value: 'person' as EntityType, label: '人物', icon: '👤' },
  { value: 'organization' as EntityType, label: '组织', icon: '🏢' },
  { value: 'location' as EntityType, label: '地点', icon: '📍' },
  { value: 'tech_concept' as EntityType, label: '技术概念', icon: '💡' },
  { value: 'event' as EntityType, label: '事件', icon: '📅' }
]

const relationTypes = [
  { value: 'belongs_to' as RelationType, label: '属于' },
  { value: 'located_in' as RelationType, label: '位于' },
  { value: 'created_by' as RelationType, label: '由...创建' },
  { value: 'uses' as RelationType, label: '使用' },
  { value: 'depends_on' as RelationType, label: '依赖' },
  { value: 'contains' as RelationType, label: '包含' }
]

const filteredEntities = computed(() => {
  if (!entitySearch.value) return entities.value
  const search = entitySearch.value.toLowerCase()
  return entities.value.filter(e =>
    e.name.toLowerCase().includes(search)
  )
})

const getEntityIcon = (type: EntityType) => {
  const t = entityTypes.find(t => t.value === type)
  return t?.icon || '❓'
}

const getEntityLabel = (type: EntityType) => {
  const t = entityTypes.find(t => t.value === type)
  return t?.label || type
}

const getRelationLabel = (type: RelationType) => {
  const r = relationTypes.find(r => r.value === type)
  return r?.label || type
}

const loadEntities = async () => {
  try {
    entities.value = await graphApi.listEntities(props.knowledgeBaseId, { limit: 200 })
  } catch (e) {
    console.error('Failed to load entities:', e)
  }
}

const loadRelations = async () => {
  try {
    relations.value = await graphApi.listRelations(props.knowledgeBaseId, { limit: 200 })
  } catch (e) {
    console.error('Failed to load relations:', e)
  }
}

const createEntity = async () => {
  if (!newEntity.value.name) return
  try {
    await graphApi.createEntity(newEntity.value)
    newEntity.value.name = ''
    newEntity.value.description = ''
    await loadEntities()
    emit('refresh')
  } catch (e) {
    console.error('Failed to create entity:', e)
  }
}

const editEntity = (entity: GraphEntity) => {
  editingEntity.value = { ...entity }
}

const updateEntity = async () => {
  if (!editingEntity.value) return
  try {
    await graphApi.updateEntity(editingEntity.value.id, {
      name: editingEntity.value.name,
      entity_type: editingEntity.value.entity_type,
      description: editingEntity.value.description
    })
    editingEntity.value = null
    await loadEntities()
    emit('refresh')
  } catch (e) {
    console.error('Failed to update entity:', e)
  }
}

const deleteEntity = async (id: number) => {
  if (!confirm('确定要删除这个实体吗？相关关系也会被删除。')) return
  try {
    await graphApi.deleteEntity(id)
    await loadEntities()
    await loadRelations()
    emit('refresh')
  } catch (e) {
    console.error('Failed to delete entity:', e)
  }
}

const createRelation = async () => {
  if (!newRelation.value.source_entity_id || !newRelation.value.target_entity_id) return
  try {
    await graphApi.createRelation(newRelation.value)
    newRelation.value.source_entity_id = 0
    newRelation.value.target_entity_id = 0
    newRelation.value.description = ''
    await loadRelations()
    emit('refresh')
  } catch (e) {
    console.error('Failed to create relation:', e)
  }
}

const deleteRelation = async (id: number) => {
  if (!confirm('确定要删除这个关系吗？')) return
  try {
    await graphApi.deleteRelation(id)
    await loadRelations()
    emit('refresh')
  } catch (e) {
    console.error('Failed to delete relation:', e)
  }
}

const buildGraph = async () => {
  isBuilding.value = true
  try {
    const result = await graphApi.buildGraph({
      knowledge_base_id: props.knowledgeBaseId,
      rebuild: rebuildGraph.value
    })
    buildProgress.value = result

    const interval = setInterval(async () => {
      try {
        const progress = await graphApi.getBuildProgress(props.knowledgeBaseId)
        buildProgress.value = progress
        if (progress.status === 'completed' || progress.status === 'failed') {
          clearInterval(interval)
          isBuilding.value = false
          await loadEntities()
          await loadRelations()
          emit('refresh')
        }
      } catch (e) {
        clearInterval(interval)
        isBuilding.value = false
      }
    }, 2000)
  } catch (e) {
    console.error('Failed to build graph:', e)
    isBuilding.value = false
  }
}

const exportGraph = async () => {
  try {
    const blob = await graphApi.exportGraph(props.knowledgeBaseId) as unknown as Blob
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `knowledge_base_${props.knowledgeBaseId}_graph.graphml`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error('Failed to export graph:', e)
  }
}

const clearGraph = async () => {
  if (!confirm('确定要清除所有图谱数据吗？此操作不可恢复！')) return
  isClearing.value = true
  try {
    await graphApi.clearGraph(props.knowledgeBaseId)
    await loadEntities()
    await loadRelations()
    emit('refresh')
  } catch (e) {
    console.error('Failed to clear graph:', e)
  } finally {
    isClearing.value = false
  }
}

onMounted(() => {
  loadEntities()
  loadRelations()
})
</script>

<style scoped>
.graph-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
}

.editor-header {
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.editor-header h3 {
  margin: 0;
  font-size: 16px;
}

.editor-tabs {
  display: flex;
  border-bottom: 1px solid #e2e8f0;
}

.tab-btn {
  flex: 1;
  padding: 12px 16px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  color: #64748b;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: #f8fafc;
  color: #475569;
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
  font-weight: 500;
}

.editor-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.entity-form,
.relation-form {
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.entity-form h4,
.relation-form h4,
.entity-list h4,
.relation-list h4,
.action-section h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #334155;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  margin-bottom: 4px;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  background: white;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.add-btn {
  width: 100%;
  padding: 10px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s;
}

.add-btn:hover:not(:disabled) {
  background: #2563eb;
}

.add-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.search-box {
  margin-bottom: 12px;
}

.search-box input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
}

.entity-items,
.relation-items {
  max-height: 200px;
  overflow-y: auto;
}

.entity-item,
.relation-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  margin-bottom: 8px;
}

.entity-info,
.relation-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.entity-type-icon {
  font-size: 16px;
}

.entity-name {
  font-weight: 500;
  color: #1e293b;
  font-size: 13px;
}

.entity-type-tag {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.tag-person { background: #fee2e2; color: #dc2626; }
.tag-organization { background: #ccfbf1; color: #0d9488; }
.tag-location { background: #cffafe; color: #0891b2; }
.tag-tech_concept { background: #d1fae5; color: #059669; }
.tag-event { background: #fef3c7; color: #d97706; }

.relation-arrow {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.rel-belongs_to { background: #fee2e2; color: #dc2626; }
.rel-located_in { background: #ccfbf1; color: #0d9488; }
.rel-created_by { background: #cffafe; color: #0891b2; }
.rel-uses { background: #d1fae5; color: #059669; }
.rel-depends_on { background: #fef3c7; color: #d97706; }
.rel-contains { background: #f1f5f9; color: #475569; }

.freq-badge {
  padding: 2px 6px;
  background: #f1f5f9;
  border-radius: 4px;
  font-size: 11px;
  color: #64748b;
}

.entity-actions,
.relation-actions {
  display: flex;
  gap: 4px;
}

.action-icon {
  width: 28px;
  height: 28px;
  border: none;
  background: #f1f5f9;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.action-icon:hover {
  background: #e2e8f0;
}

.action-icon.delete:hover {
  background: #fee2e2;
}

.action-section {
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.action-section.danger {
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.help-text {
  font-size: 12px;
  color: #64748b;
  margin: 0 0 12px;
}

.action-options {
  margin-bottom: 12px;
  font-size: 13px;
}

.action-btn {
  width: 100%;
  padding: 10px;
  background: white;
  color: #475569;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.action-btn.primary {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.action-btn.primary:hover:not(:disabled) {
  background: #2563eb;
}

.action-btn.danger {
  background: #ef4444;
  color: white;
  border-color: #ef4444;
}

.action-btn.danger:hover:not(:disabled) {
  background: #dc2626;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.progress-bar {
  position: relative;
  height: 24px;
  background: #e2e8f0;
  border-radius: 12px;
  margin-top: 12px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 12px;
  transition: width 0.3s;
}

.progress-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #1e293b;
}

.edit-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.edit-modal {
  background: white;
  border-radius: 12px;
  padding: 24px;
  width: 90%;
  max-width: 400px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}

.edit-modal h3 {
  margin: 0 0 20px;
  font-size: 18px;
}

.modal-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.cancel-btn,
.save-btn {
  flex: 1;
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.cancel-btn {
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #e2e8f0;
}

.cancel-btn:hover {
  background: #e2e8f0;
}

.save-btn {
  background: #3b82f6;
  color: white;
  border: none;
}

.save-btn:hover {
  background: #2563eb;
}
</style>