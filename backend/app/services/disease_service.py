from __future__ import annotations

from hashlib import sha256
import io
from pathlib import Path
import uuid
import warnings

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.ml.disease.config import CLASS_NAMES, MODEL_VERSION
from app.ml.disease.inference import get_disease_predictor
from app.models.crop_batch import CropBatch
from app.models.disease_recognition_record import DiseaseRecognitionRecord
from app.models.greenhouse import Greenhouse
from app.schemas.common import PaginatedData
from app.schemas.disease import DiseaseIdentification, DiseaseRecordData, DiseaseReviewRequest
from app.services.errors import ServiceError


UPLOAD_DIR = BACKEND_DIR / "uploads" / "disease"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 50_000_000
ALLOWED_EXTENSIONS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
LIMITATIONS = ["仅支持番茄六分类叶片辅助识别", "模型仍处于公开数据集评估阶段",
               "非番茄、非叶片或目标类别以外图像可能产生不可靠结果"]
SAFETY_NOTICE = "识别结果仅供辅助参考，不能替代农技人员或植物病理专家诊断；系统不提供自动施药、剂量或设备控制。"


def _public_recognition_status(record: DiseaseRecognitionRecord) -> str:
    """兼容旧记录的 recognized，同时按候选模型状态对外要求人工复核。"""
    if record.recognition_status == "recognized" and record.model_status == "under_evaluation":
        return "review_required"
    return record.recognition_status


def _record_data(record: DiseaseRecognitionRecord) -> DiseaseRecordData:
    return DiseaseRecordData(
        id=record.id, greenhouse_id=record.greenhouse_id, crop_batch_id=record.crop_batch_id,
        crop_type=record.crop_type, image_path=record.image_path, image_sha256=record.image_sha256,
        original_filename=record.original_filename, predicted_class=record.predicted_class,
        predicted_class_name=record.predicted_class_name, confidence=record.confidence,
        top3_predictions=record.top3_json or [], recognition_status=_public_recognition_status(record),
        model_version=record.model_version, model_status=record.model_status,
        validation_status=("under_evaluation" if record.model_status == "under_evaluation"
                           else "validated_on_public_dataset" if record.model_status == "ready"
                           else "not_validated"),
        local_calibration_status=record.local_calibration_status, review_status=record.review_status,
        reviewed_class=record.reviewed_class, review_note=record.review_note,
        created_at=record.created_at, updated_at=record.updated_at,
    )


def model_status() -> dict:
    payload = get_disease_predictor().status()
    status = payload.get("model_status")
    payload["validation_status"] = (
        "under_evaluation" if status == "under_evaluation"
        else "validated_on_public_dataset" if status == "ready"
        else "not_validated"
    )
    payload["limitations"] = LIMITATIONS
    return payload


def _validate_context(db: Session, greenhouse_id: int, crop_batch_id: int) -> CropBatch:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    batch = db.get(CropBatch, crop_batch_id)
    if batch is None or batch.greenhouse_id != greenhouse_id:
        raise ServiceError(404, "该大棚下不存在指定种植批次")
    if batch.crop_type != "tomato":
        raise ServiceError(422, f"当前番茄病害模型不支持作物类型 {batch.crop_type}，未调用模型")
    return batch


