"""Authorization is deterministic and is repeated when an approval resumes."""
from sqlalchemy import select
from app.models import Greenhouse, FarmTask, DiseaseRecognitionRecord, Intervention
from app.services.access import actor
from app.services.errors import ServiceError
from app.config import get_settings


def check(db, tool, args):
    user = actor()
    if tool.risk not in {"READ", "SOFTWARE_ACTION", "PHYSICAL_ACTION"}:
        raise ValueError("未知风险级别")
    if tool.risk != "READ" and user.role not in {"admin", "agronomist"}:
        raise ServiceError(403, "当前角色只能读取Agent证据")
    ids = []
    if hasattr(args, "greenhouse_id"):
        ids.append(args.greenhouse_id)
    for key, model in (("task_id", FarmTask), ("record_id", DiseaseRecognitionRecord), ("case_id", Intervention)):
        value = getattr(args, key, None)
        if value:
            item = db.scalar(select(model).where(model.id == value))
            if item is None:
                raise ValueError("资源不存在或不可访问")
            ids.append(item.greenhouse_id)
    for greenhouse_id in ids:
        greenhouse = db.scalar(select(Greenhouse).where(Greenhouse.id == greenhouse_id,
            Greenhouse.organization_id == user.organization_id))
        if greenhouse is None:
            raise ServiceError(403, "目标大棚不存在或不属于当前组织")
    if hasattr(args, "target_min"):
        limits = {"temperature": (-20, 60), "air_humidity": (0, 100),
                  "soil_moisture": (0, 100), "co2_concentration": (0, 10000)}
        lower, upper = limits[args.metric]
        if not lower <= args.target_min <= args.target_max <= upper:
            raise ValueError("目标范围超出该环境指标的有效范围")
    return tool.risk == "PHYSICAL_ACTION" or (
        tool.risk == "SOFTWARE_ACTION" and get_settings().agent_software_approval)
