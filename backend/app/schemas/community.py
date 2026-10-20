from typing import Literal
from pydantic import BaseModel, Field

class AgricultureFields(BaseModel):
    crop: str = Field(default="", max_length=40)
    variety: str = Field(default="", max_length=100)
    stage: str = Field(default="", max_length=60)
    issue: str = Field(default="", max_length=100)
    environment: str = Field(default="", max_length=1500)
    attempted: str = Field(default="", max_length=2000)
    observation: str = Field(default="", max_length=2000)
    references: list[str] = Field(default_factory=list, max_length=10)

class PostWrite(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    body: str = Field(min_length=2, max_length=20000)
    category: Literal["question", "experience", "research", "discussion"] = "discussion"
    visibility: Literal["public", "organization", "private"] = "organization"
    fields: AgricultureFields = Field(default_factory=AgricultureFields)
    tags: list[str] = Field(default_factory=list, max_length=8)
    asset_ids: list[int] = Field(default_factory=list, max_length=8)
    version: int | None = None
    research_source_id: int | None = None
    publish_confirmed: bool = False

class CommentWrite(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    parent_id: int | None = None

class ReportWrite(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)

class ModerationWrite(BaseModel):
    action: Literal["review", "hide", "restore", "dismiss"]
    note: str = Field(min_length=2, max_length=1000)

class ResearchLink(BaseModel):
    greenhouse_id: int = Field(gt=0)
    crop_batch_id: int | None = None
    research_id: int | None = None
    confirmed: bool = False

class AssistRequest(BaseModel):
    use_model: bool = False

class SourceWrite(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    url: str = Field(max_length=1500)
    kind: Literal["rss", "web", "official_index"] = "rss"
    permission_confirmed: bool
    permission_note: str = Field(min_length=3, max_length=2000)
    enabled: bool = True

class PreferenceWrite(BaseModel):
    crops: list[str] = Field(default_factory=list, max_length=10)
    topics: list[str] = Field(default_factory=list, max_length=20)
    enabled: bool = False
    local_hour: int = Field(default=8, ge=0, le=23)

class EvaluationRequest(BaseModel):
    mode: Literal["local", "model"] = "local"
    paid_model_authorized: bool = False

class ReactionWrite(BaseModel):
    enabled: bool = True

class BookmarkWrite(BaseModel):
    bookmarked: bool | None = None
    read: bool = False

class ReviewWrite(BaseModel):
    approved: bool
