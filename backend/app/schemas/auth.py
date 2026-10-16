from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=40)
    phone: str = Field(pattern=r"^1\d{10}$")
    organization: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("display_name", "organization")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class LoginRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    password: str = Field(min_length=1, max_length=72)
    remember_me: bool = False


class MemberCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=40)
    phone: str = Field(pattern=r"^1\d{10}$")
    password: str = Field(min_length=8, max_length=72)
    role: Literal["admin", "agronomist", "executor", "observer"]


class UserData(BaseModel):
    id: int
    display_name: str
    phone: str
    organization: str | None
    organization_id: int | None
    role: str
    created_at: datetime
    is_active: bool = True

    model_config = {"from_attributes": True}


class AuthData(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_at: datetime
    user: UserData

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

class MemberUpdateRequest(BaseModel):
    role: Literal["admin", "agronomist", "executor", "observer"] | None = None
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=72)
