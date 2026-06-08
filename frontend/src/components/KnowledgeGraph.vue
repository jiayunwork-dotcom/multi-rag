<template>
  <div class="knowledge-graph">
    <div class="graph-toolbar">
      <div class="filter-section">
        <span class="filter-label">实体类型筛选:</span>
        <div class="filter-buttons">
          <button
            v-for="type in entityTypes"
            :key="type.value"
            :class="['filter-btn', { active: selectedTypes.includes(type.value) }]"
            @click="toggleTypeFilter(type.value)"
          >
            <span class="type-icon" :class="`icon-${type.value}`">{{ type.icon }}</span>
            <span>{{ type.label }}</span>
          </button>
        </div>
      </div>
      <div class="action-buttons">
        <button class="action-btn" @click="resetView">
          <span>🔄</span> 重置视图
        </button>
        <button class="action-btn" @click="zoomIn">
          <span>🔍+</span> 放大
        </button>
        <button class="action-btn" @click="zoomOut">
          <span>🔍-</span> 缩小
        </button>
        <button class="action-btn" @click="toggleEditMode">
          <span>✏️</span> {{ isEditMode ? '退出编辑' : '编辑模式' }}
        </button>
      </div>
    </div>

    <div class="graph-container" ref="containerRef" @mousedown="onContainerMouseDown" @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp" @wheel="onWheel">
      <svg ref="svgRef" :width="containerWidth" :height="containerHeight">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#999" />
          </marker>
        </defs>
        <g :transform="`translate(${translateX}, ${translateY}) scale(${scale})`">
          <g class="edges">
            <line
              v-for="edge in visibleEdges"
              :key="edge.id"
              :x1="getNodeById(edge.source)?.x || 0"
              :y1="getNodeById(edge.source)?.y || 0"
              :x2="getNodeById(edge.target)?.x || 0"
              :y2="getNodeById(edge.target)?.y || 0"
              :stroke-width="edge.width"
              :stroke="getEdgeColor(edge)"
              :class="['edge', { highlighted: isEdgeHighlighted(edge) }]"
              @click.stop="onEdgeClick(edge)"
            />
          </g>
          <g class="nodes">
            <g
              v-for="node in visibleNodes"
              :key="node.id"
              :transform="`translate(${node.x}, ${node.y})`"
              :class="['node', { 
                selected: selectedNode?.id === node.id, 
                highlighted: isNodeHighlighted(node), 
                'super-node': node.is_super_node,
                'added-node': isNodeAdded(node),
                'removed-node': isNodeRemoved(node)
              }]"
              @mousedown.stop="onNodeMouseDown($event, node)"
              @click.stop="onNodeClick(node)"
            >
              <path
                v-if="!node.is_super_node"
                :d="getNodeShape(node)"
                :fill="getNodeColor(node)"
                :stroke="getNodeStroke(node)"
                :stroke-width="getNodeStrokeWidth(node)"
                :stroke-dasharray="isNodeRemoved(node) ? '5,5' : undefined"
                :r="node.size"
              />
              <circle
                v-else
                :r="node.size"
                :fill="getNodeColor(node)"
                :stroke="getNodeStroke(node)"
                :stroke-width="getNodeStrokeWidth(node)"
                :stroke-dasharray="isNodeRemoved(node) ? '5,5' : '5,5'"
              />
              <text
                :y="node.size + 15"
                text-anchor="middle"
                font-size="12"
                :fill="selectedNode?.id === node.id ? '#ff6b6b' : '#333'"
                font-weight="500"
              >
                {{ node.name.length > 10 ? node.name.slice(0, 10) + '...' : node.name }}
              </text>
              <text v-if="node.is_super_node" :y="node.size + 30" text-anchor="middle" font-size="10" fill="#888">
                {{ node.super_node_members?.length || 0 }} 个节点
              </text>
            </g>
          </g>
        </g>
        <rect
          v-if="isSelecting"
          :x="selectionStart.x < selectionEnd.x ? selectionStart.x : selectionEnd.x"
          :y="selectionStart.y < selectionEnd.y ? selectionStart.y : selectionEnd.y"
          :width="Math.abs(selectionEnd.x - selectionStart.x)"
          :height="Math.abs(selectionEnd.y - selectionStart.y)"
          fill="rgba(66, 153, 225, 0.1)"
          stroke="#4299e1"
          stroke-width="1"
          stroke-dasharray="5,5"
        />
      </svg>

      <div v-if="loading" class="loading-overlay">
        <div class="spinner"></div>
        <p>正在加载图谱数据...</p>
      </div>

      <div v-else-if="!graphData?.nodes?.length" class="empty-overlay">
        <div class="empty-icon">🕸️</div>
        <h3>暂无图谱数据</h3>
        <p>该知识库尚未构建知识图谱</p>
        <p class="empty-hint">请先上传并解析文档，系统将自动提取实体和关系构建知识图谱</p>
      </div>
    </div>

    <div v-if="selectedNode" class="entity-detail-panel">
      <div class="panel-header">
        <h3>
          <span class="entity-icon" :class="`icon-${selectedNode.entity_type}`">{{ getEntityTypeIcon(selectedNode.entity_type) }}</span>
          {{ selectedNode.name }}
        </h3>
        <button class="close-btn" @click="selectedNode = null">×</button>
      </div>
      <div class="panel-body">
        <div class="info-row">
          <span class="label">实体类型:</span>
          <span class="value">{{ getEntityTypeLabel(selectedNode.entity_type) }}</span>
        </div>
        <div class="info-row">
          <span class="label">关联度数:</span>
          <span class="value">{{ selectedNode.degree }}</span>
        </div>
        <div class="info-row">
          <span class="label">所属社区:</span>
          <span class="value">{{ selectedNode.community_id ?? 'N/A' }}</span>
        </div>
        <div v-if="entityDetail" class="entity-full-detail">
          <div class="info-row">
            <span class="label">出现次数:</span>
            <span class="value">{{ entityDetail.occurrence_count }}</span>
          </div>
          <div class="info-row">
            <span class="label">文档数量:</span>
            <span class="value">{{ entityDetail.document_count }}</span>
          </div>
          <div v-if="entityDetail.description" class="info-row">
            <span class="label">描述:</span>
            <span class="value">{{ entityDetail.description }}</span>
          </div>
          <div v-if="entityDetail.related_chunks?.length" class="related-chunks">
            <h4>相关片段</h4>
            <div v-for="(chunk, idx) in entityDetail.related_chunks.slice(0, 5)" :key="idx" class="chunk-item">
              <div class="chunk-header">
                <span>{{ chunk.document_title }}</span>
                <span class="chunk-index">Chunk #{{ chunk.chunk_index }}</span>
              </div>
              <p class="chunk-content">{{ chunk.content_preview }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="isEditMode" class="graph-editor-panel">
      <GraphEditor
        :knowledge-base-id="knowledgeBaseId"
        @refresh="loadGraphData"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import type { GraphData, GraphNode, GraphEdge, GraphEntityDetail, EntityType } from '@/types'
import { graphApi } from '@/api'
import GraphEditor from './GraphEditor.vue'

const props = defineProps<{
  knowledgeBaseId: number
  highlightAddedEntityIds?: Set<string>
  highlightRemovedEntityIds?: Set<string>
  highlightNodeIds?: Set<string>
  highlightEdgeIds?: Set<string>
}>()

const emit = defineEmits<{
  (e: 'node-click', node: GraphNode): void
  (e: 'graph-loaded', data: GraphData): void
}>()

const containerRef = ref<HTMLDivElement>()
const svgRef = ref<SVGSVGElement>()
const containerWidth = ref(800)
const containerHeight = ref(600)

const graphData = ref<GraphData | null>(null)
const loading = ref(false)
const selectedNode = ref<GraphNode | null>(null)
const entityDetail = ref<GraphEntityDetail | null>(null)
const selectedTypes = ref<EntityType[]>(['person', 'organization', 'location', 'tech_concept', 'event'])
const isEditMode = ref(false)

const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const isDragging = ref(false)
const isNodeDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const isSelecting = ref(false)
const selectionStart = ref({ x: 0, y: 0 })
const selectionEnd = ref({ x: 0, y: 0 })

const entityTypes = [
  { value: 'person' as EntityType, label: '人物', icon: '👤' },
  { value: 'organization' as EntityType, label: '组织', icon: '🏢' },
  { value: 'location' as EntityType, label: '地点', icon: '📍' },
  { value: 'tech_concept' as EntityType, label: '技术', icon: '💡' },
  { value: 'event' as EntityType, label: '事件', icon: '📅' }
]

const visibleNodes = computed(() => {
  if (!graphData.value) return []
  return graphData.value.nodes.filter(node =>
    selectedTypes.value.includes(node.entity_type) || node.is_super_node
  )
})

const visibleEdges = computed(() => {
  if (!graphData.value) return []
  const visibleNodeIds = new Set(visibleNodes.value.map(n => n.id))
  return graphData.value.edges.filter(edge =>
    visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
  )
})

const getNodeById = (id: string) => {
  return visibleNodes.value.find(n => n.id === id)
}

const getNodeShape = (node: GraphNode) => {
  const size = node.size
  const type = node.entity_type

  switch (type) {
    case 'person':
      return `M 0 ${-size} A ${size} ${size} 0 1 1 0 ${size} A ${size} ${size} 0 1 1 0 ${-size}`
    case 'organization':
      return `M ${-size} ${-size} L ${size} ${-size} L ${size} ${size} L ${-size} ${size} Z`
    case 'location':
      return `M 0 ${-size} L ${size} ${size * 0.5} L ${-size} ${size * 0.5} Z`
    case 'tech_concept':
      return `M 0 ${-size} L ${size} 0 L 0 ${size} L ${-size} 0 Z`
    case 'event':
      const angle = Math.PI / 3
      const points = []
      for (let i = 0; i < 6; i++) {
        const x = size * Math.cos(angle * i - Math.PI / 2)
        const y = size * Math.sin(angle * i - Math.PI / 2)
        points.push(`${x} ${y}`)
      }
      return `M ${points.join(' L ')} Z`
    default:
      return `M 0 ${-size} A ${size} ${size} 0 1 1 0 ${size} A ${size} ${size} 0 1 1 0 ${-size}`
  }
}

const getNodeColor = (node: GraphNode) => {
  if (node.is_super_node) return '#e2e8f0'
  const colors: Record<EntityType, string> = {
    person: '#ff6b6b',
    organization: '#4ecdc4',
    location: '#45b7d1',
    tech_concept: '#96ceb4',
    event: '#ffeaa7'
  }
  return colors[node.entity_type] || '#ccc'
}

const getEdgeColor = (edge: GraphEdge) => {
  if (props.highlightEdgeIds?.has(edge.id)) {
    return '#f59e0b'
  }
  const colors: Record<string, string> = {
    belongs_to: '#ff6b6b',
    located_in: '#4ecdc4',
    created_by: '#45b7d1',
    uses: '#96ceb4',
    depends_on: '#ffeaa7',
    contains: '#dfe6e9'
  }
  return colors[edge.relation_type] || '#999'
}

const getEntityTypeLabel = (type: EntityType) => {
  const t = entityTypes.find(t => t.value === type)
  return t?.label || type
}

const getEntityTypeIcon = (type: EntityType) => {
  const t = entityTypes.find(t => t.value === type)
  return t?.icon || '❓'
}

const toggleTypeFilter = (type: EntityType) => {
  const idx = selectedTypes.value.indexOf(type)
  if (idx > -1) {
    selectedTypes.value.splice(idx, 1)
  } else {
    selectedTypes.value.push(type)
  }
}

const isNodeHighlighted = (node: GraphNode) => {
  if (props.highlightNodeIds?.has(node.id)) return true
  if (props.highlightAddedEntityIds?.has(node.id)) return true
  if (props.highlightRemovedEntityIds?.has(node.id)) return true
  if (!selectedNode.value) return false
  if (selectedNode.value.id === node.id) return true
  if (!graphData.value) return false
  return graphData.value.edges.some(e =>
    (e.source === selectedNode.value?.id && e.target === node.id) ||
    (e.target === selectedNode.value?.id && e.source === node.id)
  )
}

const isEdgeHighlighted = (edge: GraphEdge) => {
  if (props.highlightEdgeIds?.has(edge.id)) return true
  if (!selectedNode.value) return false
  return edge.source === selectedNode.value.id || edge.target === selectedNode.value.id
}

const isNodeAdded = (node: GraphNode) => {
  return props.highlightAddedEntityIds?.has(node.id) || false
}

const isNodeRemoved = (node: GraphNode) => {
  return props.highlightRemovedEntityIds?.has(node.id) || false
}

const getNodeStroke = (node: GraphNode) => {
  if (selectedNode.value?.id === node.id) return '#ff6b6b'
  if (isNodeAdded(node)) return '#22c55e'
  if (isNodeRemoved(node)) return '#ef4444'
  return '#333'
}

const getNodeStrokeWidth = (node: GraphNode) => {
  if (selectedNode.value?.id === node.id) return 3
  if (isNodeAdded(node) || isNodeRemoved(node)) return 2.5
  return 1.5
}

const onNodeMouseDown = (event: MouseEvent, node: GraphNode) => {
  if (isEditMode.value) return
  event.preventDefault()
  isNodeDragging.value = true
  dragStart.value = { x: event.clientX - node.x, y: event.clientY - node.y }
}

const onNodeClick = async (node: GraphNode) => {
  selectedNode.value = node
  if (node.is_super_node) {
    return
  }
  try {
    entityDetail.value = await graphApi.getEntityDetail(parseInt(node.id))
  } catch (e) {
    console.error('Failed to load entity detail:', e)
  }
  emit('node-click', node)
}

const onEdgeClick = (edge: GraphEdge) => {
  console.log('Edge clicked:', edge)
}

const onContainerMouseDown = (event: MouseEvent) => {
  if (isEditMode.value) return
  if (event.button === 0) {
    if (event.shiftKey) {
      isSelecting.value = true
      selectionStart.value = { x: event.clientX, y: event.clientY }
      selectionEnd.value = { x: event.clientX, y: event.clientY }
    } else {
      isDragging.value = true
      dragStart.value = { x: event.clientX - translateX.value, y: event.clientY - translateY.value }
    }
  }
}

const onMouseMove = (event: MouseEvent) => {
  if (isNodeDragging.value && selectedNode.value) {
    selectedNode.value.x = event.clientX - dragStart.value.x
    selectedNode.value.y = event.clientY - dragStart.value.y
  } else if (isDragging.value) {
    translateX.value = event.clientX - dragStart.value.x
    translateY.value = event.clientY - dragStart.value.y
  } else if (isSelecting.value) {
    selectionEnd.value = { x: event.clientX, y: event.clientY }
  }
}

const onMouseUp = () => {
  isDragging.value = false
  isNodeDragging.value = false
  isSelecting.value = false
}

const onWheel = (event: WheelEvent) => {
  event.preventDefault()
  const delta = event.deltaY > 0 ? 0.9 : 1.1
  scale.value = Math.max(0.2, Math.min(3, scale.value * delta))
}

const resetView = () => {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
  selectedNode.value = null
  entityDetail.value = null
}

const zoomIn = () => {
  scale.value = Math.min(3, scale.value * 1.2)
}

const zoomOut = () => {
  scale.value = Math.max(0.2, scale.value / 1.2)
}

const toggleEditMode = () => {
  isEditMode.value = !isEditMode.value
}

const loadGraphData = async () => {
  loading.value = true
  try {
    const response = await graphApi.getGraphData(props.knowledgeBaseId, {
      filter_entity_types: selectedTypes.value.length < 5 ? selectedTypes.value : undefined
    })
    
    if (response && typeof response === 'object') {
      graphData.value = {
        nodes: Array.isArray(response.nodes) ? response.nodes : [],
        edges: Array.isArray(response.edges) ? response.edges : [],
        stats: response.stats || {
          entity_count: 0,
          relation_count: 0,
          connected_components: 0,
          community_count: 0,
          avg_degree: 0,
          max_degree: 0,
          entity_types_distribution: {},
          relation_types_distribution: {},
          build_status: 'pending',
          build_progress: 0,
          last_built_at: null
        }
      }
      runForceSimulation()
      emit('graph-loaded', graphData.value)
    } else {
      graphData.value = {
        nodes: [],
        edges: [],
        stats: {
          entity_count: 0,
          relation_count: 0,
          connected_components: 0,
          community_count: 0,
          avg_degree: 0,
          max_degree: 0,
          entity_types_distribution: {},
          relation_types_distribution: {},
          build_status: 'pending',
          build_progress: 0,
          last_built_at: null
        }
      }
    }
  } catch (e) {
    console.error('Failed to load graph data:', e)
    graphData.value = {
      nodes: [],
      edges: [],
      stats: {
        entity_count: 0,
        relation_count: 0,
        connected_components: 0,
        community_count: 0,
        avg_degree: 0,
        max_degree: 0,
        entity_types_distribution: {},
        relation_types_distribution: {},
        build_status: 'failed',
        build_progress: 0,
        last_built_at: null
      }
    }
  } finally {
    loading.value = false
  }
}

const runForceSimulation = () => {
  if (!graphData.value) return
  const nodes = graphData.value.nodes
  const edges = graphData.value.edges
  const width = containerWidth.value
  const height = containerHeight.value
  const centerX = width / 2
  const centerY = height / 2

  if (!nodes.some(n => n.x === undefined || n.y === undefined)) {
    return
  }

  nodes.forEach((node, i) => {
    if (node.x === undefined || node.y === undefined) {
      const angle = (2 * Math.PI * i) / nodes.length
      node.x = centerX + Math.cos(angle) * 150
      node.y = centerY + Math.sin(angle) * 150
    }
  })

  const iterations = 100
  const forceStrength = 0.05
  const repulsionStrength = 2000
  const attractionStrength = 0.01

  for (let iter = 0; iter < iterations; iter++) {
    nodes.forEach((node, i) => {
      let fx = 0, fy = 0

      nodes.forEach((other, j) => {
        if (i === j) return
        const dx = (node.x || 0) - (other.x || 0)
        const dy = (node.y || 0) - (other.y || 0)
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const repulsion = repulsionStrength / (dist * dist)
        fx += (dx / dist) * repulsion
        fy += (dy / dist) * repulsion
      })

      edges.forEach(edge => {
        let source: GraphNode | undefined, target: GraphNode | undefined
        if (edge.source === node.id) {
          source = node
          target = nodes.find(n => n.id === edge.target)
        } else if (edge.target === node.id) {
          source = nodes.find(n => n.id === edge.source)
          target = node
        }
        if (source && target) {
          const dx = (target.x || 0) - (source.x || 0)
          const dy = (target.y || 0) - (source.y || 0)
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const attraction = (dist - 100) * attractionStrength
          if (edge.source === node.id) {
            fx += (dx / dist) * attraction
            fy += (dy / dist) * attraction
          } else {
            fx -= (dx / dist) * attraction
            fy -= (dy / dist) * attraction
          }
        }
      })

      fx += (centerX - (node.x || 0)) * 0.01
      fy += (centerY - (node.y || 0)) * 0.01

      node.x = (node.x || 0) + fx * forceStrength
      node.y = (node.y || 0) + fy * forceStrength
    })
  }
}

const updateContainerSize = () => {
  if (containerRef.value) {
    containerWidth.value = containerRef.value.clientWidth
    containerHeight.value = containerRef.value.clientHeight
  }
}

onMounted(() => {
  updateContainerSize()
  window.addEventListener('resize', updateContainerSize)
  nextTick(() => {
    updateContainerSize()
    loadGraphData()
  })
})

watch(() => props.knowledgeBaseId, () => {
  loadGraphData()
})

watch(selectedTypes, () => {
  loadGraphData()
}, { deep: true })
</script>

<style scoped>
.knowledge-graph {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
  background: #f8fafc;
  border-radius: 8px;
  overflow: hidden;
}

.graph-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: white;
  border-bottom: 1px solid #e2e8f0;
  flex-wrap: wrap;
  gap: 12px;
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-label {
  font-weight: 500;
  color: #475569;
}

.filter-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
}

