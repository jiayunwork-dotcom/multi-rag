# 多模态 RAG 问答系统

一个功能完整的多模态检索增强生成（Retrieval-Augmented Generation）问答系统，支持上传各类文档建立知识库，用户提问时系统从知识库中检索相关内容辅助回答，并自动标注信息来源。

## ✨ 功能特性

### 📁 文档上传与解析
- 支持 **PDF / Word / Markdown / 纯文本 / 图片** 文件上传
- PDF 自动提取文字内容和表格数据
- 图片使用开源 OCR 库识别文字
- 每个文档包含标题、上传时间、页数、文件大小等元数据
- 解析状态实时追踪（排队中/解析中/完成/失败）
- 支持批量上传（最多 20 个文件）
- 支持创建多个独立知识库

### 🧩 文档分块策略
提供三种分块策略供选择：
1. **固定 Token 数**：每块 256/512/1024 Token 可选，相邻块重叠 50 Token
2. **按段落**：以连续两个换行符为分割点，超长段落二次切分
3. **语义分割**：基于句子嵌入相似度，阈值可调 0.3-0.7

分块统计：总块数、平均块长度、最长块、最短块，支持预览任意块内容。

### 🔍 多模态嵌入与索引
- **文本块**：使用 Sentence-Transformers 模型（默认 all-MiniLM-L6-v2）生成 384 维向量
- **图片块**：使用 CLIP 模型生成 512 维视觉向量
- **向量存储**：Chroma 数据库 + HNSW 近似最近邻索引
- **关键词索引**：jieba 分词提取关键词，构建 BM25 倒排索引
- 索引构建进度实时查看

### 🎯 检索策略
1. **语义检索**：问题编码为向量后在 Chroma 中搜索 Top-K
2. **关键词检索**：问题分词后 BM25 打分取 Top-K
3. **混合融合**：RRF（Reciprocal Rank Fusion）合并两路结果
4. **重排序**：Cross-Encoder 模型精排，取 Top-5 作为最终结果
5. **调试面板**：每步中间结果（语义得分/BM25得分/RRF分数/重排得分）可查看

### 💬 上下文组装与生成
- 检索到的 Top-5 块拼接为上下文
- Prompt 模板可自定义
- 调用 LLM API（支持 OpenAI 兼容接口）
- 自动标注引用来源：[1][2] 标记指向具体来源块，点击可跳转查看原文

### 📜 对话历史管理
- 支持多轮对话
- 最近 5 轮对话作为上下文，超过部分自动摘要压缩
- 会话独立保存，支持创建新会话或切换历史会话
- 支持删除单条消息或整个会话

### 📊 评估指标
每次问答自动计算质量指标：
- **Faithfulness**：答案陈述是否都能从文档中找到依据（百分比）
- **Answer Relevancy**：答案与问题的语义相关度（0-1）
- **Context Precision**：检索到的块排名靠前的是否确实更相关

### ⚙️ 管理后台
- **文档管理**：查看所有文档、删除、重新解析
- **知识库管理**：创建、删除、重命名
- **系统配置**：LLM 接口参数、嵌入模型选择、分块策略默认值、检索参数调整
- **使用统计**：总问答次数、平均响应时间、检索命中率

### 🔌 REST API
- `POST /api/documents` - 上传文档
- `GET /api/documents` - 列表查询
- `POST /api/chat` - 发送问题（支持流式 SSE 返回）
- `GET /api/chat/history` - 获取对话历史
- 支持 Token 认证

## 🏗️ 技术架构

### 后端
- **框架**：FastAPI + Python 3.11
- **数据库**：PostgreSQL 16（元数据）+ Chroma（向量存储）
- **ORM**：SQLAlchemy 2.0
- **文档解析**：
  - PDF: pdfplumber（文字 + 表格）
  - Word: python-docx
  - 图片 OCR: pytesseract
- **嵌入模型**：
  - 文本: sentence-transformers (all-MiniLM-L6-v2)
  - 图片: open-clip (CLIP)
  - 重排序: cross-encoder (ms-marco-MiniLM-L-6-v2)
- **关键词检索**：jieba + rank_bm25

### 前端
- **框架**：Vue 3 + TypeScript
- **构建工具**：Vite
- **UI 组件**：Element Plus
- **状态管理**：Pinia
- **路由**：Vue Router
- **HTTP 客户端**：Axios

### 部署
- **容器化**：Docker Compose
- **前端托管**：Nginx Alpine
- **后端运行时**：Python 3.11 Slim

## 📦 快速开始

### 环境要求
- Docker >= 20.10
- Docker Compose >= 2.0
- 建议内存 >= 8GB（模型加载需要）

