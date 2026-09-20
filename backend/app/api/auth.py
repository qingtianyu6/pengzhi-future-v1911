from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import AuthData, LoginRequest, RegisterRequest, UserData
from app.schemas.common import ApiResponse
from app.services import auth_service


router = APIRouter(prefix="/auth", tags=["用户认证"])


@router.post("/register", response_model=ApiResponse[AuthData], summary="注册账号")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return ApiResponse(data=auth_service.register(db, payload), message="注册成功")


@router.post("/login", response_model=ApiResponse[AuthData], summary="账号登录")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return ApiResponse(data=auth_service.login(db, payload), message="登录成功")


@router.get("/me", response_model=ApiResponse[UserData], summary="获取当前用户")
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    return ApiResponse(data=auth_service.current_user(db, authorization))


@router.post("/logout", response_model=ApiResponse[None], summary="退出登录")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    auth_service.logout(db, authorization)
    return ApiResponse(data=None, message="已退出登录")
