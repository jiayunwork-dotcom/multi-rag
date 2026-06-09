<template>
  <div class="query-panel">
    <div class="query-header">
      <h3>图谱查询</h3>
      <div class="query-actions">
        <el-button size="small" @click="showHelp = !showHelp">
          <el-icon><QuestionFilled /></el-icon>
          查询语法
        </el-button>
      </div>
    </div>

    <div v-if="showHelp" class="help-panel">
      <div class="help-header">
        <span>查询语法说明</span>
        <el-button size="small" text @click="showHelp = false">关闭</el-button>
      </div>
      <div class="help-content">
        <div class="help-section">
          <h4>自然语言查询示例:</h4>
          <ul>
            <li>"找出所有与Python相关的技术概念"</li>
            <li>"从FastAPI到PostgreSQL的依赖路径"</li>
          </ul>
        </div>
        <div class="help-section">
          <h4>简化语法示例:</h4>
          <ul>
            <li><code>FIND entity WHERE type=tech_concept AND name CONTAINS "Python"</code></li>
            <li><code>PATH FROM "FastAPI" TO "PostgreSQL" MAX_HOPS 3</code></li>
          </ul>
        </div>
        <div class="help-tip">
          💡 提示: 按 Tab 键可以自动补全实体名称
        </div>
      </div>
    </div>

    <div class="query-input-section">
      <div class="input-wrapper">
        <el-input
          ref="queryInputRef"
          v-model="queryText"
          placeholder="输入查询语句... (支持自然语言或简化语法)"
          size="large"
          clearable
          @keyup.enter="executeQuery"
          @keydown.tab.prevent="handleTab"
          @input="onInput"
        >
          <template #prepend>
            <el-select v-model="queryMode" size="large" style="width: 110px;">
              <el-option label="智能模式" value="auto" />
              <el-option label="自然语言" value="natural" />
              <el-option label="图查询语法" value="structured" />
            </el-select>
          </template>
          <template #append>
            <el-button type="primary" :loading="queryLoading" @click="executeQuery">
              <el-icon><Search /></el-icon>
              查询
            </el-button>
          </template>
        </el-input>

        <div v-if="suggestions.length > 0" class="autocomplete-dropdown">
          <div
            v-for="(item, index) in suggestions"
            :key="item.id"
            class="autocomplete-item"
            :class="{ active: activeSuggestionIndex === index }"
            @click="selectSuggestion(item)"
          >
            <span class="suggestion-name">{{ item.name }}</span>
            <el-tag size="small" :type="getEntityTagType(item.entity_type)">
              {{ getEntityTypeLabel(item.entity_type) }}
            </el-tag>
          </div>
        </div>
      </div>

      <div v-if="queryHistory.length > 0" class="history-section">
        <div class="history-header">
          <span>查询历史 (最近10条)</span>
          <el-button size="small" text @click="showHistory = !showHistory">
            {{ showHistory ? '收起' : '展开' }}
          </el-button>
        </div>
        <div v-if="showHistory" class="history-list">
          <div
            v-for="(item, index) in queryHistory"
            :key="index"
            class="history-item"
            @click="useHistoryQuery(item.query)"
          >
            <span class="history-query">{{ item.query }}</span>
            <span class="history-time">{{ formatDate(item.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="query-results" v-loading="queryLoading">
      <div v-if="queryResult" class="results-content">
        <div class="results-header">
          <div class="results-stats">
            <span v-if="queryResult.query_type === 'find'" class="stat">
              找到 <strong>{{ queryResult.matched_entities?.length || 0 }}</strong> 个实体
            </span>
            <span v-else-if="queryResult.query_type === 'path'" class="stat">
              找到 <strong>{{ queryResult.matched_paths?.length || 0 }}</strong> 条路径
            </span>
            <span v-else-if="queryResult.query_type === 'natural_language'" class="stat">
              找到 <strong>{{ queryResult.matched_entities?.length || 0 }}</strong> 个实体,
              <strong>{{ queryResult.matched_paths?.length || 0 }}</strong> 条路径
            </span>
            <span v-if="queryResult.parsed_query" class="parsed-query">
              解析为: <code>{{ queryResult.parsed_query }}</code>
            </span>
          </div>
          <div class="results-actions">
            <el-button
              size="small"
              @click="highlightResults"
              :disabled="!queryResult.matched_entities?.length && !queryResult.matched_paths?.length"
            >
              在图谱中高亮
            </el-button>
          </div>
        </div>

        <div v-if="queryResult.query_type === 'find' && queryResult.matched_entities" class="results-table">
          <el-table :data="queryResult.matched_entities" stripe size="small" max-height="400">
            <el-table-column prop="name" label="实体名称" min-width="150">
              <template #default="{ row }">
                <span class="entity-name" @click="selectEntity(row)">{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="entity_type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="getEntityTagType(row.entity_type)">
                  {{ getEntityTypeLabel(row.entity_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="200" />
          </el-table>
        </div>

        <div v-else-if="queryResult.query_type === 'path' && queryResult.matched_paths" class="paths-results">
          <div
            v-for="(path, pathIndex) in queryResult.matched_paths"
            :key="pathIndex"
            class="path-item"
          >
            <div class="path-header">
              <span>路径 {{ pathIndex + 1 }} ({{ path.hops }} 跳)</span>
              <el-button size="small" text @click="highlightPath(path)">
                高亮路径
              </el-button>
            </div>
            <div class="path-visual">
              <template v-for="(node, index) in path.entities" :key="index">
                <span class="path-node" @click="selectEntity(node)">{{ node.name }}</span>
                <span v-if="index < path.relations.length" class="path-relation">
                  → {{ getRelationTypeLabel(path.relations[index].relation_type) }} →
                </span>
              </template>
            </div>
          </div>
        </div>

        <div v-else-if="queryResult.query_type === 'natural_language'" class="mixed-results">
          <div v-if="queryResult.matched_entities && queryResult.matched_entities.length > 0" class="results-table">
            <h5>相关实体</h5>
            <el-table :data="queryResult.matched_entities" stripe size="small" max-height="300">
              <el-table-column prop="name" label="实体名称" min-width="150">
                <template #default="{ row }">
                  <span class="entity-name" @click="selectEntity(row)">{{ row.name }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="entity_type" label="类型" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="getEntityTagType(row.entity_type)">
                    {{ getEntityTypeLabel(row.entity_type) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述" min-width="200" />
            </el-table>
          </div>
          <div v-if="queryResult.matched_paths && queryResult.matched_paths.length > 0" class="paths-results">
            <h5>相关路径</h5>
            <div
              v-for="(path, pathIndex) in queryResult.matched_paths"
              :key="pathIndex"
              class="path-item"
            >
              <div class="path-header">
                <span>路径 {{ pathIndex + 1 }} ({{ path.hops }} 跳)</span>
                <el-button size="small" text @click="highlightPath(path)">
                  高亮路径
                </el-button>
              </div>
              <div class="path-visual">
                <template v-for="(node, index) in path.entities" :key="index">
                  <span class="path-node" @click="selectEntity(node)">{{ node.name }}</span>
                  <span v-if="index < path.relations.length" class="path-relation">
                    → {{ getRelationTypeLabel(path.relations[index].relation_type) }} →
                  </span>
                </template>
              </div>
            </div>
          </div>
        </div>

        <div v-if="queryResult.highlight" class="highlight-info">
          <el-alert
            title="查询结果已在图谱中高亮显示"
            type="success"
            :closable="false"
            show-icon
          />
        </div>
      </div>

      <div v-if="!queryResult && !queryLoading" class="empty-results">
        <div class="empty-icon">🔍</div>
        <p>请输入查询语句开始查询</p>
        <p class="empty-hint">支持自然语言提问和简化的图查询语法</p>
      </div>

      <div v-if="queryError" class="query-error">
        <el-alert :title="queryError" type="error" :closable="false" show-icon />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { graphApi } from '@/api'
import type { GraphQLQueryResult, GraphQLAutocompleteResult, GraphEntity } from '@/types'

const props = defineProps<{
  knowledgeBaseId: number
}>()

const emit = defineEmits<{
  (e: 'highlight-changed', data: {
    nodeIds: Set<string>
    edgeIds: Set<string>
  }): void
  (e: 'entity-selected', entity: GraphEntity): void
}>()

const queryText = ref('')
const queryMode = ref<'auto' | 'natural' | 'structured'>('auto')
const queryLoading = ref(false)
const queryResult = ref<(GraphQLQueryResult & { highlight?: boolean }) | null>(null)
const queryError = ref<string | null>(null)
const showHelp = ref(false)
const showHistory = ref(false)

const queryInputRef = ref()
const suggestions = ref<GraphQLAutocompleteResult['suggestions']>([])
const activeSuggestionIndex = ref(-1)

const queryHistory = ref<Array<{ query: string; created_at: string }>>([])

const entityTypes = [
  { value: 'person', label: '人物' },
  { value: 'organization', label: '组织' },
  { value: 'location', label: '地点' },
  { value: 'tech_concept', label: '技术' },
  { value: 'event', label: '事件' }
]

onMounted(() => {
  loadQueryHistory()
})

async function loadQueryHistory() {
  try {
    const res = await graphApi.getQueryHistory(props.knowledgeBaseId)
    queryHistory.value = res.data.history
  } catch (e) {
    console.error('Failed to load query history:', e)
  }
}

function useHistoryQuery(query: string) {
  queryText.value = query
  showHistory.value = false
  queryInputRef.value?.focus()
}

async function onInput() {
  const text = queryText.value.trim()
  
  if (text.length >= 2) {
    try {
      const lastQuoteIndex = text.lastIndexOf('"')
      const prefix = lastQuoteIndex > 0 
        ? text.substring(lastQuoteIndex + 1).trim()
        : text.split(' ').pop() || ''
      
      if (prefix.length >= 2) {
        const res = await graphApi.getQueryAutocomplete(props.knowledgeBaseId, prefix, 5)
        suggestions.value = res.data.suggestions
        activeSuggestionIndex.value = -1
      } else {
        suggestions.value = []
      }
    } catch (e) {
      suggestions.value = []
    }
  } else {
    suggestions.value = []
  }
}

function handleTab(event: KeyboardEvent) {
  if (suggestions.value.length > 0) {
    event.preventDefault()
    
    if (activeSuggestionIndex.value === -1) {
      activeSuggestionIndex.value = 0
    }
    
    const suggestion = suggestions.value[activeSuggestionIndex.value]
    if (suggestion) {
      selectSuggestion(suggestion)
    }
  }
}

function selectSuggestion(item: { id: number; name: string; entity_type: string }) {
  const text = queryText.value
  const lastQuoteIndex = text.lastIndexOf('"')
  
  if (lastQuoteIndex > 0 && text.includes('"')) {
    queryText.value = text.substring(0, lastQuoteIndex + 1) + item.name + '"'
  } else {
    const words = text.split(' ')
    words[words.length - 1] = item.name
    queryText.value = words.join(' ')
  }
  
  suggestions.value = []
  nextTick(() => {
    queryInputRef.value?.focus()
  })
}

async function executeQuery() {
  if (!queryText.value.trim()) {
    ElMessage.warning('请输入查询语句')
    return
  }

  queryLoading.value = true
  queryError.value = null
  queryResult.value = null
  suggestions.value = []

  try {
    const res = await graphApi.executeAdvancedQuery({
      knowledge_base_id: props.knowledgeBaseId,
      query: queryText.value.trim(),
      query_mode: queryMode.value
    })
    queryResult.value = res.data
    loadQueryHistory()
  } catch (e: any) {
    queryError.value = e.response?.data?.detail || '查询执行失败'
  } finally {
    queryLoading.value = false
  }
}

function highlightResults() {
  if (!queryResult.value) return

  const nodeIds = new Set<string>()
  const edgeIds = new Set<string>()

  if (queryResult.value.matched_entities) {
    queryResult.value.matched_entities.forEach(e => nodeIds.add(e.id.toString()))
  }

  if (queryResult.value.matched_paths) {
    queryResult.value.matched_paths.forEach(path => {
      if (path.entities) {
        path.entities.forEach((e: any) => nodeIds.add(e.id.toString()))
      }
      if (path.relations) {
        path.relations.forEach((r: any) => edgeIds.add(r.id.toString()))
      }
    })
  }

  emit('highlight-changed', { nodeIds, edgeIds })
  if (queryResult.value) {
    queryResult.value.highlight = true
  }
}

function highlightPath(path: Record<string, any>) {
  const nodeIds = new Set<string>()
  const edgeIds = new Set<string>()

  if (path.entities) {
    path.entities.forEach((e: any) => nodeIds.add(e.id.toString()))
  }
  if (path.relations) {
    path.relations.forEach((r: any) => edgeIds.add(r.id.toString()))
  }

  emit('highlight-changed', { nodeIds, edgeIds })
}

function selectEntity(entity: GraphEntity) {
  emit('entity-selected', entity)
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
  clearHighlight: () => {
    emit('highlight-changed', { nodeIds: new Set(), edgeIds: new Set() })
  }
})
</script>

<style scoped>
.query-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
}

.query-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.query-header h3 {
  margin: 0;
  font-size: 16px;
  color: #1e293b;
}

.help-panel {
  border-bottom: 1px solid #e2e8f0;
  background: #fefce8;
}

.help-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  font-weight: 600;
  color: #854d0e;
}

.help-content {
  padding: 12px 20px;
}

.help-section {
  margin-bottom: 12px;
}

.help-section h4 {
  margin: 0 0 6px 0;
  font-size: 13px;
  color: #713f12;
}

.help-section ul {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #422006;
}

.help-section code {
  background: #fef3c7;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.help-tip {
  background: #fef3c7;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #713f12;
}

.query-input-section {
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.input-wrapper {
  position: relative;
}

.autocomplete-dropdown {
  position: absolute;
  top: 100%;
  left: 110px;
  right: 100px;
  max-height: 200px;
  overflow-y: auto;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 100;
  margin-top: 4px;
}

.autocomplete-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.autocomplete-item:hover,
.autocomplete-item.active {
  background: #f1f5f9;
}

.suggestion-name {
  font-weight: 500;
  color: #1e293b;
}

.history-section {
  margin-top: 12px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.history-list {
  max-height: 120px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.history-item:last-child {
  border-bottom: none;
}

.history-item:hover {
  background: #f8fafc;
}

.history-query {
  color: #334155;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 12px;
}

.history-time {
  color: #94a3b8;
  flex-shrink: 0;
}

.query-results {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.results-stats {
  font-size: 14px;
  color: #475569;
}

.results-stats strong {
  color: #3b82f6;
  margin: 0 4px;
}

.parsed-query {
  margin-left: 16px;
  font-size: 12px;
  color: #64748b;
}

.parsed-query code {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  color: #475569;
}

.results-table {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.entity-name {
  color: #3b82f6;
  cursor: pointer;
  font-weight: 500;
}

.entity-name:hover {
  text-decoration: underline;
}

.paths-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.path-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
}

.path-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: #475569;
  font-weight: 500;
}

.path-visual {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 13px;
}

.path-node {
  background: #dbeafe;
  color: #1e40af;
  padding: 4px 10px;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 500;
}

.path-node:hover {
  background: #bfdbfe;
}

.path-relation {
  color: #64748b;
  font-size: 12px;
}

.highlight-info {
  margin-top: 16px;
}

.empty-results {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-results p {
  margin: 4px 0;
}

.empty-hint {
  font-size: 13px;
}

.query-error {
  margin-top: 16px;
}
</style>