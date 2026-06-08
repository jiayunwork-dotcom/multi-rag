<template>
  <div class="ab-compare-panel">
    <div v-if="!result" class="config-panel">
      <h3>检索策略A/B对比</h3>
      <p class="tip">选择两组不同的检索参数，系统将并行执行并对比结果</p>

      <div class="strategy-config">
        <div class="strategy-column">
          <div class="strategy-header strategy-a">
            <el-icon><Histogram /></el-icon>
            <span>策略 A</span>
          </div>
          <div class="strategy-form">
            <el-form :model="strategyA" label-width="120px" size="small">
              <el-form-item label="语义检索Top-K">
                <el-input-number v-model="strategyA.semantic_top_k" :min="1" :max="50" />
              </el-form-item>
              <el-form-item label="BM25检索Top-K">
                <el-input-number v-model="strategyA.bm25_top_k" :min="1" :max="50" />
              </el-form-item>
              <el-form-item label="使用RRF融合">
                <el-switch v-model="strategyA.use_rrf" />
              </el-form-item>
              <el-form-item label="RRF K值" v-if="strategyA.use_rrf">
                <el-input-number v-model="strategyA.rrf_k" :min="10" :max="120" />
              </el-form-item>
              <el-form-item label="使用重排序">
                <el-switch v-model="strategyA.use_rerank" />
              </el-form-item>
              <el-form-item label="重排返回数" v-if="strategyA.use_rerank">
                <el-input-number v-model="strategyA.rerank_n" :min="1" :max="20" />
              </el-form-item>
            </el-form>
          </div>
        </div>

        <div class="vs-divider">
          <span>VS</span>
        </div>

        <div class="strategy-column">
          <div class="strategy-header strategy-b">
            <el-icon><DataLine /></el-icon>
            <span>策略 B</span>
          </div>
          <div class="strategy-form">
            <el-form :model="strategyB" label-width="120px" size="small">
              <el-form-item label="语义检索Top-K">
                <el-input-number v-model="strategyB.semantic_top_k" :min="1" :max="50" />
              </el-form-item>
              <el-form-item label="BM25检索Top-K">
                <el-input-number v-model="strategyB.bm25_top_k" :min="1" :max="50" />
              </el-form-item>
              <el-form-item label="使用RRF融合">
                <el-switch v-model="strategyB.use_rrf" />
              </el-form-item>
              <el-form-item label="RRF K值" v-if="strategyB.use_rrf">
                <el-input-number v-model="strategyB.rrf_k" :min="10" :max="120" />
              </el-form-item>
              <el-form-item label="使用重排序">
                <el-switch v-model="strategyB.use_rerank" />
              </el-form-item>
              <el-form-item label="重排返回数" v-if="strategyB.use_rerank">
                <el-input-number v-model="strategyB.rerank_n" :min="1" :max="20" />
              </el-form-item>
            </el-form>
          </div>
        </div>
      </div>

      <div class="quick-presets">
        <span class="preset-label">快速预设:</span>
        <el-button size="small" @click="applyPreset('semantic_vs_bm25')">
          语义Top-20 vs BM25 Top-10
        </el-button>
        <el-button size="small" @click="applyPreset('with_rerank_vs_without')">
          重排序 vs 无重排序
        </el-button>
        <el-button size="small" @click="applyPreset('rrf_vs_no_rrf')">
          RRF融合 vs 简单合并
        </el-button>
      </div>

      <div class="question-input">
        <el-input
          v-model="question"
          type="textarea"
          :rows="2"
          placeholder="请输入要测试的问题..."
        />
      </div>

      <div class="actions">
        <el-button @click="$emit('cancel')">取消</el-button>
        <el-button type="primary" :loading="loading" @click="runComparison">
          <el-icon><VideoPlay /></el-icon>
          开始对比
        </el-button>
      </div>
    </div>

    <div v-else class="result-panel">
      <div class="result-header">
        <h3>对比结果: {{ result.question }}</h3>
        <el-button size="small" @click="reset">
          <el-icon><Refresh /></el-icon>
          重新配置
        </el-button>
      </div>

      <div class="result-content">
        <div class="result-column">
          <div class="result-header-tag strategy-a">
            <span>策略 A</span>
            <el-tag size="small" :type="strategyAWinner ? 'success' : 'info'">
              {{ strategyAWinner ? '更优' : '' }}
            </el-tag>
          </div>

          <div class="metrics-row">
            <div class="metric-item">
              <div class="metric-value">{{ result.strategy_a.retrieval_time_ms.toFixed(0) }}ms</div>
              <div class="metric-label">检索耗时</div>
            </div>
            <div class="metric-item">
              <div class="metric-value">{{ result.strategy_a.chunk_count }}</div>
              <div class="metric-label">返回块数</div>
            </div>
            <div class="metric-item">
              <div class="metric-value">{{ (result.strategy_a.final_score * 100).toFixed(1) }}%</div>
              <div class="metric-label">最终得分</div>
            </div>
          </div>

          <div class="strategy-config-mini">
            <el-tag size="small" type="info">
              语义Top-{{ result.strategy_a.strategy_config.semantic_top_k }}
            </el-tag>
            <el-tag size="small" type="info">
              BM25 Top-{{ result.strategy_a.strategy_config.bm25_top_k }}
            </el-tag>
            <el-tag size="small" :type="result.strategy_a.strategy_config.use_rrf ? 'success' : 'info'">
              RRF: {{ result.strategy_a.strategy_config.use_rrf ? '开启' : '关闭' }}
            </el-tag>
            <el-tag size="small" :type="result.strategy_a.strategy_config.use_rerank ? 'success' : 'info'">
              重排: {{ result.strategy_a.strategy_config.use_rerank ? '开启' : '关闭' }}
            </el-tag>
          </div>

          <div class="answer-section">
            <h4>回答:</h4>
            <div class="answer-content" v-html="formatMessageContent(result.strategy_a.answer)"></div>
          </div>

          <div class="citations-section" v-if="result.strategy_a.citations?.length">
            <h4>引用来源:</h4>
            <div
              v-for="cite in result.strategy_a.citations"
              :key="cite.index"
              class="citation-item"
            >
              <span class="cite-index">[{{ cite.index }}]</span>
              <span class="cite-doc">{{ cite.document_title }}</span>
              <span class="cite-page" v-if="cite.page_number">p.{{ cite.page_number }}</span>
            </div>
          </div>

          <div class="retrieval-debug">
            <el-collapse>
              <el-collapse-item title="检索调试信息" name="debug">
                <el-tabs>
                  <el-tab-pane label="语义检索" name="semantic">
                    <el-table :data="result.strategy_a.retrieval_debug.semantic_retrieval || []" size="small">
                      <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
                      <el-table-column prop="score" label="得分" width="100">
                        <template #default="{ row }">{{ row.score?.toFixed(4) }}</template>
                      </el-table-column>
                      <el-table-column prop="content_preview" label="内容预览" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>
                  <el-tab-pane label="BM25检索" name="bm25">
                    <el-table :data="result.strategy_a.retrieval_debug.bm25_retrieval || []" size="small">
                      <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
                      <el-table-column prop="score" label="得分" width="100">
                        <template #default="{ row }">{{ row.score?.toFixed(4) }}</template>
                      </el-table-column>
                      <el-table-column prop="content_preview" label="内容预览" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>
                  <el-tab-pane label="RRF融合" name="rrf" v-if="result.strategy_a.strategy_config.use_rrf">
                    <el-table :data="result.strategy_a.retrieval_debug.rrf_fusion || []" size="small">
                      <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
                      <el-table-column prop="score" label="得分" width="100">
                        <template #default="{ row }">{{ row.score?.toFixed(4) }}</template>
                      </el-table-column>
                    </el-table>
                  </el-tab-pane>
                  <el-tab-pane label="重排序" name="rerank" v-if="result.strategy_a.strategy_config.use_rerank">
                    <el-table :data="result.strategy_a.retrieval_debug.reranked || []" size="small">
                      <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
                      <el-table-column prop="score" label="得分" width="100">
                        <template #default="{ row }">{{ row.score?.toFixed(4) }}</template>
                      </el-table-column>
                      <el-table-column prop="content_preview" label="内容预览" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>
                </el-tabs>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>

        <div class="result-column">
          <div class="result-header-tag strategy-b">
            <span>策略 B</span>
            <el-tag size="small" :type="strategyBWinner ? 'success' : 'info'">
              {{ strategyBWinner ? '更优' : '' }}
            </el-tag>
          </div>

          <div class="metrics-row">
            <div class="metric-item">
              <div class="metric-value">{{ result.strategy_b.retrieval_time_ms.toFixed(0) }}ms</div>
              <div class="metric-label">检索耗时</div>
            </div>
            <div class="metric-item">
              <div class="metric-value">{{ result.strategy_b.chunk_count }}</div>
              <div class="metric-label">返回块数</div>
            </div>
            <div class="metric-item">
              <div class="metric-value">{{ (result.strategy_b.final_score * 100).toFixed(1) }}%</div>
              <div class="metric-label">最终得分</div>
            </div>
          </div>

          <div class="strategy-config-mini">
            <el-tag size="small" type="info">
              语义Top-{{ result.strategy_b.strategy_config.semantic_top_k }}
            </el-tag>
            <el-tag size="small" type="info">
              BM25 Top-{{ result.strategy_b.strategy_config.bm25_top_k }}
            </el-tag>
            <el-tag size="small" :type="result.strategy_b.strategy_config.use_rrf ? 'success' : 'info'">
              RRF: {{ result.strategy_b.strategy_config.use_rrf ? '开启' : '关闭' }}
            </el-tag>
            <el-tag size="small" :type="result.strategy_b.strategy_config.use_rerank ? 'success' : 'info'">
              重排: {{ result.strategy_b.strategy_config.use_rerank ? '开启' : '关闭' }}
            </el-tag>
          </div>

          <div class="answer-section">
            <h4>回答:</h4>
            <div class="answer-content" v-html="formatMessageContent(result.strategy_b.answer)"></div>
          </div>

          <div class="citations-section" v-if="result.strategy_b.citations?.length">
            <h4>引用来源:</h4>
            <div
              v-for="cite in result.strategy_b.citations"
              :key="cite.index"
              class="citation-item"
            >
              <span class="cite-index">[{{ cite.index }}]</span>
              <span class="cite-doc">{{ cite.document_title }}</span>
              <span class="cite-page" v-if="cite.page_number">p.{{ cite.page_number }}</span>
            </div>
          </div>

          <div class="retrieval-debug">
            <el-collapse>
              <el-collapse-item title="检索调试信息" name="debug">
                <el-tabs>
                  <el-tab-pane label="语义检索" name="semantic">
                    <el-table :data="result.strategy_b.retrieval_debug.semantic_retrieval || []" size="small">
                      <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
                      <el-table-column prop="score" label="得分" width="100">
                        <template #default="{ row }">{{ row.score?.toFixed(4) }}</template>
                      </el-table-column>
                      <el-table-column prop="content_preview" label="内容预览" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>
                  <el-tab-pane label="BM25检索" name="bm25">
                    <el-table :data="result.strategy_b.retrieval_debug.bm25_retrieval || []" size="small">
                      <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
                      <el-table-column prop="score" label="得分" width="100">
                        <template #default="{ row }">{{ row.score?.toFixed(4) }}</template>
                      </el-table-column>
                      <el-table-column prop="content_preview" label="内容预览" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>
                  <el-tab-pane label="RRF融合" name="rrf" v-if="result.strategy_b.strategy_config.use_rrf">
                    <el-table :data="result.strategy_b.retrieval_debug.rrf_fusion || []" size="small">
                      <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
                      <el-table-column prop="score" label="得分" width="100">
                        <template #default="{ row }">{{ row.score?.toFixed(4) }}</template>
                      </el-table-column>
                    </el-table>
                  </el-tab-pane>
                  <el-tab-pane label="重排序" name="rerank" v-if="result.strategy_b.strategy_config.use_rerank">
                    <el-table :data="result.strategy_b.retrieval_debug.reranked || []" size="small">
                      <el-table-column prop="chunk_id" label="Chunk ID" width="80" />
                      <el-table-column prop="score" label="得分" width="100">
                        <template #default="{ row }">{{ row.score?.toFixed(4) }}</template>
                      </el-table-column>
                      <el-table-column prop="content_preview" label="内容预览" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>
                </el-tabs>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { chatApi } from '@/api'
