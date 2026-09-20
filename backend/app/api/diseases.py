from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.disease import (DiseaseIdentification, DiseaseModelStatus, DiseaseRecordData,
                                 DiseaseReviewRequest)
from app.services import disease_service


router = APIRouter(prefix="/diseases", tags=["番茄病害辅助识别"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/model-status", response_model=ApiResponse[DiseaseModelStatus], summary="获取病害模型状态")
def get_model_status() -> ApiResponse[DiseaseModelStatus]:
    return ApiResponse(data=DiseaseModelStatus.model_validate(disease_service.model_status()))


@router.post("/identify", response_model=ApiResponse[DiseaseIdentification], summary="上传番茄叶片图片辅助识别")
async def identify_disease(
    db: Database,
    greenhouse_id: Annotated[int, Form(gt=0)],
    crop_batch_id: Annotated[int, Form(gt=0)],
    image: Annotated[UploadFile, File(description="JPG/JPEG/PNG/WEBP，最大10MB")],
) -> ApiResponse[DiseaseIdentification]:
    content = await image.read(disease_service.MAX_UPLOAD_BYTES + 1)
    await image.close()
    result = disease_service.identify(
        db, greenhouse_id=greenhouse_id, crop_batch_id=crop_batch_id, content=content,
        original_filename=image.filename or "upload", content_type=image.content_type,
    )
    return ApiResponse(message="模型候选结果已生成，请完成人工复核", data=result)


@router.get("/records", response_model=ApiResponse[PaginatedData[DiseaseRecordData]], summary="分页查询识别历史")
def list_disease_records(
    db: Database, page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    greenhouse_id: int | None = None, recognition_status: str | None = None,
    review_status: str | None = None,
) -> ApiResponse[PaginatedData[DiseaseRecordData]]:
    return ApiResponse(data=disease_service.list_records(
        db, page=page, page_size=page_size, greenhouse_id=greenhouse_id,
        recognition_status=recognition_status, review_status=review_status,
    ))


@router.get("/records/{record_id}", response_model=ApiResponse[DiseaseRecordData], summary="获取识别记录详情")
def get_disease_record(record_id: int, db: Database) -> ApiResponse[DiseaseRecordData]:
    return ApiResponse(data=disease_service.get_record(db, record_id))


@router.post("/records/{record_id}/review", response_model=ApiResponse[DiseaseRecordData], summary="人工确认、修正或拒绝")
def review_disease_record(record_id: int, payload: DiseaseReviewRequest,
                          db: Database) -> ApiResponse[DiseaseRecordData]:
    return ApiResponse(message="人工审核已保存", data=disease_service.review_record(db, record_id, payload))