### 一键启动

1. 克隆项目
```bash
git clone <repository-url>
cd multi-rag
```

2. 配置环境变量
```bash
cp .env.example .env
```

编辑 `.env` 文件，配置 LLM 接口：
```env
# 数据库配置（默认即可）
POSTGRES_USER=raguser
POSTGRES_PASSWORD=ragpass
POSTGRES_DB=ragdb

# LLM 配置（支持 OpenAI 兼容接口）
LLM_ENDPOINT=https://api.openai.com/v1
LLM_API_KEY=sk-your-api-key
LLM_MODEL=gpt-3.5-turbo

# API 认证 Token
API_TOKEN=rag-token-secret

# 模型配置
EMBEDDING_MODEL=all-MiniLM-L6-v2
CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

3. 启动所有服务
```bash
docker-compose up -d
```

4. 访问系统
- 前端界面：http://localhost
- API 文档：http://localhost:8080/docs
- API 认证：在请求头中携带 `Authorization: Bearer rag-token-secret`

### 本地开发

#### 后端开发
```bash
cd backend
pip install -r requirements.txt

# 配置环境变量
export DATABASE_URL=postgresql://raguser:ragpass@localhost:5432/ragdb
export CHROMA_HOST=localhost
export CHROMA_PORT=8000

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

#### 前端开发
```bash
cd frontend
npm install
npm run dev
```

## 📁 项目结构

```
multi-rag/
├── backend/
│   ├── app/
│   │   ├── routers/              # API 路由
│   │   │   ├── admin.py          # 管理后台接口
│   │   │   ├── chat.py           # 对话接口
│   │   │   ├── documents.py      # 文档管理接口
│   │   │   └── knowledge_base.py # 知识库管理接口
│   │   ├── services/             # 业务服务
│   │   │   ├── document_parser.py    # 文档解析
│   │   │   ├── chunking_service.py   # 分块服务
│   │   │   ├── embedding_service.py  # 嵌入服务
│   │   │   ├── vector_store.py       # 向量存储
│   │   │   ├── bm25_index.py         # BM25 索引
│   │   │   ├── retrieval_service.py  # 检索服务
│   │   │   ├── llm_service.py        # LLM 生成
│   │   │   ├── conversation_service.py # 对话管理
│   │   │   ├── evaluation_service.py  # 评估指标
│   │   │   └── pipeline_service.py    # 处理流水线
│   │   ├── config.py             # 配置管理
│   │   ├── database.py           # 数据库连接
│   │   ├── models.py             # ORM 模型
│   │   ├── schemas.py            # Pydantic 模式
│   │   └── middleware.py         # 中间件
│   ├── main.py                   # 应用入口
│   ├── requirements.txt          # Python 依赖
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                  # API 客户端
│   │   ├── router/               # 路由配置
│   │   ├── stores/               # Pinia 状态管理
│   │   ├── types/                # TypeScript 类型
│   │   ├── views/                # 页面组件
│   │   │   ├── Chat.vue          # 聊天界面
│   │   │   ├── Documents.vue     # 文档管理
│   │   │   ├── KnowledgeBase.vue # 知识库管理
│   │   │   └── Admin.vue         # 系统管理
│   │   ├── App.vue               # 根组件
│   │   └── main.ts               # 入口文件
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🔧 API 接口

### 知识库管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge-bases` | 获取知识库列表 |
| POST | `/api/knowledge-bases` | 创建知识库 |
| GET | `/api/knowledge-bases/{id}` | 获取知识库详情 |
| PUT | `/api/knowledge-bases/{id}` | 更新知识库 |
| DELETE | `/api/knowledge-bases/{id}` | 删除知识库 |

### 文档管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/documents` | 获取文档列表 |
| POST | `/api/documents/upload` | 上传文档（支持批量） |
| GET | `/api/documents/{id}` | 获取文档详情 |
| GET | `/api/documents/{id}/parse-status` | 获取解析状态 |
| GET | `/api/documents/{id}/chunks/{index}` | 查看分块内容 |
| POST | `/api/documents/{id}/reparse` | 重新解析 |
| DELETE | `/api/documents/{id}` | 删除文档 |

### 对话接口
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送问题（支持流式） |
| GET | `/api/chat/history` | 获取对话历史 |
| GET | `/api/chat/conversations` | 获取会话列表 |
| POST | `/api/chat/conversations` | 创建会话 |
| GET | `/api/chat/conversations/{id}` | 获取会话详情 |
| PUT | `/api/chat/conversations/{id}` | 更新会话 |
| DELETE | `/api/chat/conversations/{id}` | 删除会话 |

