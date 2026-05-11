from pydantic import BaseModel


class TaskStatusRead(BaseModel):
    id: str
    task_type: str
    status: str
    progress_stage: str = ""
    error_message: str | None = None
    updated_at: str | None = None
