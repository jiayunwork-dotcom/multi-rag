<template>
  <div class="retrieval-visualization">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="向量空间分布" name="scatter">
        <div class="chart-container">
          <div class="chart-header">
            <el-tag size="small" type="info">
              PCA降维 ({{ explainedVariance[0].toFixed(2) }} + {{ explainedVariance[1].toFixed(2) }})
            </el-tag>
            <div class="legend">
              <span class="legend-item">
                <span class="legend-dot query-dot"></span>
                用户问题
              </span>
              <span
                v-for="doc in uniqueDocuments"
                :key="doc.id"
                class="legend-item"
              >
                <span
                  class="legend-dot"
                  :style="{ backgroundColor: getDocumentColor(doc.id) }"
                ></span>
                {{ doc.name }}
              </span>
            </div>
          </div>
          <div ref="scatterChartRef" class="scatter-chart"></div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="检索得分对比" name="bar">
        <div class="chart-container">
          <div class="chart-header">
            <el-select v-model="sortBy" size="small" style="width: 150px;" @change="updateBarChart">
              <el-option label="按重排得分" value="rerank_score" />
              <el-option label="按RRF得分" value="rrf_score" />
              <el-option label="按语义得分" value="semantic_score" />
              <el-option label="按BM25得分" value="bm25_score" />
            </el-select>
          </div>
          <div ref="barChartRef" class="bar-chart"></div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import * as echarts from 'echarts'
import type { VisualizationData } from '@/types'

const props = defineProps<{
  data: VisualizationData | null
}>()

const activeTab = ref('scatter')
const sortBy = ref('rerank_score')
const scatterChartRef = ref<HTMLElement | null>(null)
const barChartRef = ref<HTMLElement | null>(null)
let scatterChart: echarts.ECharts | null = null
let barChart: echarts.ECharts | null = null

const documentColors: Record<number, string> = {}
const colorPalette = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#48b8bd'
]

const explainedVariance = computed(() => {
  return props.data?.explained_variance_ratio || [0, 0]
})

const uniqueDocuments = computed(() => {
  if (!props.data) return []
  const docMap = new Map<number, string>()
  props.data.chunks.forEach(chunk => {
    if (!docMap.has(chunk.document_id)) {
      docMap.set(chunk.document_id, chunk.document_title)
    }
  })
  return Array.from(docMap.entries()).map(([id, name]) => ({ id, name }))
})

function getDocumentColor(docId: number): string {
  if (!documentColors[docId]) {
    const index = Object.keys(documentColors).length % colorPalette.length
    documentColors[docId] = colorPalette[index]
  }
  return documentColors[docId]
}

function initScatterChart() {
  if (!scatterChartRef.value || !props.data) return

  scatterChart = echarts.init(scatterChartRef.value)

  const series: any[] = []

  const docGroups: Record<number, any[]> = {}
  props.data.chunks.forEach(chunk => {
    if (!docGroups[chunk.document_id]) {
      docGroups[chunk.document_id] = []
    }
    docGroups[chunk.document_id].push({
      value: [chunk.x, chunk.y, chunk.relevance_score],
      chunk_id: chunk.chunk_id,
      document_id: chunk.document_id,
      document_title: chunk.document_title,
      content_preview: chunk.content_preview,
      chunk_index: chunk.chunk_index,
      relevance_score: chunk.relevance_score
    })
  })

  Object.keys(docGroups).forEach(docId => {
    const docIdNum = parseInt(docId)
    const doc = uniqueDocuments.value.find(d => d.id === docIdNum)
    series.push({
      name: doc?.name || `文档${docId}`,
      type: 'scatter',
      data: docGroups[docIdNum],
      symbolSize: (data: any) => 10 + data[2] * 20,
      itemStyle: {
        color: getDocumentColor(docIdNum),
        opacity: 0.8
      },
      emphasis: {
        itemStyle: {
          borderColor: '#333',
          borderWidth: 2
        }
      }
    })
  })

  if (props.data.query_point) {
    series.push({
      name: '用户问题',
      type: 'scatter',
      data: [{
        value: [props.data.query_point.x, props.data.query_point.y, 1],
        content_preview: props.data.query_point.content_preview
      }],
      symbolSize: 25,
      symbol: 'diamond',
      itemStyle: {
        color: '#ff4d4f',
        borderColor: '#fff',
        borderWidth: 3
      },
      z: 100
    })
  }

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const data = params.data
        if (data.chunk_id) {
          return `
            <div style="max-width: 300px;">
              <strong>${data.document_title}</strong><br/>
              <span style="color: #666;">Chunk #${data.chunk_index}</span><br/>
              <span style="color: #666;">相关度: ${(data.relevance_score * 100).toFixed(1)}%</span><br/>
              <hr/>
              <p style="margin: 0; word-break: break-all;">${data.content_preview}</p>
            </div>
          `
        } else {
          return `
            <div style="max-width: 300px;">
              <strong>用户问题</strong><br/>
              <p style="margin: 0; word-break: break-all;">${data.content_preview}</p>
            </div>
          `
        }
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      name: 'PC1',
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    yAxis: {
      name: 'PC2',
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series
  }

  scatterChart.setOption(option)
}

