"""Small typed registry; handlers are adapters to existing business services."""
from dataclasses import dataclass
from typing import Literal, Callable, Any

from pydantic import BaseModel, ConfigDict, Field

from app.services import sensor_service, prediction_service, warning_service, task_service, case_service
from app.services import greenhouse_service, disease_service
from app.services.knowledge_service import search_knowledge
from app.schemas.task import ManualTaskCreate, VersionedAction, AssignTaskRequest, CompleteTaskRequest
from app.services.access import actor
from app.models import CropBatch
from sqlalchemy import select
from fastapi.encoders import jsonable_encoder


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class GreenhouseArgs(Args):
    greenhouse_id: int = Field(gt=0)


class ListArgs(Args):
    keyword: str = Field(default="", max_length=100)
    page: int = Field(default=1, ge=1, le=1000)


class HistoryArgs(GreenhouseArgs):
    hours: int = Field(default=24, ge=1, le=168)


class QueryArgs(Args):
    query: str = Field(min_length=1, max_length=500)


class CaseSearchArgs(GreenhouseArgs):
    warning_id: int | None = Field(default=None, gt=0)


class CaseArgs(Args):
    case_id: int = Field(gt=0)


class DiseaseArgs(Args):
    record_id: int = Field(gt=0)


class CreateTaskArgs(GreenhouseArgs):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=3000)
    action_type: Literal["ventilation_check", "shading_check", "heating_check", "humidity_control",
                         "condensation_inspection", "irrigation_check", "sensor_inspection",
                         "manual_observation", "expert_review", "field_inspection", "sample_collection", "isolation_check"]
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    planned_start_at: str | None = None
    due_at: str | None = None


class UpdateTaskArgs(Args):
    task_id: int = Field(gt=0)
    version: int = Field(ge=1)
    operation: Literal["submit", "assign"]
    assignee_name: str | None = Field(default=None, max_length=60)


class CloseTaskArgs(Args):
    task_id: int = Field(gt=0)
    version: int = Field(ge=1)


class RecheckArgs(GreenhouseArgs):
    task_id: int = Field(gt=0)
    minutes: int = Field(default=30, ge=1, le=10080)
    metric: Literal["temperature", "air_humidity", "soil_moisture", "co2_concentration"] = "temperature"
    target_min: float = Field(ge=-20, le=10000)
    target_max: float = Field(ge=-20, le=10000)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: type[Args]
    risk: str
    handler: Callable

    def definition(self):
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                    "parameters": self.schema.model_json_schema()}}


REGISTRY: dict[str, Tool] = {}


def register(name, description, schema, risk="READ"):
    def wrap(fn):
        REGISTRY[name] = Tool(name, description, schema, risk, fn)
        return fn
    return wrap


def compact(value):
    return jsonable_encoder(value)


@register("list_greenhouses", "列出可访问的大棚，支持名称/编号搜索与分页；返回真实ID。", ListArgs)
def greenhouses(db, run, args):
    page = greenhouse_service.list_greenhouses(db, args.page, 30, None, args.keyword or None)
    return {"items": [{"id": i.id, "name": i.name, "code": i.code} for i in page.items],
            "total": page.total, "page": args.page}


@register("get_current_environment", "读取最新环境及时间、质量、来源；没有数据时明确返回空。", GreenhouseArgs)
def environment(db, run, args):
    return {"reading": compact(sensor_service.get_latest(db, args.greenhouse_id))}


@register("get_environment_history", "读取最近1至168小时环境历史，最多返回24个真实样本。", HistoryArgs)
def history(db, run, args):
    from datetime import datetime, UTC, timedelta
    end = datetime.now(UTC)
    result = sensor_service.get_history(db, args.greenhouse_id, end - timedelta(hours=args.hours), end, 1, 24)
    return compact(result)


@register("get_future_prediction", "调用现有六小时预测服务，保留模型状态与数据不足提示。", GreenhouseArgs)
def prediction(db, run, args):
    return compact(prediction_service.predict_environment(db, args.greenhouse_id, 6))


@register("get_active_warnings", "读取活动预警；open和acknowledged均为活动状态。", GreenhouseArgs)
def warnings(db, run, args):
    items = []
    for status in ("open", "acknowledged"):
        result = warning_service.list_warnings(db, greenhouse_id=args.greenhouse_id, severity=None,
            status=status, warning_type=None, start_time=None, end_time=None, page=1, page_size=10)
        items.extend(compact(result.items))
    return {"items": items}


@register("get_risk_summary", "按现有作物和生育期规则计算当前风险分数，用于大棚风险比较。", GreenhouseArgs)
def risk(db, run, args):
    from app.services.risk_service import assess_current_risk
    batch = db.scalar(select(CropBatch).where(CropBatch.greenhouse_id == args.greenhouse_id, CropBatch.status == "growing").limit(1))
    return compact(assess_current_risk(sensor_service.get_latest(db, args.greenhouse_id),
        batch.growth_stage if batch else None, batch.crop_type if batch else "tomato"))


@register("search_agriculture_knowledge", "检索现有本地农业知识库并返回来源。", QueryArgs)
def knowledge(db, run, args):
    return {"items": search_knowledge(args.query, limit=4)}


