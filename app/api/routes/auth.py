"""
Авторизация администратора.
- Первый запуск: логин admin, пароль из ADMIN_PASSWORD в .env (или 'changeme123!')
- После входа возвращается JWT-токен (24 часа)
- Смена логина/пароля через PATCH /auth/credentials
"""
import os
import hashlib
import hmac
import json
import base64
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import re

import smtplib
from email.mime.text import MIMEText
# from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.db.session import get_session

# _pool = ThreadPoolExecutor(max_workers=2)

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

# Хранилище учётных данных — файл вне кода
CREDS_FILE = Path("/app/data/.admin_creds.json")
SECRET_KEY = os.getenv("SECRET_KEY", "kaza-shop-secret-change-me-in-production-please")
TOKEN_TTL = 86400  # 24 часа


def _load_creds() -> dict:
    if CREDS_FILE.exists():
        try:
            return json.loads(CREDS_FILE.read_text())
        except Exception:
            pass
    # Дефолтные данные
    default_pass = os.getenv("ADMIN_PASSWORD", "changeme123!")
    if os.getenv("ENV") == "production" and default_pass == "changeme123!":
        import secrets, string
        default_pass = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        print(f"WARNING: ADMIN_PASSWORD not set, generated: {default_pass}")
    creds = {
        "login": "admin",
        "password_hash": _hash_password(default_pass),
    }
    # Сохраняем чтобы при перезапуске пароль не менялся
    _save_creds(creds["login"], creds["password_hash"])
    return creds


def _save_creds(login: str, password_hash: str):
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDS_FILE.write_text(json.dumps({"login": login, "password_hash": password_hash}))


def _hash_password(password: str) -> str:
    salt = "kaza2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def _make_token(login: str) -> str:
    payload = f"{login}:{int(time.time()) + TOKEN_TTL}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token_data = base64.b64encode(f"{payload}:{sig}".encode()).decode()
    return token_data


def _verify_token(token: str) -> str | None:
    """Возвращает login если токен валиден, иначе None"""
    try:
        decoded = base64.b64decode(token.encode()).decode()
        parts = decoded.rsplit(":", 2)
        if len(parts) != 3:
            return None
        login, expires, sig = parts
        # Проверяем подпись
        payload = f"{login}:{expires}"
        expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        # Проверяем срок
        if int(expires) < int(time.time()):
            return None
        return login
    except Exception:
        return None


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency: требует валидный JWT. Использовать в защищённых роутах."""
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    login = _verify_token(credentials.credentials)
    if not login:
        raise HTTPException(401, "Invalid or expired token")
    return login


def _validate_password(password: str) -> str | None:
    """Возвращает None если пароль валиден, иначе сообщение об ошибке"""
    if len(password) < 8:
        return "Минимум 8 символов"
    if not re.search(r"[A-Za-z]", password):
        return "Нужна хотя бы одна буква"
    if not re.search(r"\d", password):
        return "Нужна хотя бы одна цифра"
    return None


# ─── Endpoints ───────────────────────────────────────

class LoginRequest(BaseModel):
    login: str
    password: str


class CredentialsUpdate(BaseModel):
    new_login: str = Field(min_length=3, max_length=64)
    new_password: str = Field(min_length=8)
    current_password: str


@router.post("/login")
async def login(data: LoginRequest):
    creds = _load_creds()
    if data.login != creds["login"]:
        raise HTTPException(401, "Неверный логин или пароль")
    if _hash_password(data.password) != creds["password_hash"]:
        raise HTTPException(401, "Неверный логин или пароль")
    token = _make_token(data.login)
    return {"token": token, "login": data.login, "expires_in": TOKEN_TTL}


@router.get("/me")
async def me(login: str = Depends(require_auth)):
    return {"login": login, "authenticated": True}


@router.patch("/credentials")
async def update_credentials(data: CredentialsUpdate, login: str = Depends(require_auth)):
    creds = _load_creds()
    # Проверяем текущий пароль
    if _hash_password(data.current_password) != creds["password_hash"]:
        raise HTTPException(400, "Неверный текущий пароль")
    # Валидируем новый пароль
    err = _validate_password(data.new_password)
    if err:
        raise HTTPException(400, err)
    _save_creds(data.new_login, _hash_password(data.new_password))
    # Возвращаем новый токен
    token = _make_token(data.new_login)
    return {"ok": True, "token": token, "login": data.new_login}


def _send_email_sync(to_email: str, subject: str, body: str):
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user:
        # Если SMTP не настроен — пишем в логи
        import logging
        logging.getLogger(__name__).warning(
            "SMTP not configured. Recovery email to %s: %s / %s", to_email, subject, body
        )
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Email send failed: %s", e)
        return False

