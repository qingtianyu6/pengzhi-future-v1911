from typing import Annotated, Literal
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.models.community import AIEvaluationRun, AutomationJob, KnowledgeDocument, NewsArticle, NewsBookmark, NewsDigest, NewsSource
from app.schemas.common import ApiResponse
from app.schemas.community import AssistRequest, CommentWrite, EvaluationRequest, ModerationWrite, PostWrite, PreferenceWrite, ReportWrite, ResearchLink, SourceWrite
from app.schemas.community import ReactionWrite, BookmarkWrite, ReviewWrite
from app.services import ai_evaluation_service as evaluations, document_service, forum_service as forum, news_service as news
from app.services.access import actor, require_role
from app.services.errors import ServiceError

router = APIRouter(prefix="/community", tags=["棚友论坛与农业知识服务"])
public_router = APIRouter(prefix="/community-public", tags=["公开农业参考资料"])
Database = Annotated[Session, Depends(get_db)]

@public_router.get("/knowledge")
def public_knowledge(q: str = Query("", max_length=500), crop: str | None = None, stage: str | None = None):
    from app.services.knowledge_service import search_knowledge
    return ApiResponse(data={"items":search_knowledge(q, limit=100, crop=crop, stage=stage),
        "method":"public_curated_reference", "notice":"平台内置参考资料，保留出处，不能替代现场核验；不含组织上传文档"})

@router.get("/forum/posts")
def posts(db: Database, q: str = Query("", max_length=200), category: str = "", crop: str = "", tag: str = "", mine: str = "", page: int = Query(1, ge=1), answer: Literal["all","open","resolved"] = "all", sort: Literal["recent","discussed","liked"] = "recent"):
    return ApiResponse(data=forum.list_posts(db, q, category, crop, tag, mine, page, answer, sort))

@router.post("/forum/posts", status_code=201)
def create_post(payload: PostWrite, db: Database):
    return ApiResponse(data=forum.write_post(db, payload))

@router.get("/forum/posts/{post_id}")
def post_detail(post_id: int, db: Database):
    return ApiResponse(data=forum.data(db, forum.get_post(db, post_id), True))

@router.put("/forum/posts/{post_id}")
def edit_post(post_id: int, payload: PostWrite, db: Database):
    return ApiResponse(data=forum.write_post(db, payload, post_id))

@router.delete("/forum/posts/{post_id}")
def delete_post(post_id: int, db: Database):
    return ApiResponse(data=forum.delete_post(db, post_id))

@router.post("/forum/posts/{post_id}/comments", status_code=201)
def comment(post_id: int, payload: CommentWrite, db: Database):
    return ApiResponse(data=forum.comment(db, post_id, payload))

@router.delete("/forum/posts/{post_id}/comments/{comment_id}")
def delete_comment(post_id: int, comment_id: int, db: Database):
    return ApiResponse(data=forum.delete_comment(db, post_id, comment_id))

@router.put("/forum/posts/{post_id}/accepted/{comment_id}")
def accept(post_id: int, comment_id: int, db: Database):
    return ApiResponse(data=forum.accept(db, post_id, comment_id))

@router.put("/forum/posts/{post_id}/reactions/{kind}")
def react(post_id: int, kind: Literal["like", "bookmark"], db: Database, payload: ReactionWrite):
    return ApiResponse(data=forum.react(db, post_id, kind, payload.enabled))

@router.post("/forum/posts/{post_id}/reports")
def report(post_id: int, payload: ReportWrite, db: Database):
    return ApiResponse(data=forum.report(db, post_id, payload.reason))

@router.get("/forum/moderation/reports")
def reports(db: Database):
    return ApiResponse(data=forum.reports(db))

@router.post("/forum/posts/{post_id}/moderation")
def moderate(post_id: int, payload: ModerationWrite, db: Database):
    return ApiResponse(data=forum.moderate(db, post_id, payload))

@router.post("/forum/posts/{post_id}/research")
def research(post_id: int, payload: ResearchLink, db: Database):
    return ApiResponse(data=forum.create_research(db, post_id, payload))

@router.post("/forum/posts/{post_id}/assist")
async def assist(post_id: int, payload: AssistRequest, db: Database):
    return ApiResponse(data=await forum.assist(db, post_id, payload.use_model))

@router.post("/forum/assets", status_code=201)
async def upload_asset(db: Database, file: UploadFile = File()):
    content = await file.read(8*1024*1024+1)
    return ApiResponse(data=forum.upload(db, file.filename, content, file.content_type))

