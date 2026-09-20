from datetime import datetime

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


class UserData(BaseModel):
    id: int
    display_name: str
    phone: str
    organization: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthData(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_at: datetime
    user: UserData
