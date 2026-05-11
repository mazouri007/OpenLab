from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=200)
    description: str | None = None
    primary_language: str = "python"


class ProjectRead(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    primary_language: str

    model_config = {"from_attributes": True}

