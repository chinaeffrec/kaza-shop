"""
Авторизация администратора.
- bcrypt (rounds=12) для паролей
- PyJWT HS256, TTL 24 часа
- Rate limiting: 5 попыток / 60 сек с одного IP (Redis; fallback — in-memory)
"""
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.schemas.auth import (
    CredentialsUpdate, CredentialsUpdateResponse,
    LoginRequest, LoginResponse, MeResponse,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

_cfg = get_settings()
CREDS_FILE = Path("/app/data/.admin_creds.json")
TOKEN_TTL = 86400  # 24 часа

# ── Rate limiting ──────────────────────────────────────────────────────────────
_login_attempts: dict[str, list[float]] = {}  # fallback: используется если Redis недоступен
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(_cfg.redis_url, decode_responses=True)
        except Exception as e:
            logger.warning("Redis rate limiter unavailable, using in-memory fallback: %s", e)
    return _redis_client


async def _check_rate_limit(ip: str) -> None:
    redis = _get_redis()
    if redis is not None:
        try:
            key = f"rl:login:{ip}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, _RATE_LIMIT_WINDOW)
            if count > _RATE_LIMIT_MAX:
                retry_after = max(await redis.ttl(key), 1)
                raise HTTPException(
                    429, f"Слишком много попыток. Повторите через {retry_after} сек.",
                    headers={"Retry-After": str(retry_after)},
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Redis rate limit error, falling back to in-memory: %s", e)

    # In-memory fallback
    now = time.time()
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < _RATE_LIMIT_WINDOW]
    if len(attempts) >= _RATE_LIMIT_MAX:
        retry_after = int(_RATE_LIMIT_WINDOW - (now - attempts[0]))
        raise HTTPException(
            429, f"Слишком много попыток. Повторите через {retry_after} сек.",
            headers={"Retry-After": str(retry_after)},
        )
    attempts.append(now)
    _login_attempts[ip] = attempts


async def _clear_rate_limit(ip: str) -> None:
    redis = _get_redis()
    if redis is not None:
        try:
            await redis.delete(f"rl:login:{ip}")
            return
        except Exception as e:
            logger.warning("Redis clear rate limit error: %s", e)
    _login_attempts.pop(ip, None)


# ── Пароли ────────────────────────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def _env_password_fingerprint() -> str:
    """Хеш текущего ADMIN_PASSWORD из env — для детекции изменений."""
    return hashlib.sha256(_cfg.admin_password.encode()).hexdigest()[:16]


def _load_creds() -> dict:
    """
    Загружает учётные данные. Логика:
    1. Если файла нет — создаём из ADMIN_PASSWORD.
    2. Если файл есть, но ADMIN_PASSWORD в env изменился (fingerprint не совпадает) — перезаписываем.
    3. Если файл есть и пароль не менялся — используем файл.
    """
    env_pass = _cfg.admin_password
    env_fp = _env_password_fingerprint()

    if CREDS_FILE.exists():
        try:
            data = json.loads(CREDS_FILE.read_text())
            stored_hash = data.get("password_hash", "")
            stored_fp = data.get("env_fingerprint", "")

            # Пароль в .env изменился — принудительно перезаписываем
            if stored_fp and stored_fp != env_fp:
                logger.info("ADMIN_PASSWORD changed in env, updating credentials")
                return _create_creds(env_pass, env_fp)

            # Валидный bcrypt-хеш и fingerprint совпадает - всё ок
            if stored_hash.startswith("$2") and stored_fp == env_fp:
                return data

            # Старый формат (sha256 или без fingerprint) - мигрируем
            if stored_hash.startswith("$2") and not stored_fp:
                logger.info("Migrating creds: adding env_fingerprint")
                data["env_fingerprint"] = env_fp
                _save_creds_data(data)
                return data

            logger.warning("Invalid creds format, recreating from env")
        except Exception as e:
            logger.warning("Failed to read creds file: %s, recreating", e)

    return _create_creds(env_pass, env_fp)


def _create_creds(password: str, fingerprint: str) -> dict:
    if not password:
        import secrets, string
        password = "".join(
            secrets.choice(string.ascii_letters + string.digits + "!@#$%")
            for _ in range(20)
        )
        logger.warning("ADMIN_PASSWORD not set, generated temporary password. Set it in .env!")

    creds = {
        "login": "admin",
        "password_hash": _hash_password(password),
        "env_fingerprint": fingerprint,
    }
    _save_creds_data(creds)
    return creds


def _save_creds_data(data: dict) -> None:
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDS_FILE.write_text(json.dumps(data))
    os.chmod(CREDS_FILE, 0o600)


def _save_creds(login: str, password_hash: str) -> None:
    """Сохранить новые учётные данные после смены пароля через API."""
    data = {
        "login": login,
        "password_hash": password_hash,
        # При смене через API fingerprint сбрасываем - пароль теперь независим от env
        "env_fingerprint": "",
    }
    _save_creds_data(data)


# ── JWT ───────────────────────────────────────────────────────────────────────
def _make_token(login: str) -> str:
    if not _cfg.secret_key:
        raise RuntimeError("SECRET_KEY must be set in environment")
    now = datetime.now(timezone.utc)
    payload = {"sub": login, "iat": now, "exp": now + timedelta(seconds=TOKEN_TTL)}
    return jwt.encode(payload, _cfg.secret_key, algorithm="HS256")


def _verify_token(token: str) -> str | None:
    if not _cfg.secret_key:
        return None
    try:
        payload = jwt.decode(token, _cfg.secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── Dependency ────────────────────────────────────────────────────────────────
def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    login = _verify_token(credentials.credentials)
    if not login:
        raise HTTPException(401, "Invalid or expired token")
    return login


def require_bot_auth(
    x_bot_token: Optional[str] = Header(default=None, alias="X-Bot-Token"),
    x_bot_user_id: Optional[int] = Header(default=None, alias="X-Bot-User-Id"),
) -> Optional[int]:
    """
    Авторизация внутренних bot-only эндпоинтов на уровне приложения.
    Возвращает user_id из заголовка (если есть), чтобы сверять с payload/path.
    """
    if not _cfg.bot_api_token:
        raise HTTPException(500, "BOT_API_TOKEN is not configured")
    if not x_bot_token or x_bot_token != _cfg.bot_api_token:
        raise HTTPException(401, "Invalid bot token")
    return x_bot_user_id


# ── Валидация пароля ──────────────────────────────────────────────────────────
def _validate_password(password: str) -> str | None:
    if len(password) < 10:
        return "Минимум 10 символов"
    if not re.search(r"[A-Za-z]", password):
        return "Нужна хотя бы одна буква"
    if not re.search(r"\d", password):
        return "Нужна хотя бы одна цифра"
    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    await _check_rate_limit(ip)
    creds = _load_creds()
    if data.login != creds["login"] or not _verify_password(data.password, creds["password_hash"]):
        raise HTTPException(401, "Неверный логин или пароль")
    await _clear_rate_limit(ip)
    return LoginResponse(token=_make_token(data.login), login=data.login, expires_in=TOKEN_TTL)


@router.get("/me", response_model=MeResponse)
async def me(login: str = Depends(require_auth)):
    return MeResponse(login=login, authenticated=True)


@router.patch("/credentials", response_model=CredentialsUpdateResponse)
async def update_credentials(data: CredentialsUpdate, login: str = Depends(require_auth)):
    creds = _load_creds()
    if not _verify_password(data.current_password, creds["password_hash"]):
        raise HTTPException(400, "Неверный текущий пароль")
    err = _validate_password(data.new_password)
    if err:
        raise HTTPException(400, err)
    _save_creds(data.new_login, _hash_password(data.new_password))
    return CredentialsUpdateResponse(ok=True, token=_make_token(data.new_login), login=data.new_login)