import type { RetrievalStrategy, ABCompareResponse } from '@/types'

const props = defineProps<{
  knowledgeBaseId: number
  conversationId?: number
}>()

const emit = defineEmits<{
  cancel: []
  result: [response: ABCompareResponse]
}>()

const loading = ref(false)
const question = ref('')
const result = ref<ABCompareResponse | null>(null)

const strategyA = ref<RetrievalStrategy>({
  semantic_top_k: 20,
  bm25_top_k: 20,
  use_rrf: true,
  rrf_k: 60,
  use_rerank: true,
  rerank_n: 5
})

const strategyB = ref<RetrievalStrategy>({
  semantic_top_k: 10,
  bm25_top_k: 10,
  use_rrf: false,
  rrf_k: 60,
  use_rerank: false,
  rerank_n: 5
})

const strategyAWinner = computed(() => {
  if (!result.value) return false
  return result.value.strategy_a.final_score > result.value.strategy_b.final_score
})

const strategyBWinner = computed(() => {
  if (!result.value) return false
  return result.value.strategy_b.final_score > result.value.strategy_a.final_score
})

function formatMessageContent(content: string) {
  return content.replace(/\[(\d+)\]/g, '<span class="citation-link" data-index="$1">[$1]</span>')
}

function applyPreset(preset: string) {
  switch (preset) {
    case 'semantic_vs_bm25':
      strategyA.value = {
        semantic_top_k: 20,
        bm25_top_k: 0,
        use_rrf: false,
        rrf_k: 60,
        use_rerank: true,
        rerank_n: 5
      }
      strategyB.value = {
        semantic_top_k: 0,
        bm25_top_k: 10,
        use_rrf: false,
        rrf_k: 60,
        use_rerank: false,
        rerank_n: 5
      }
      break
    case 'with_rerank_vs_without':
      strategyA.value = {
        semantic_top_k: 20,
        bm25_top_k: 20,
        use_rrf: true,
        rrf_k: 60,
        use_rerank: true,
        rerank_n: 5
      }
      strategyB.value = {
        semantic_top_k: 20,
        bm25_top_k: 20,
        use_rrf: true,
        rrf_k: 60,
        use_rerank: false,
        rerank_n: 5
      }
      break
    case 'rrf_vs_no_rrf':
      strategyA.value = {
        semantic_top_k: 20,
        bm25_top_k: 20,
        use_rrf: true,
        rrf_k: 60,
        use_rerank: true,
        rerank_n: 5
      }
      strategyB.value = {
        semantic_top_k: 20,
        bm25_top_k: 20,
        use_rrf: false,
        rrf_k: 60,
        use_rerank: true,
        rerank_n: 5
      }
      break
  }
}