@register("search_similar_cases", "有预警ID时调用现有相似案例算法，否则列出该棚最近案例；两者明确区分。", CaseSearchArgs)
def cases(db, run, args):
    if args.warning_id:
        from app.models import WarningEvent
        warning = db.get(WarningEvent, args.warning_id)
        if warning is None or warning.greenhouse_id != args.greenhouse_id:
            raise ValueError("预警不属于目标大棚")
        return compact(case_service.get_similar_cases(db, args.warning_id, top_k=5))
    return {"mode": "recent_not_similarity_ranked",
            **compact(case_service.list_cases(db, args.greenhouse_id, 1, 5)),
            "task_cases": case_service.list_task_case_memories(db, args.greenhouse_id)}


@register("get_case_detail", "读取现有处置案例的情况、决策、执行和结果。", CaseArgs)
def case_detail(db, run, args):
    return compact(case_service.get_case(db, args.case_id))


@register("diagnose_crop_image", "读取已通过现有病害上传接口识别的图片记录；不接受虚构图片或路径。", DiseaseArgs)
def disease(db, run, args):
    return compact(disease_service.get_record(db, args.record_id))


@register("get_farm_tasks", "读取最近农事任务及状态、版本、执行人和日期。", GreenhouseArgs)
def tasks(db, run, args):
    result = task_service.list_tasks(db, greenhouse_id=args.greenhouse_id, crop_batch_id=None,
        source_type=None, status=None, priority=None, assignee_name=None, start_time=None,
        end_time=None, page=1, page_size=20)
    return {"total": result.total, "items": [{k: compact(t)[k] for k in (
        "id", "title", "status", "version", "priority", "assignee_name", "due_at")} for t in result.items]}


def make_task(db, run, args, submit):
    payload = ManualTaskCreate.model_validate({**args.model_dump(), "created_by": actor().display_name})
    task = task_service.create_manual_task(db, payload)
    if submit:
        task = task_service.submit_task(db, task.id, VersionedAction(version=task.version, operator=actor().display_name))
    return {k: compact(task)[k] for k in ("id", "title", "status", "version", "requires_manual_confirmation", "safety_note")}


@register("create_task_draft", "通过现有任务服务建立人工操作草稿。不会操作设备。", CreateTaskArgs, "SOFTWARE_ACTION")
def draft(db, run, args):
    return make_task(db, run, args, False)


@register("create_farm_task", "建立并提交待执行人工农事任务；不代表任务已执行。", CreateTaskArgs, "SOFTWARE_ACTION")
def create_task(db, run, args):
    return make_task(db, run, args, True)


@register("update_farm_task", "按版本提交或分配任务；不得声称已执行现场操作。", UpdateTaskArgs, "SOFTWARE_ACTION")
def update_task(db, run, args):
    payload = {"version": args.version, "operator": actor().display_name}
    if args.operation == "submit":
        result = task_service.submit_task(db, args.task_id, VersionedAction(**payload))
    else:
        result = task_service.assign_task(db, args.task_id, AssignTaskRequest(**payload, assignee_name=args.assignee_name))
    return compact(result)


@register("close_farm_task", "仅在复查已达标且人工已开始执行任务时记录环境结果并完成任务。", CloseTaskArgs, "SOFTWARE_ACTION")
def close_task(db, run, args):
    from app.models import AgentRecheck
    from datetime import datetime, UTC
    check = db.scalar(select(AgentRecheck).where(AgentRecheck.run_id == run.id,
        AgentRecheck.task_id == args.task_id, AgentRecheck.status == "completed").order_by(AgentRecheck.id.desc()))
    if not check or not check.evaluation_json.get("achieved"):
        raise ValueError("没有该任务的达标复查证据")
    task = task_service.get_task_detail(db, args.task_id)
    if task.status != "in_progress":
        raise ValueError("任务尚未由人员开始执行，不能自动宣称完成")
    return compact(task_service.complete_task(db, args.task_id, CompleteTaskRequest(
        version=args.version, operator=actor().display_name, executed_at=datetime.now(UTC),
        result_type="resolved", execution_note="Agent复查记录环境目标达标；不证明操作因果关系。",
        observed_change=str(check.evaluation_json))))


@register("schedule_recheck", "持久化指定任务的复查，目标范围必须明确；到期读取新数据并恢复同一run。", RecheckArgs, "SOFTWARE_ACTION")
def recheck(db, run, args):
    from app.agent.scheduler import schedule
    return schedule(db, run, args)


@register("save_case_memory", "把已达标的任务复查作为情况→决策→行动→结果存入案例记忆；优先复用现有处置案例。", CloseTaskArgs, "SOFTWARE_ACTION")
def memory(db, run, args):
    from app.agent.memory import save_case
    return save_case(db, run, args.task_id)


@register("generate_greenhouse_report", "汇总已读取的当前运行证据，生成可审计的大棚报告。", GreenhouseArgs, "SOFTWARE_ACTION")
def report(db, run, args):
    return {"greenhouse_id": args.greenhouse_id, "goal": run.goal,
            "observations": [item for item in run.context_json.get("observations", [])
                             if item.get("arguments", {}).get("greenhouse_id") == args.greenhouse_id][-12:]}
