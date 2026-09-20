from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.predictions import router as predictions_router
from app.api.greenhouses import router as greenhouses_router
from app.api.crop_batches import router as crop_batches_router
from app.api.sensors import router as sensors_router
from app.api.dashboard import router as dashboard_router
from app.api.warnings import router as warnings_router
from app.api.decisions import router as decisions_router
from app.api.diseases import router as diseases_router
from app.api.tasks import router as tasks_router
from app.api.ai import router as ai_router
from app.api.models import router as models_router
from app.api.sensor_ingest import router as sensor_ingest_router
from app.api.auth import router as auth_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(predictions_router)
api_router.include_router(greenhouses_router)
api_router.include_router(crop_batches_router)
api_router.include_router(sensors_router)
api_router.include_router(dashboard_router)
api_router.include_router(warnings_router)
api_router.include_router(decisions_router)
api_router.include_router(diseases_router)
api_router.include_router(tasks_router)
api_router.include_router(ai_router)
api_router.include_router(models_router)
api_router.include_router(sensor_ingest_router)
api_router.include_router(auth_router)
