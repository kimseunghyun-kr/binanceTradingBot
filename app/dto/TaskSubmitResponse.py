from pydantic import BaseModel


class TaskSubmitResponse(BaseModel):
    task_id: str
    detail: str = "Task submitted"