async function runComparison() {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  loading.value = true
  try {
    const res = await chatApi.sendABCompare({
      question: question.value.trim(),
      knowledge_base_id: props.knowledgeBaseId,
      conversation_id: props.conversationId,
      strategy_a: strategyA.value,
      strategy_b: strategyB.value
    })
    result.value = res.data
    emit('result', res.data)
  } catch (e) {
    ElMessage.error('对比失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

function reset() {
  result.value = null
  question.value = ''
}
</script>

<style lang="scss" scoped>
.ab-compare-panel {
  width: 100%;
}

.config-panel {
  padding: 20px;

  h3 {
    margin: 0 0 8px 0;
    color: #303133;
  }

  .tip {
    color: #909399;
    margin: 0 0 20px 0;
    font-size: 13px;
  }
}

.strategy-config {
  display: flex;
  align-items: stretch;
  gap: 20px;
  margin-bottom: 20px;
}

.strategy-column {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.strategy-header {
  padding: 12px 16px;
  color: white;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;

  &.strategy-a {
    background: linear-gradient(135deg, #5470c6, #7392e6);
  }

  &.strategy-b {
    background: linear-gradient(135deg, #91cc75, #b3e09b);
  }
}

.strategy-form {
  padding: 16px;
}

.vs-divider {
  display: flex;
  align-items: center;
  justify-content: center;

  span {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: #f0f2f5;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    color: #909399;
  }
}

.quick-presets {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;

  .preset-label {
    color: #606266;
    font-size: 13px;
  }
}

.question-input {
  margin-bottom: 20px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.result-panel {
  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid #e4e7ed;

    h3 {
      margin: 0;
      color: #303133;
    }
  }
}

.result-content {
  display: flex;
  gap: 20px;
  padding: 20px;
}

.result-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-header-tag {
  padding: 12px 16px;
  border-radius: 8px;
  color: white;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;

  &.strategy-a {
    background: linear-gradient(135deg, #5470c6, #7392e6);
  }

  &.strategy-b {
    background: linear-gradient(135deg, #91cc75, #b3e09b);
  }
}

.metrics-row {
  display: flex;
  gap: 16px;
}

.metric-item {
  flex: 1;
  text-align: center;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;

  .metric-value {
    font-size: 24px;
    font-weight: 700;
    color: #303133;
    margin-bottom: 4px;
  }

  .metric-label {
    font-size: 12px;
    color: #909399;
  }
}

.strategy-config-mini {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.answer-section,
.citations-section,
.retrieval-debug {
  h4 {
    margin: 0 0 8px 0;
    color: #606266;
    font-size: 14px;
  }
}

.answer-content {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  line-height: 1.6;
  color: #303133;

  :deep(.citation-link) {
    color: #409eff;
    cursor: pointer;
  }
}

.citations-section {
  .citation-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    background: #f5f7fa;
    border-radius: 6px;
    margin-bottom: 4px;
    font-size: 13px;

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

.retrieval-debug {
  margin-top: auto;
}
</style>