function initBarChart() {
  if (!barChartRef.value || !props.data) return

  barChart = echarts.init(barChartRef.value)
  updateBarChart()
}

function updateBarChart() {
  if (!barChart || !props.data) return

  const scoreData = [...props.data.score_data].sort((a, b) => {
    return (b[sortBy.value] || 0) - (a[sortBy.value] || 0)
  })

  const categories = scoreData.map((d, i) => `Chunk #${d.chunk_index}`)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const data = scoreData[params[0].dataIndex]
        return `
          <div style="max-width: 300px;">
            <strong>${data.document_title}</strong><br/>
            <span style="color: #666;">Chunk #${data.chunk_index}</span><br/>
            <hr/>
            <p style="margin: 5px 0;"><strong>语义得分:</strong> ${(data.semantic_score || 0).toFixed(4)}</p>
            <p style="margin: 5px 0;"><strong>BM25得分:</strong> ${(data.bm25_score || 0).toFixed(4)}</p>
            <p style="margin: 5px 0;"><strong>RRF得分:</strong> ${(data.rrf_score || 0).toFixed(4)}</p>
            <p style="margin: 5px 0;"><strong>重排得分:</strong> ${(data.rerank_score || 0).toFixed(4)}</p>
            <hr/>
            <p style="margin: 0; word-break: break-all; color: #666;">${data.content_preview}</p>
          </div>
        `
      }
    },
    legend: {
      data: ['语义得分', 'BM25得分', 'RRF得分', '重排得分'],
      top: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: {
        rotate: 45,
        fontSize: 10
      }
    },
    yAxis: {
      type: 'value',
      name: '得分'
    },
    series: [
      {
        name: '语义得分',
        type: 'bar',
        data: scoreData.map(d => d.semantic_score || 0),
        itemStyle: { color: '#5470c6' }
      },
      {
        name: 'BM25得分',
        type: 'bar',
        data: scoreData.map(d => d.bm25_score || 0),
        itemStyle: { color: '#91cc75' }
      },
      {
        name: 'RRF得分',
        type: 'bar',
        data: scoreData.map(d => d.rrf_score || 0),
        itemStyle: { color: '#fac858' }
      },
      {
        name: '重排得分',
        type: 'bar',
        data: scoreData.map(d => d.rerank_score || 0),
        itemStyle: { color: '#ee6666' }
      }
    ]
  }

  barChart.setOption(option)
}

function handleResize() {
  scatterChart?.resize()
  barChart?.resize()
}

watch(() => props.data, () => {
  if (props.data) {
    initScatterChart()
    initBarChart()
  }
}, { deep: true })

watch(activeTab, () => {
  setTimeout(() => {
    scatterChart?.resize()
    barChart?.resize()
  }, 100)
})

onMounted(() => {
  initScatterChart()
  initBarChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  scatterChart?.dispose()
  barChart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style lang="scss" scoped>
.retrieval-visualization {
  width: 100%;
  height: 500px;
}

.chart-container {
  padding: 10px;
  height: 450px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.legend {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;

  &.query-dot {
    background: #ff4d4f;
    border: 2px solid #fff;
    box-shadow: 0 0 0 1px #ff4d4f;
  }
}

.scatter-chart,
.bar-chart {
  width: 100%;
  height: 380px;
}
</style>