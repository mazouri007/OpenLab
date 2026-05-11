from pydantic import BaseModel


class PromptTemplateCreate(BaseModel):
    template_type: str
    name: str
    system_prompt: str
    user_prompt: str
    is_default: bool = False


class PromptTemplateRead(BaseModel):
    id: str
    template_type: str
    name: str
    version: int
    is_default: bool

    model_config = {"from_attributes": True}