def _decode_image(content: bytes, original_filename: str, content_type: str | None) -> Image.Image:
    if not content:
        raise ServiceError(422, "上传文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ServiceError(413, "图片大小不能超过10MB")
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ServiceError(415, "仅支持 JPG、JPEG、PNG 和 WEBP 图片")
    if content_type not in ALLOWED_MIME:
        raise ServiceError(415, "上传文件的 MIME 类型不是受支持的图片类型")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as probe:
                probe.verify()
            image = Image.open(io.BytesIO(content))
            image.load()
            if image.width * image.height > MAX_PIXELS:
                raise ServiceError(413, "图片像素过大")
            if image.format != ALLOWED_EXTENSIONS[suffix]:
                raise ServiceError(415, "文件扩展名与图片真实格式不一致")
            return image.convert("RGB")
    except ServiceError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ServiceError(422, "图片损坏或无法安全解码") from exc


def identify(db: Session, *, greenhouse_id: int, crop_batch_id: int, content: bytes,
             original_filename: str, content_type: str | None) -> DiseaseIdentification:
    batch = _validate_context(db, greenhouse_id, crop_batch_id)
    image = _decode_image(content, original_filename, content_type)
    image_hash = sha256(content).hexdigest()
    duplicate = db.scalar(select(DiseaseRecognitionRecord).where(
        DiseaseRecognitionRecord.image_sha256 == image_hash).order_by(DiseaseRecognitionRecord.id))
    duplicate_disk_path = (UPLOAD_DIR / Path(duplicate.image_path).name) if duplicate else None
    if duplicate and duplicate_disk_path and duplicate_disk_path.exists():
        relative_path = duplicate.image_path
    else:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / f"{uuid.uuid4().hex}.jpg"
        image.save(path, format="JPEG", quality=92, optimize=True, exif=b"")
        relative_path = f"uploads/disease/{path.name}"
    predictor = get_disease_predictor()
    prediction = predictor.predict(image)
    record = DiseaseRecognitionRecord(
        greenhouse_id=greenhouse_id, crop_batch_id=crop_batch_id, crop_type=batch.crop_type,
        image_path=relative_path, image_sha256=image_hash,
        original_filename=Path(original_filename).name[:255] or "upload",
        predicted_class=prediction.get("predicted_class"),
        predicted_class_name=prediction.get("predicted_class_name"),
        confidence=prediction.get("confidence"), top3_json=prediction.get("top3_predictions", []),
        # 旧开发库的 CheckConstraint 仅允许 recognized；对外状态由 model_status 稳定映射为
        # review_required，避免破坏性重建既有 SQLite 表。
        recognition_status=("recognized" if prediction["recognition_status"] == "review_required"
                            else prediction["recognition_status"]), model_version=MODEL_VERSION,
        model_status=predictor.model_status, local_calibration_status="not_calibrated",
        review_status="unreviewed",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return DiseaseIdentification(
        record_id=record.id, recognition_status=_public_recognition_status(record),
        predicted_class=record.predicted_class, predicted_class_name=record.predicted_class_name,
        confidence=record.confidence, top3_predictions=record.top3_json or [], model_version=MODEL_VERSION,
        validation_status=("under_evaluation" if predictor.model_status == "under_evaluation"
                           else "validated_on_public_dataset" if predictor.model_status == "ready"
                           else "not_validated"),
        limitations=LIMITATIONS, safety_notice=SAFETY_NOTICE, duplicate_image=duplicate is not None,
    )


def list_records(db: Session, *, page: int, page_size: int, greenhouse_id: int | None = None,
                 recognition_status: str | None = None, review_status: str | None = None) -> PaginatedData[DiseaseRecordData]:
    query = select(DiseaseRecognitionRecord)
    if greenhouse_id is not None:
        query = query.where(DiseaseRecognitionRecord.greenhouse_id == greenhouse_id)
    if recognition_status:
        if recognition_status == "review_required":
            query = query.where(DiseaseRecognitionRecord.recognition_status == "recognized",
                                DiseaseRecognitionRecord.model_status == "under_evaluation")
        else:
            query = query.where(DiseaseRecognitionRecord.recognition_status == recognition_status)
    if review_status:
        query = query.where(DiseaseRecognitionRecord.review_status == review_status)
    records = list(db.scalars(query.order_by(DiseaseRecognitionRecord.created_at.desc(),
                                             DiseaseRecognitionRecord.id.desc())).all())
    start = (page - 1) * page_size
    return PaginatedData(items=[_record_data(record) for record in records[start:start + page_size]],
                         total=len(records), page=page, page_size=page_size)


def get_record(db: Session, record_id: int) -> DiseaseRecordData:
    record = db.get(DiseaseRecognitionRecord, record_id)
    if record is None:
        raise ServiceError(404, "识别记录不存在")
    return _record_data(record)


def review_record(db: Session, record_id: int, payload: DiseaseReviewRequest) -> DiseaseRecordData:
    record = db.get(DiseaseRecognitionRecord, record_id)
    if record is None:
        raise ServiceError(404, "识别记录不存在")
    if payload.reviewed_class and payload.reviewed_class not in CLASS_NAMES:
        raise ServiceError(422, "人工修正类别不在番茄六分类范围内")
    if payload.review_status == "confirmed" and _public_recognition_status(record) not in {
        "recognized", "review_required"
    }:
        raise ServiceError(422, "低置信度或模型不可用记录不能直接确认，请修正或拒绝")
    record.review_status = payload.review_status
    record.reviewed_class = (record.predicted_class if payload.review_status == "confirmed"
                             else payload.reviewed_class if payload.review_status == "corrected" else None)
    record.review_note = payload.review_note
    db.commit()
    db.refresh(record)
    return _record_data(record)
