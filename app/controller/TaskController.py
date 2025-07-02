from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException

from app.core.celery_app import celery

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}")
def get_task_status(task_id: str):
    """
    Get the status and result (if available) of a background task.
    """
    async_res = AsyncResult(task_id, app=celery)
    if async_res is None:
        raise HTTPException(status_code=404, detail="Task ID not found.")
    status = async_res.status  # e.g., PENDING, STARTED, SUCCESS, FAILURE
    result = None
    if async_res.successful():
        result = async_res.result  # this will be a summary dict or specified result
    elif async_res.failed():
        # Optionally include error info
        result = str(async_res.result)
    return {"task_id": task_id, "status": status, "result": result}
