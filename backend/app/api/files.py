from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.database import get_db
from app.models import DiseaseRecognitionRecord, FarmTask, TaskFeedback
from app.services.errors import ServiceError


router = APIRouter(prefix="/files", tags=["受控附件"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/{relative_path:path}", response_class=FileResponse)
def get_file(relative_path: str, db: Database):
    parts = Path(relative_path).parts
    if len(parts) < 3 or parts[0] != "uploads" or any(part in {"..", "."} for part in parts):
        raise ServiceError(404, "文件不存在")
    allowed = False
    if len(parts) == 4 and parts[1] == "tasks":
        task = db.scalar(select(FarmTask).where(FarmTask.task_code == parts[2]))
        if task:
            feedbacks = db.scalars(select(TaskFeedback).where(TaskFeedback.task_id == task.id))
            allowed = any(relative_path in row.attachment_paths_json for row in feedbacks)
    elif len(parts) == 3 and parts[1] == "disease":
        allowed = db.scalar(select(DiseaseRecognitionRecord.id).where(
            DiseaseRecognitionRecord.image_path == relative_path)) is not None
    path = (BACKEND_DIR / relative_path).resolve()
    if not allowed or not path.is_relative_to((BACKEND_DIR / "uploads").resolve()) or not path.is_file():
        raise ServiceError(404, "文件不存在")
    return FileResponse(path)