.filter-btn:hover {
  background: #f1f5f9;
}

.filter-btn.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

.type-icon {
  font-size: 14px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
}

.action-btn:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.graph-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  cursor: grab;
}

.graph-container:active {
  cursor: grabbing;
}

svg {
  display: block;
}

.edge {
  cursor: pointer;
  transition: stroke 0.2s, stroke-width 0.2s;
  opacity: 0.6;
}

.edge:hover,
.edge.highlighted {
  opacity: 1;
  stroke-width: 3 !important;
}

.node {
  cursor: pointer;
  transition: transform 0.1s;
}

.node:hover {
  transform: scale(1.1);
}

.node.highlighted {
  filter: brightness(1.1);
}

.node.selected {
  filter: drop-shadow(0 0 8px rgba(255, 107, 107, 0.6));
}

.node text {
  pointer-events: none;
  user-select: none;
}

.super-node {
  opacity: 0.9;
}

.loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  z-index: 10;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  z-index: 10;
  text-align: center;
  padding: 24px;
}

.empty-icon {
  font-size: 64px;
  opacity: 0.5;
}

.empty-overlay h3 {
  margin: 0;
  color: #475569;
  font-size: 20px;
}

.empty-overlay p {
  margin: 0;
  color: #64748b;
  font-size: 14px;
}

