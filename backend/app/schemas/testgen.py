from typing import Literal

from pydantic import BaseModel, Field


class TestGenerationRequest(BaseModel):
    language: Literal["python", "java"]
    framework: str
    target_name: str
    code: str
    extra_requirements: str | None = None


class TestScenario(BaseModel):
    name: str
    case_type: Literal["happy_path", "edge_case", "exception"]
    description: str


class TestGenerationResultRead(BaseModel):
    test_code: str
    scenarios: list[TestScenario] = Field(default_factory=list)
    self_check_report: dict = Field(default_factory=dict)


class TestGenerationTaskRead(BaseModel):
    id: str
    language: str
    framework: str
    target_name: str
    status: str
    progress_stage: str
    error_message: str | None = None

    model_config = {"from_attributes": True}
