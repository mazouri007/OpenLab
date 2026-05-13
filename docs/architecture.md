# Architecture

- FastAPI handles REST APIs, task creation, and project-level data isolation.
- LangChain/LangGraph entrypoints live under `backend/app/agents`.
- LangChain model providers keep chat generation and embedding generation as separate configs.
- Alembic owns schema migrations; application startup seeds demo data only after migrations exist.
- SQLite stores knowledge documents/chunks; local ChromaDB stores chunk embeddings for vector retrieval.
- Model provider API keys are encrypted at rest with Fernet keys from `APP_SECRET_KEYS`.
- React provides a lightweight workbench for review, test generation, chat, knowledge base, GitHub, and model settings.