### 管理接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/config` | 获取系统配置 |
| PUT | `/api/admin/config` | 更新系统配置 |
| GET | `/api/admin/stats` | 获取使用统计 |
| GET | `/api/admin/documents` | 获取所有文档 |
| GET | `/api/admin/conversations` | 获取所有会话 |

### 请求示例

**上传文档**
```bash
curl -X POST http://localhost:8080/api/documents/upload \
  -H "Authorization: Bearer rag-token-secret" \
  -F "files=@document.pdf" \
  -F "knowledge_base_id=1" \
  -F "chunk_strategy=token" \
  -F "chunk_size=512"
```

**发送问题（流式）**
```bash
curl -N http://localhost:8080/api/chat \
  -H "Authorization: Bearer rag-token-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是RAG？",
    "knowledge_base_id": 1,
    "stream": true,
    "top_k": 10
  }'
```

## 🎨 界面预览

### 智能问答界面
- 左侧对话历史列表，支持新建和切换会话
- 右侧聊天区域，支持流式输出
- 回答自动标注引用来源，点击可查看原文
- 每条回答显示质量评估指标（Faithfulness/Relevancy/Precision）
- 调试面板可查看检索各阶段的得分和详情

### 文档管理界面
- 文档列表展示所有文档的状态和元数据
- 上传弹窗支持选择分块策略和参数
- 解析状态实时追踪，显示进度条和预计剩余时间
- 分块预览可逐块查看内容和关键词

### 知识库管理界面
- 卡片式展示所有知识库
- 支持创建、重命名、删除知识库
- 一键切换当前使用的知识库

### 系统管理界面
- 使用统计面板展示核心指标
- 系统配置页面可调整 LLM、模型、分块、检索等参数
- 文档和对话的全局管理

## ⚙️ 配置说明

### LLM 配置
系统支持任何 OpenAI 兼容的 API 接口：

- **OpenAI**：
  ```env
  LLM_ENDPOINT=https://api.openai.com/v1
  LLM_API_KEY=sk-xxx
  LLM_MODEL=gpt-3.5-turbo
  ```

- **Ollama（本地）**：
  ```env
  LLM_ENDPOINT=http://localhost:11434/v1
  LLM_API_KEY=ollama
  LLM_MODEL=qwen2.5
  ```

- **OneAPI / 其他中转**：
  ```env
  LLM_ENDPOINT=https://your-oneapi-url/v1
  LLM_API_KEY=sk-xxx
  LLM_MODEL=qwen2.5-72b
  ```

### 分块策略选择

| 策略 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| 固定 Token | 通用场景 | 实现简单，块大小可控 | 可能切断语义 |
| 按段落 | 结构化文档 | 保留语义完整性 | 段落长度差异大 |
| 语义分割 | 长文档、专业内容 | 语义边界准确 | 计算成本高 |

### 检索参数调优

- `retrieval_top_k`：初始检索数量，建议 10-20
- `rerank_top_n`：重排序后返回数量，建议 3-5
- 增大 `top_k` 可提高召回率，但会增加计算量
- 重排序模型可以显著提升相关性，但会增加延迟

## 📝 使用流程

1. **创建知识库**：在"知识库管理"页面创建一个新的知识库
2. **上传文档**：在"文档管理"页面上传文档，选择分块策略
3. **等待解析**：文档会自动进行解析、分块、索引
4. **开始问答**：切换到"智能问答"页面，选择知识库后开始提问
5. **查看来源**：点击回答中的 [1][2] 标记可查看原文来源
6. **查看指标**：每条回答旁的指标图标显示质量评分
7. **调试检索**：点击"调试信息"查看各检索阶段的详细得分

## 🔒 安全说明

- API Token 用于接口认证，请妥善保管
- 生产环境请修改默认的 `API_TOKEN`
- 建议使用 HTTPS 部署
- 定期备份 PostgreSQL 和 Chroma 数据

## 🐛 常见问题

**Q: 模型下载慢怎么办？**
A: 首次启动会自动下载嵌入模型，可以设置国内镜像源：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

**Q: 内存不足怎么办？**
A: 可以减少同时加载的模型，或使用更小的模型：
```env
EMBEDDING_MODEL=all-MiniLM-L6-v2
CROSS_ENCODER_MODEL=cross-encoder/ms-marco-TinyBERT-L-2-v2
```

**Q: 如何支持更多文件格式？**
A: 在 `backend/app/services/document_parser.py` 中添加对应格式的解析器。

**Q: 如何添加新的分块策略？**
A: 在 `backend/app/services/chunking_service.py` 中实现新的分块方法。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📮 联系方式

如有问题或建议，欢迎提交 Issue。
