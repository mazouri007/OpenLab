# Lab AI Reviewer

面向实验室和小团队研发流程的 AI 代码审查与测试生成平台。项目包含 FastAPI 后端、React 管理台、Celery Worker、GitHub 接入骨架、RAG 知识库问答、会话记忆和多模型适配接口。

## 功能概览

- AI Code Review：支持代码片段、diff、GitHub PR 和 commit 输入。
- AI 单元测试生成：当前重点支持 Python `pytest` 和 Java `JUnit 5` 的生成流程骨架。
- 知识库问答：提供文档切片、检索、引用来源和项目级隔离能力。
- 会话记忆：包含短期摘要和长期偏好/背景记忆接口。
- GitHub 集成：包含仓库同步、PAT 配置、Webhook 入口和任务触发骨架。
- 多模型适配：通过 LangChain 模型层接入 OpenAI-Compatible 供应商，支持 Chat 与 Embedding 独立配置。
- 工作流编排：为 review、testgen、chat 预留 LangChain / LangGraph 扩展点。

## 技术栈

- 后端：FastAPI、SQLAlchemy 2.x、Alembic、Pydantic、Celery
- AI 编排：LangChain、LangGraph、langchain-openai
- 检索：SQLite chunk 表 + BM25 关键词召回 + 本地持久化 ChromaDB 向量索引
- 前端：React、TypeScript、Vite、Ant Design、TanStack Query
- 集成：GitHub REST / Webhook skeleton

## 目录结构

```text
backend/      后端 API、数据库模型、服务层和 agent 编排接口
frontend/     React + Vite 前端工作台
worker/       Celery worker 和后台任务入口
infra/env/    环境变量示例
docs/         架构、API、Prompt 设计文档
scripts/      本地开发启动脚本和演示数据脚本
```

## 环境要求

- Python 3.10 或更高版本
- Node.js 18 或更高版本
- npm
- Redis，可选，仅在运行 Celery worker 或异步任务时需要

## 快速启动

### 1. 配置后端环境变量

复制示例配置：

```powershell
Copy-Item infra\env\backend.env.example backend\.env
```

默认配置中 `ENABLE_MOCK_LLM=true`，可以在不接入真实大模型的情况下先启动和体验主要流程。接入真实模型时，按需设置 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_CHAT_MODEL`。如果聊天模型供应商不支持向量化，可额外设置 `LLM_EMBEDDING_BASE_URL`、`LLM_EMBEDDING_API_KEY` 和 `LLM_EMBEDDING_MODEL`。

`APP_SECRET_KEYS` 用于加密落库的模型 API Key。生产环境必须替换为安全生成的 Fernet key，可使用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成。

### 2. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
$env:PYTHONPATH = "$PWD"
alembic upgrade head
python -m uvicorn app.main:app --reload
```

如果你已有旧版本地 SQLite 且表结构已经存在，先执行 `alembic stamp head` 建立迁移基线；新库或清空后的库执行 `alembic upgrade head`。

后端默认地址：

- API: `http://127.0.0.1:8000/api/v1`
- Swagger 文档: `http://127.0.0.1:8000/docs`

也可以在项目根目录使用脚本启动：

```powershell
.\scripts\dev_backend.ps1
```

### 3. 配置并启动前端

```powershell
Copy-Item infra\env\frontend.env.example frontend\.env
cd frontend
npm install
npm run dev
```

前端默认地址通常为 `http://127.0.0.1:5173`。如果端口被占用，Vite 会自动提示新的端口。

也可以在项目根目录使用脚本启动：

```powershell
.\scripts\dev_frontend.ps1
```

### 4. 可选：启动 Celery Worker

先确保 Redis 正在运行，并且后端 `.env` 中的 `CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND` 配置可用。

```powershell
$env:PYTHONPATH = "$PWD;$PWD\backend"
celery -A worker.app.celery_app.celery_app worker --loglevel=info
```

## 常用命令

### 后端测试

```powershell
cd backend
pytest
```

### 数据迁移与运维

```powershell
cd backend
alembic upgrade head
cd ..
python scripts\encrypt_existing_model_keys.py
python scripts\rotate_model_key_encryption.py
python scripts\rebuild_chroma_index.py
```

### 后端代码检查

```powershell
cd backend
ruff check .
```

### 前端构建

```powershell
cd frontend
npm run build
```

### 预览前端构建产物

```powershell
cd frontend
npm run preview
```

## API 与文档

- API 设计：`docs/api-spec.md`
- 架构说明：`docs/architecture.md`
- Prompt 设计：`docs/prompt-design.md`
- 后端 OpenAPI：启动后访问 `http://127.0.0.1:8000/api/v1/openapi.json`

## 数据与配置说明

- 本地 SQLite 数据库默认为 `lab_ai_reviewer.db`，该文件不会提交到 Git。
- 本地 ChromaDB 向量索引默认为 `chroma_db/`，可通过 `CHROMA_PERSIST_DIRECTORY` 调整。
- `.env`、`.env.local`、虚拟环境、`node_modules`、构建产物和缓存目录已通过 `.gitignore` 排除。
- GitHub Webhook 本地调试时可使用 `GITHUB_WEBHOOK_SECRET=dev-secret`，生产环境必须替换为安全随机值。

## 当前状态

项目已完成第一版工程骨架，后端 REST API、数据库模型、服务层、GitHub/Webhook 接口、LangGraph 接口和前端工作台页面均已建立。部分 AI 调用、GitHub 拉取、检索和异步任务仍以占位实现为主，适合继续扩展为真实业务逻辑。
