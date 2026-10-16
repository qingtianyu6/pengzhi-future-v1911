from fastapi import APIRouter, Depends, Header, Request
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from app.schemas.auth import PasswordChangeRequest, MemberUpdateRequest
from app.services.errors import ServiceError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import AuthData, LoginRequest, MemberCreateRequest, RegisterRequest, UserData
from app.schemas.common import ApiResponse
from app.services import auth_service
from app.services.access import business_access, require_role
from app.models.user import User
from sqlalchemy import select


router = APIRouter(prefix="/auth", tags=["用户认证"])
_attempts = defaultdict(deque)
_rate_lock = Lock()

def _throttle(request: Request, phone: str, kind: str):
    # Trust the socket peer, never an arbitrary X-Forwarded-For supplied by clients.
    address = request.client.host if request.client else "unknown"
    now = monotonic()
    with _rate_lock:
        for key in list(_attempts):
            while _attempts[key] and now-_attempts[key][0]>60:_attempts[key].popleft()
            if not _attempts[key]:del _attempts[key]
        limits=[(f"{kind}:account:{phone}",10),(f"{kind}:ip:{address}",100 if kind=="login" else 30)]
        if any(len(_attempts[key])>=limit for key,limit in limits):
            raise ServiceError(429,"请求过于频繁，请等待一分钟后重试")
        for key,_ in limits:_attempts[key].append(now)



@router.post("/register", response_model=ApiResponse[AuthData], summary="注册账号")
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    _throttle(request, payload.phone, "register")
    return ApiResponse(data=auth_service.register(db, payload), message="注册成功")


@router.post("/login", response_model=ApiResponse[AuthData], summary="账号登录")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _throttle(request, payload.phone, "login")
    return ApiResponse(data=auth_service.login(db, payload), message="登录成功")


@router.get("/me", response_model=ApiResponse[UserData], summary="获取当前用户")
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    return ApiResponse(data=auth_service.current_user(db, authorization))


@router.post("/logout", response_model=ApiResponse[None], summary="退出登录")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    auth_service.logout(db, authorization)
    return ApiResponse(data=None, message="已退出登录")


@router.get("/members", response_model=ApiResponse[list[UserData]], dependencies=[Depends(business_access)])
def members(db: Session = Depends(get_db)):
    actor = require_role("admin")
    rows = db.scalars(select(User).where(User.organization_id == actor.organization_id).order_by(User.id))
    return ApiResponse(data=[UserData.model_validate(row) for row in rows])


@router.post("/members", response_model=ApiResponse[UserData], dependencies=[Depends(business_access)])
def add_member(payload: MemberCreateRequest, db: Session = Depends(get_db)):
    actor = require_role("admin")
    return ApiResponse(data=auth_service.create_member(db, payload, actor.organization_id))

@router.post("/change-password", response_model=ApiResponse[AuthData])
def change_password(payload: PasswordChangeRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    from sqlalchemy import delete
    from app.models.user import AuthSession
    user, _ = auth_service.authenticate(db, authorization)
    if not auth_service._password_matches(payload.current_password, user.password_hash):
        raise ServiceError(403, "当前密码不正确")
    user.password_hash=auth_service._password_hash(payload.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id==user.id))
    db.commit()
    return ApiResponse(data=auth_service._issue_session(db,user,False),message="密码已更新，其他会话已退出")

@router.patch("/members/{member_id}", response_model=ApiResponse[UserData], dependencies=[Depends(business_access)])
def update_member(member_id: int, payload: MemberUpdateRequest, db: Session = Depends(get_db)):
    from sqlalchemy import func, delete
    from app.models.user import AuthSession
    actor=require_role("admin")
    user=db.scalar(select(User).where(User.id==member_id, User.organization_id==actor.organization_id))
    if user is None:raise ServiceError(404,"成员不存在")
    if user.role=="admin" and user.is_active and (payload.is_active is False or payload.role not in {None,"admin"}):
        total=db.scalar(select(func.count()).select_from(User).where(User.organization_id==actor.organization_id,User.role=="admin",User.is_active.is_(True)))
        if total<=1:raise ServiceError(409,"必须保留至少一名启用的管理员")
    if payload.role is not None:user.role=payload.role
    if payload.is_active is not None:user.is_active=payload.is_active
    if payload.new_password:
        if user.id==actor.id:raise ServiceError(422,"本人修改密码请使用修改密码功能")
        user.password_hash=auth_service._password_hash(payload.new_password)
    if payload.new_password or payload.is_active is False:
        db.execute(delete(AuthSession).where(AuthSession.user_id==user.id))
    db.commit();db.refresh(user)
    return ApiResponse(data=UserData.model_validate(user),message="成员设置已更新")
