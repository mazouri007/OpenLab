# Architecture

- FastAPI handles REST APIs, task creation, and project-level data isolation.
- LangChain/LangGraph entrypoints live under `backend/app/agents`.
- SQLite + chunk tables support local development; PostgreSQL + pgvector is the deployment path.
- React provides a lightweight workbench for review, test generation, chat, knowledge base, GitHub, and model settings.

