"""Community, news and document records share the existing account system."""
from datetime import datetime
from typing import Any
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.greenhouse import utc_now


class ForumPost(Base):
    __tablename__ = "forum_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30), index=True)
    visibility: Mapped[str] = mapped_column(String(16), default="organization")
    status: Mapped[str] = mapped_column(String(16), default="published")
    review_state: Mapped[str] = mapped_column(String(16), default="unreviewed")
    accepted_comment_id: Mapped[int | None] = mapped_column()
    fields_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    research_source_id: Mapped[int | None] = mapped_column()
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    __mapper_args__ = {"version_id_col": version}


class ForumComment(Base):
    __tablename__ = "forum_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("forum_posts.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("forum_comments.id"))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ForumReaction(Base):
    __tablename__ = "forum_reactions"
    __table_args__ = (UniqueConstraint("post_id", "user_id", "kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("forum_posts.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))


class ForumReport(Base):
    __tablename__ = "forum_reports"
    __table_args__ = (UniqueConstraint("post_id", "reporter_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("forum_posts.id"), index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContentAsset(Base):
    __tablename__ = "content_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("forum_posts.id"), index=True)
    filename: Mapped[str] = mapped_column(String(180))
    stored_name: Mapped[str] = mapped_column(String(80))
    media_type: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NewsSource(Base):
    __tablename__ = "news_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    url: Mapped[str] = mapped_column(String(1500))
    kind: Mapped[str] = mapped_column(String(16), default="rss")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    permission_note: Mapped[str] = mapped_column(Text)
    failures: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(300))


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (UniqueConstraint("organization_id", "canonical_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("news_sources.id"))
    title: Mapped[str] = mapped_column(String(500))
    canonical_url: Mapped[str] = mapped_column(String(1500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="metadata_only")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    crops: Mapped[list[str]] = mapped_column(JSON, default=list)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    local_hour: Mapped[int] = mapped_column(default=8)


class NewsAutomation(Base):
    __tablename__ = "news_automation"
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    use_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_ai_limit: Mapped[int] = mapped_column(default=8)
    digest_limit: Mapped[int] = mapped_column(default=8)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class NewsEvidence(Base):
    __tablename__ = "news_evidence"
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id"), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30))
    sha256: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NewsDigest(Base):
    __tablename__ = "news_digests"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[str] = mapped_column(String(10))
    article_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NewsBookmark(Base):
    __tablename__ = "news_bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "article_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)


class AutomationJob(Base):
    __tablename__ = "automation_jobs"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner: Mapped[str] = mapped_column(String(80))
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    attempts: Mapped[int] = mapped_column(default=1)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (UniqueConstraint("organization_id", "sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(180))
    sha256: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(String(1500))
    source_quality: Mapped[str] = mapped_column(String(30), default="unverified")
    crops: Mapped[list[str]] = mapped_column(JSON, default=list)
    stages: Mapped[list[str]] = mapped_column(JSON, default=list)
    applicability: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="processing")
    parser: Mapped[str] = mapped_column(String(60), default="")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    position: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)


class AIEvaluationRun(Base):
    __tablename__ = "ai_evaluation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    suite_version: Mapped[str] = mapped_column(String(60))
    model_version: Mapped[str] = mapped_column(String(100))
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AITrace(Base):
    __tablename__ = "ai_traces"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tool_call_id: Mapped[int | None] = mapped_column(ForeignKey("agent_tool_calls.id"))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    operation: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    elapsed_ms: Mapped[int] = mapped_column()
    error_code: Mapped[str | None] = mapped_column(String(100))
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
