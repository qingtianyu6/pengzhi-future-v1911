from fastapi import APIRouter, Depends
from app.services.access import business_access

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
from app.api.guest_ai import router as guest_ai_router
from app.api.agent import router as agent_router
from app.api.models import router as models_router
from app.api.sensor_ingest import router as sensor_ingest_router
from app.api.auth import router as auth_router
from app.api.interventions import router as interventions_router
from app.api.files import router as files_router
from app.api.cases import router as cases_router
from app.api.decision_support import router as decision_support_router
from app.api.v2_decision import (decision_router as v2_decision_router,
                                 evaluation_router as v2_evaluation_router,
                                 profile_router as v2_profile_router,
                                 risk_router as v2_risk_router,
                                 simulation_router as v2_simulation_router)


api_router = APIRouter()
protected = [Depends(business_access)]
api_router.include_router(health_router)
api_router.include_router(guest_ai_router)
api_router.include_router(predictions_router, dependencies=protected)
api_router.include_router(greenhouses_router, dependencies=protected)
api_router.include_router(crop_batches_router, dependencies=protected)
api_router.include_router(sensors_router, dependencies=protected)
api_router.include_router(dashboard_router, dependencies=protected)
api_router.include_router(warnings_router, dependencies=protected)
api_router.include_router(decisions_router, dependencies=protected)
api_router.include_router(diseases_router, dependencies=protected)
api_router.include_router(tasks_router, dependencies=protected)
api_router.include_router(ai_router, dependencies=protected)
api_router.include_router(agent_router, dependencies=protected)
api_router.include_router(models_router, dependencies=protected)
api_router.include_router(interventions_router, dependencies=protected)
api_router.include_router(files_router, dependencies=protected)
api_router.include_router(cases_router, dependencies=protected)
api_router.include_router(decision_support_router, dependencies=protected)
api_router.include_router(v2_risk_router, dependencies=protected)
api_router.include_router(v2_decision_router, dependencies=protected)
api_router.include_router(v2_simulation_router, dependencies=protected)
api_router.include_router(v2_evaluation_router, dependencies=protected)
api_router.include_router(v2_profile_router, dependencies=protected)
api_router.include_router(sensor_ingest_router)
api_router.include_router(auth_router)
