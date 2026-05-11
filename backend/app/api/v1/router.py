from fastapi import APIRouter

from app.api.v1.routes import (
    chat,
    github,
    health,
    knowledge,
    model_providers,
    projects,
    prompts,
    reviews,
    tasks,
    testgen,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(prompts.router, tags=["prompts"])
api_router.include_router(knowledge.router, tags=["knowledge"])
api_router.include_router(reviews.router, tags=["reviews"])
api_router.include_router(testgen.router, tags=["test-generation"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(github.router, tags=["github"])
api_router.include_router(model_providers.router, tags=["model-providers"])
api_router.include_router(tasks.router, tags=["tasks"])

