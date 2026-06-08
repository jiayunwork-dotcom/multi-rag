<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-left">
        <el-icon class="logo-icon"><ChatDotRound /></el-icon>
        <h1 class="app-title">多模态 RAG 问答系统</h1>
      </div>
      <div class="header-right">
        <el-select
          v-model="selectedKbId"
          class="kb-selector"
          placeholder="选择知识库"
          @change="onKbChange"
        >
          <el-option
            v-for="kb in store.knowledgeBases"
            :key="kb.id"
            :label="kb.name"
            :value="kb.id"
          />
        </el-select>
      </div>
    </el-header>
    <el-container>
      <el-aside width="220px" class="app-aside">
        <el-menu
          :default-active="activeMenu"
          class="side-menu"
          @select="onMenuSelect"
        >
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>智能问答</span>
          </el-menu-item>
          <el-menu-item index="/documents">
            <el-icon><Document /></el-icon>
            <span>文档管理</span>
          </el-menu-item>
          <el-menu-item index="/knowledge-base">
            <el-icon><FolderOpened /></el-icon>
            <span>知识库管理</span>
          </el-menu-item>
          <el-menu-item index="/admin">
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </el-menu-item>
        </el-menu>

        <div class="conversation-list" v-if="activeMenu === '/chat'">
          <div class="conv-header">
            <span>对话历史</span>
            <el-button size="small" type="primary" @click="createNewConversation">
              <el-icon><Plus /></el-icon>
              新建
            </el-button>
          </div>
          <el-scrollbar class="conv-scroll">
            <div
              v-for="conv in store.conversations"
              :key="conv.id"
              class="conv-item"
              :class="{ active: conv.id === store.currentConversationId }"
              @click="selectConversation(conv.id)"
            >
              <el-icon><ChatLineSquare /></el-icon>
              <span class="conv-title">{{ conv.title || '新对话' }}</span>
              <span class="conv-count">{{ conv.message_count }}条</span>
            </div>
          </el-scrollbar>
        </div>
      </el-aside>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores'
import { chatApi } from '@/api'

const store = useAppStore()
const route = useRoute()
const router = useRouter()

const selectedKbId = ref<number | null>(null)

const activeMenu = computed(() => route.path)

onMounted(async () => {
  await store.loadKnowledgeBases()
  await store.loadConversations()
  if (store.knowledgeBases.length > 0) {
    selectedKbId.value = store.currentKnowledgeBaseId
  }
})

function onKbChange(kbId: number) {
  store.currentKnowledgeBaseId = kbId
  if (route.path === '/documents') {
    store.loadDocuments(kbId)
  }
}

function onMenuSelect(index: string) {
  router.push(index)
}

async function createNewConversation() {
  try {
    const res = await chatApi.createConversation({
      knowledge_base_id: selectedKbId.value || undefined
    })
    store.conversations.unshift(res.data)
    store.currentConversationId = res.data.id
    store.messages = []
  } catch (e) {
    ElMessage.error('创建会话失败')
  }
}

async function selectConversation(convId: number) {
  await store.loadMessages(convId)
}
</script>

<style lang="scss">
.app-container {
  height: 100vh;
  overflow: hidden;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(90deg, #409eff 0%, #67c23a 100%);
  color: white;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 100;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .logo-icon {
      font-size: 28px;
    }

    .app-title {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }
  }

  .kb-selector {
    width: 200px;
  }
}

.app-aside {
  background: #f5f7fa;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.side-menu {
  border-right: none;
  background: transparent;
}

.conversation-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 12px;
  border-top: 1px solid #e4e7ed;

  .conv-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    font-weight: 600;
    color: #303133;
  }

  .conv-scroll {
    flex: 1;
  }

  .conv-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    margin-bottom: 4px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: #e9ecef;
    }

    &.active {
      background: #409eff;
      color: white;
    }

    .conv-title {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 14px;
    }

    .conv-count {
      font-size: 12px;
      opacity: 0.7;
    }
  }
}

.app-main {
  padding: 0;
  background: #fff;
  overflow: hidden;
}
</style>