.empty-overlay .empty-hint {
  color: #94a3b8;
  font-size: 13px;
  max-width: 400px;
}

.entity-detail-panel {
  position: absolute;
  top: 80px;
  right: 16px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  z-index: 5;
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
  display: flex;
  align-items: center;
  gap: 8px;
}

.entity-icon {
  font-size: 20px;
}

.close-btn {
  border: none;
  background: none;
  font-size: 24px;
  cursor: pointer;
  color: #94a3b8;
  line-height: 1;
}

.close-btn:hover {
  color: #475569;
}

.panel-body {
  padding: 16px;
  overflow-y: auto;
  max-height: calc(100% - 60px);
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
}

.info-row:last-child {
  border-bottom: none;
}

.label {
  color: #64748b;
  font-size: 13px;
}

.value {
  color: #1e293b;
  font-weight: 500;
  font-size: 13px;
}

.entity-full-detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.related-chunks h4 {
  margin: 16px 0 8px;
  font-size: 14px;
  color: #475569;
}

.chunk-item {
  padding: 8px;
  background: #f8fafc;
  border-radius: 4px;
  margin-bottom: 8px;
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.chunk-content {
  font-size: 12px;
  color: #475569;
  margin: 0;
  line-height: 1.4;
}

.graph-editor-panel {
  position: absolute;
  top: 80px;
  left: 16px;
  width: 360px;
  max-height: calc(100% - 100px);
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  z-index: 5;
}
</style>