@router.get("/forum/assets/{asset_id}")
def get_asset(asset_id: int, db: Database):
    row, path = forum.asset(db, asset_id)
    return FileResponse(path, media_type=row.media_type, filename=row.filename,
        content_disposition_type="inline" if row.media_type.startswith("image/") else "attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})

@router.get("/news/sources")
def sources(db: Database):
    return ApiResponse(data=[news.source_data(s) for s in db.scalars(select(NewsSource).where(NewsSource.organization_id == actor().organization_id).order_by(NewsSource.id))])

from app.services.news_automation import AutomationWrite,SetupWrite

@public_router.get("/news/source-catalog")
def news_source_catalog():
    from app.services.news_automation import CATALOG
    return ApiResponse(data=CATALOG)

@public_router.get("/news/public-headlines")
def public_chinese_news():
    from app.services.chinese_news import public_headlines
    return ApiResponse(data=public_headlines())

@public_router.get("/news/article-image")
def public_news_image(url: str = Query(..., max_length=2048)):
    from app.services.news_images import article_image
    return ApiResponse(data=article_image(url, official=True))

@router.get("/news/automation")
def news_automation_status(db:Database):
    from app.services.news_automation import settings_data
    return ApiResponse(data=settings_data(db,actor().organization_id))

@router.put("/news/automation")
def update_news_automation(payload:AutomationWrite,db:Database):
    from app.services.news_automation import save_settings
    return ApiResponse(data=save_settings(db,payload))

@router.post("/news/automation/setup")
def setup_news_automation(payload:SetupWrite,db:Database):
    from app.services.news_automation import setup
    return ApiResponse(data=setup(db,payload))

@router.post("/news/automation/run")
async def run_news_automation(db:Database):
    from app.services.news_automation import run_now
    return ApiResponse(data=await run_now(db))

@router.post("/news/sources", status_code=201)
def source(payload: SourceWrite, db: Database):
    return ApiResponse(data=news.save_source(db, payload))

@router.put("/news/sources/{source_id}")
def edit_source(source_id: int, payload: SourceWrite, db: Database):
    return ApiResponse(data=news.save_source(db, payload, source_id))

@router.post("/news/sources/{source_id}/refresh")
def refresh_source(source_id: int, db: Database):
    require_role("admin", "agronomist")
    return ApiResponse(data=news.collect(db, news.get_source(db, source_id), force=True))

@router.get("/news/articles")
def articles(db: Database, q: str = Query("", max_length=200), tag: str = "", bookmarks: bool = False, page: int = Query(1, ge=1), source_id: int | None = Query(None,gt=0), read_status: Literal["all","unread","read"] = "all", theme: Literal["all","facility","cultivation","disease","policy"] = "all", sort: Literal["published","collected"] = "collected", following: bool = False):
    from sqlalchemy import func, exists
    query = select(NewsArticle).where(NewsArticle.organization_id == actor().organization_id,NewsArticle.status != "not_relevant")
    if q: query = query.where(NewsArticle.title.icontains(q, autoescape=True))
    if tag:
        tags=func.json_each(NewsArticle.tags).table_valued("key","value")
        query=query.where(exists(select(1).select_from(tags).where(tags.c.value==tag)))
    if theme != "all":
        theme_words = {"facility": ["温室", "大棚", "设施", "greenhouse"],
            "cultivation": ["栽培", "种植", "育苗", "授粉", "水肥", "灌溉", "cultivation"],
            "disease": ["病害", "虫害", "病虫", "防治", "防控", "disease"],
            "policy": ["政策", "通知", "意见", "规划", "部署", "policy"]}
        theme_tags = func.json_each(NewsArticle.tags).table_valued("key", "value")
        query = query.where(or_(exists(select(1).select_from(theme_tags).where(theme_tags.c.value == theme)),
            *[NewsArticle.title.icontains(word, autoescape=True) | NewsArticle.summary.icontains(word, autoescape=True) for word in theme_words[theme]]))
    if following:
        pref = news.preference(db)
        wanted = list(set((pref.crops or []) + (pref.topics or [])))
        if wanted:
            followed_tags = func.json_each(NewsArticle.tags).table_valued("key", "value")
            query = query.where(exists(select(1).select_from(followed_tags).where(followed_tags.c.value.in_(wanted))))
    if source_id: query = query.where(NewsArticle.source_id == source_id)
    read_ids=select(NewsBookmark.article_id).where(NewsBookmark.user_id==actor().id,NewsBookmark.read_at.is_not(None))
    if read_status == "read": query = query.where(NewsArticle.id.in_(read_ids))
    if read_status == "unread": query = query.where(NewsArticle.id.not_in(read_ids))
    if bookmarks: query = query.where(NewsArticle.id.in_(select(NewsBookmark.article_id).where(NewsBookmark.user_id == actor().id, NewsBookmark.bookmarked.is_(True))))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return ApiResponse(data={"items": [news.article_data(db, a) for a in db.scalars(query.order_by((func.coalesce(NewsArticle.published_at, NewsArticle.collected_at) if sort == "published" else NewsArticle.collected_at).desc(), NewsArticle.id.desc()).offset((page-1)*20).limit(20))], "total": total, "page": page})

@router.post("/news/bookmarks/batch-read")
def batch_read_articles(db: Database, payload: dict):
    ids=payload.get("article_ids")
    if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(type(i) is not int or i<=0 for i in ids):
        raise ServiceError(422,"请选择1至100条有效资讯")
    ids=set(ids)
    rows=list(db.scalars(select(NewsArticle).where(NewsArticle.id.in_(ids),NewsArticle.organization_id==actor().organization_id)))
    if len(rows)!=len(ids): raise ServiceError(404,"部分资讯不存在或不可访问，未更新已读状态")
    for a in rows:
        mark=db.scalar(select(NewsBookmark).where(NewsBookmark.user_id==actor().id,NewsBookmark.article_id==a.id))
        if not mark:
            from sqlalchemy.exc import IntegrityError
            try:
                with db.begin_nested():
                    mark=NewsBookmark(user_id=actor().id,article_id=a.id);db.add(mark);db.flush()
            except IntegrityError:
                mark=db.scalar(select(NewsBookmark).where(NewsBookmark.user_id==actor().id,NewsBookmark.article_id==a.id))
        if not mark.read_at: mark.read_at=datetime.now(UTC)
    db.commit()
    return ApiResponse(data={"marked":len(rows)})

@router.get("/news/articles/{article_id}")
def article_detail(article_id:int,db:Database):
    return ApiResponse(data=news.article_data(db,news.article(db,article_id)))

@router.get("/news/articles/{article_id}/image")
def private_news_image(article_id: int, db: Database):
    from app.services.news_images import article_image
    row = news.article(db, article_id)
    return ApiResponse(data=article_image(row.canonical_url))

@router.post("/news/articles/{article_id}/analyze")
async def analyze_article(article_id: int, payload: dict, db: Database):
    return ApiResponse(data=await news.analyze(db, article_id, payload.get("greenhouse_id")))

@router.post("/news/articles/{article_id}/check-link")
def check_article_link(article_id: int, db: Database):
    return ApiResponse(data=news.check_link(db, article_id))

@router.post("/news/articles/{article_id}/research")
def article_research(article_id: int, payload: ResearchLink, db: Database):
    require_role("admin", "agronomist")
    a = news.article(db, article_id)
    from app.schemas.agronomist import StudyCreate
    from app.services import agronomist_service
    r = agronomist_service.create_study(db, StudyCreate(greenhouse_id=payload.greenhouse_id, crop_batch_id=payload.crop_batch_id,
        question=a.title[:500], hypothesis="根据公开资讯提出待验证问题；需确认适用作物与生产阶段"))
    r.payload = {**r.payload, "news_reference": {"article_id": a.id, "url": a.canonical_url, "title": a.title}}; db.commit()
    return ApiResponse(data={"research_id": r.id, "greenhouse_id": r.greenhouse_id})

@router.put("/news/bookmarks/{article_id}")
def mark_article(article_id: int, db: Database, payload: BookmarkWrite):
    a = news.article(db, article_id)
    mark = db.scalar(select(NewsBookmark).where(NewsBookmark.user_id == actor().id, NewsBookmark.article_id == a.id))
    if not mark:
        from sqlalchemy.exc import IntegrityError
        try:
            with db.begin_nested():
                mark = NewsBookmark(user_id=actor().id, article_id=a.id); db.add(mark); db.flush()
        except IntegrityError:
            mark = db.scalar(select(NewsBookmark).where(NewsBookmark.user_id == actor().id, NewsBookmark.article_id == a.id))
    if payload.bookmarked is not None: mark.bookmarked = payload.bookmarked
    if payload.read: mark.read_at = datetime.now(UTC)
    db.commit()
    return ApiResponse(data=news.article_data(db, a))

@router.get("/news/preferences")
def preference(db: Database):
    p = news.preference(db)
    return ApiResponse(data={k: getattr(p, k) for k in ("crops", "topics", "enabled", "local_hour")})

@router.put("/news/preferences")
def preference_save(payload: PreferenceWrite, db: Database):
    return ApiResponse(data=news.save_preference(db, payload))

@router.post("/news/digests")
def build_digest(db: Database):
    news.preference(db)
    return ApiResponse(data=news.digest(db, db.get(User, actor().id), force=True))

@router.get("/news/digests")
def digests(db: Database):
    rows = db.scalars(select(NewsDigest).where(NewsDigest.user_id == actor().id).order_by(NewsDigest.day.desc()).limit(60))
    return ApiResponse(data=[{"id": d.id, "day": d.day, "body": d.body, "read_at": d.read_at, "created_at": d.created_at,
        "articles": [news.article_data(db, a) for a in db.scalars(select(NewsArticle).where(NewsArticle.id.in_(d.article_ids), NewsArticle.organization_id == actor().organization_id))]} for d in rows])

@router.put("/news/digests/{digest_id}/read")
def read_digest(digest_id: int, db: Database):
    d = db.scalar(select(NewsDigest).where(NewsDigest.id == digest_id, NewsDigest.user_id == actor().id))
    if not d: raise ServiceError(404, "日报不存在")
    d.read_at = datetime.now(UTC); db.commit()
    return ApiResponse(data={"read": True})

@router.get("/news/jobs")
def jobs(db: Database):
    require_role("admin", "agronomist")
    ids = [str(s.id) for s in db.scalars(select(NewsSource).where(NewsSource.organization_id == actor().organization_id))]
    rows = db.scalars(select(AutomationJob).order_by(AutomationJob.updated_at.desc()).limit(200))
    return ApiResponse(data=[{"key": j.key, "status": j.status, "attempts": j.attempts, "updated_at": j.updated_at,
        "result": j.result} for j in rows if (j.key.startswith("news:") and j.key.split(":")[1] in ids) or j.key.startswith(f"digest:{actor().id}:")])

@router.get("/knowledge/documents")
def documents(db: Database):
    return ApiResponse(data=[document_service.data(db, d) for d in db.scalars(select(KnowledgeDocument).where(
        KnowledgeDocument.organization_id == actor().organization_id).order_by(KnowledgeDocument.id.desc()))])

@router.post("/knowledge/documents", status_code=201)
async def import_document(db: Database, file: UploadFile = File(), title: str = Form("", max_length=200),
    crops: str = Form("", max_length=300), stages: str = Form("", max_length=500), source_url: str = Form("", max_length=1500),
    applicability: str = Form("", max_length=3000), rights_confirmed: bool = Form(False)):
    content = await file.read(15_000_001)
    return ApiResponse(data=document_service.ingest(db, file.filename or "document", content, title,
        [s.strip() for s in crops.split(",") if s.strip()], [s.strip() for s in stages.split(",") if s.strip()],
        source_url, applicability, rights_confirmed))

@router.get("/knowledge/documents/{document_id}")
def document(document_id: int, db: Database):
    return ApiResponse(data=document_service.data(db, document_service.document(db, document_id), True))

@router.put("/knowledge/documents/{document_id}/review")
def review_document(document_id: int, db: Database, payload: ReviewWrite):
    return ApiResponse(data=document_service.review(db, document_id, payload.approved))

@router.delete("/knowledge/documents/{document_id}")
def remove_document(document_id: int, db: Database):
    return ApiResponse(data=document_service.remove(db, document_id))

@router.get("/knowledge/search")
def knowledge_search(db: Database, q: str = Query(min_length=1, max_length=500), crop: str | None = None, stage: str | None = None):
    from app.services.knowledge_service import search_knowledge
    return ApiResponse(data={"items": search_knowledge(q, limit=10, db=db, crop=crop, stage=stage), "method": "keyword_v2"})

@router.get("/knowledge/parsers")
def parsers():
    return ApiResponse(data=document_service.docling_probe())

@router.get("/ai/traces")
def traces(db: Database):
    return ApiResponse(data=evaluations.traces(db))

@router.post("/ai/evaluations", status_code=201)
async def evaluate(payload: EvaluationRequest, db: Database):
    require_role("admin", "agronomist")
    if payload.mode == "model":
        if not payload.paid_model_authorized: raise ServiceError(422, "实际模型评测需要明确同意调用已配置模型")
        return ApiResponse(data=await evaluations.evaluate_model(db))
    return ApiResponse(data=evaluations.evaluate(db))

@router.get("/ai/evaluations")
def evaluation_history(db: Database):
    return ApiResponse(data=[evaluations.evaluation_data(r) for r in db.scalars(select(AIEvaluationRun).where(
        AIEvaluationRun.organization_id == actor().organization_id).order_by(AIEvaluationRun.id.desc()).limit(50))])
