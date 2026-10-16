from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import BACKEND_DIR, get_settings
from app.database import initialize_database
from app.exceptions import register_exception_handlers


settings = get_settings()
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    import asyncio
    from app.agent.scheduler import worker, recover_interrupted
    recover_interrupted()
    scheduler_task = asyncio.create_task(worker())
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="棚智未来——面向设施农业的智能监测、环境预测、风险预警、病害辅助识别与农事决策平台 API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")
if (FRONTEND_DIST / "assistant").is_dir():
    app.mount("/assistant", StaticFiles(directory=FRONTEND_DIST / "assistant"), name="assistant-assets")
register_exception_handlers(app)


@app.get("/", include_in_schema=False)
def root():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"message": "棚智未来 API 正在运行", "docs": "/docs"}


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_route(full_path: str):
    """生产环境下由 FastAPI 托管前端，并为浏览器路由回退到 index.html。"""
    if not FRONTEND_DIST.is_dir():
        return {"message": "棚智未来 API 正在运行", "docs": "/docs"}

    requested = (FRONTEND_DIST / full_path).resolve()
    try:
        requested.relative_to(FRONTEND_DIST.resolve())
    except ValueError:
        return FileResponse(FRONTEND_DIST / "index.html")

    if requested.is_file():
        return FileResponse(requested)
    return FileResponse(FRONTEND_DIST / "index.html")
