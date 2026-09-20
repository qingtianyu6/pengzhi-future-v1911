from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import AuthSession, User
from app.schemas.auth import AuthData, LoginRequest, RegisterRequest, UserData
from app.services.errors import ServiceError


PBKDF2_ITERATIONS = 310_000


def _now() -> datetime:
    return datetime.now(UTC)


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))
    except (TypeError, ValueError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_session(db: Session, user: User, remember_me: bool) -> AuthData:
    token = secrets.token_urlsafe(40)
    expires_at = _now() + timedelta(days=30 if remember_me else 7)
    db.add(AuthSession(user_id=user.id, token_hash=_token_hash(token), expires_at=expires_at))
    db.commit()
    return AuthData(token=token, expires_at=expires_at, user=UserData.model_validate(user))


def register(db: Session, payload: RegisterRequest) -> AuthData:
    if db.scalar(select(User.id).where(User.phone == payload.phone)) is not None:
        raise ServiceError(409, "该手机号已注册，请直接登录")
    user = User(
        display_name=payload.display_name,
        phone=payload.phone,
        organization=payload.organization or None,
        password_hash=_password_hash(payload.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ServiceError(409, "该手机号已注册，请直接登录") from exc
    return _issue_session(db, user, False)


def login(db: Session, payload: LoginRequest) -> AuthData:
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None or not _password_matches(payload.password, user.password_hash):
        raise ServiceError(401, "手机号或密码错误")
    if not user.is_active:
        raise ServiceError(403, "账号已停用，请联系管理员")
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= _now()))
    return _issue_session(db, user, payload.remember_me)


def authenticate(db: Session, authorization: str | None) -> tuple[User, AuthSession]:
    if not authorization or not authorization.startswith("Bearer "):
        raise ServiceError(401, "请先登录")
    token = authorization.removeprefix("Bearer ").strip()
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    now = _now()
    if session is None or session.expires_at.replace(tzinfo=UTC) <= now:
        if session is not None:
            db.delete(session)
            db.commit()
        raise ServiceError(401, "登录状态已失效，请重新登录")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise ServiceError(401, "账号不可用，请重新登录")
    session.last_used_at = now
    db.commit()
    return user, session


def current_user(db: Session, authorization: str | None) -> UserData:
    user, _ = authenticate(db, authorization)
    return UserData.model_validate(user)


def logout(db: Session, authorization: str | None) -> None:
    _, session = authenticate(db, authorization)
    db.delete(session)
    db.commit()
