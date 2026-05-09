"""Роуты настроек — только HTTP-слой."""
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.api.routes.auth import require_auth
from app.api.schemas.settings import (
    FaqCreate, FaqItemResponse, FaqUpdate, SettingsResponse, SettingsUpdate,
)
from app.db.session import get_session
from app.services import settings_service_ext as svc
from app.services import db_transfer_service as db_svc

router = APIRouter(prefix="/settings", tags=["settings"])
LOGS_DIR = Path("/app/logs")


@router.get("/public")
async def get_public_settings(session: AsyncSession = Depends(get_session)):
    """
    Публичный эндпоинт для бота — возвращает только безопасные поля:
    welcome_message, shop_name, hide_out_of_stock.
    Не требует авторизации.
    """
    s = await svc.read_settings(session)
    return {
        "shop_name": s.shop_name,
        "welcome_message": s.welcome_message,
        "hide_out_of_stock": s.hide_out_of_stock,
        "reviews_enabled": s.reviews_enabled,
        "payment_qr_url": s.payment_qr_url,
        "payment_qr_comment": s.payment_qr_comment,
        "seller_contact": s.seller_contact,
    }


@router.get("/", response_model=SettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.read_settings(session)


@router.patch("/", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.update_settings(data, session)


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.upload_logo(file, session)


@router.delete("/logo")
async def delete_logo(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.delete_logo(session)


@router.post("/stamp")
async def upload_stamp(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.upload_stamp(file, session)


@router.delete("/stamp")
async def delete_stamp(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.delete_stamp(session)


@router.post("/payment-qr")
async def upload_payment_qr(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.upload_payment_qr(file, session)


@router.delete("/payment-qr")
async def delete_payment_qr(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.delete_payment_qr(session)


@router.get("/db-export", summary="Экспорт базы данных в JSON")
async def db_export(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    content = await db_svc.export_db(session)
    filename = f"kaza_db_{datetime.now().strftime('%Y-%m-%d')}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/db-import", summary="Импорт базы данных из JSON")
async def db_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    content = await file.read()
    return await db_svc.import_db(content, session)


@router.get("/media-export", summary="Экспорт медиафайлов (ZIP)")
async def media_export(_: str = Depends(require_auth)):
    content = await db_svc.export_media()
    filename = f"kaza_media_{datetime.now().strftime('%Y-%m-%d')}.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/media-import", summary="Импорт медиафайлов из ZIP")
async def media_import(
    file: UploadFile = File(...),
    _: str = Depends(require_auth),
):
    content = await file.read()
    return await db_svc.import_media(content)


@router.get("/logs/download")
async def download_logs(_: str = Depends(require_auth)):
    log_files = sorted(
        [p for p in LOGS_DIR.glob("*.log*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ) if LOGS_DIR.exists() else []
    if not log_files:
        raise HTTPException(404, "Логи ещё не созданы")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as arc:
        for p in log_files:
            arc.write(p, arcname=p.name)
    filename = f"kaza-logs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    return FileResponse(
        tmp.name, media_type="application/zip", filename=filename,
        background=BackgroundTask(os.unlink, tmp.name),
    )


# ── FAQ ───────────────────────────────────────────────────────────────────────
faq_router = APIRouter(prefix="/faq", tags=["faq"])


@faq_router.get("/", response_model=list[FaqItemResponse])
async def list_faq(session: AsyncSession = Depends(get_session)):
    """Публичный — используется ботом."""
    return await svc.list_faq(session)


@faq_router.post("/", response_model=FaqItemResponse)
async def create_faq(
    data: FaqCreate,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.create_faq(data, session)


@faq_router.patch("/{item_id}", response_model=FaqItemResponse)
async def update_faq(
    item_id: int,
    data: FaqUpdate,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.update_faq(item_id, data, session)


@faq_router.delete("/{item_id}")
async def delete_faq(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await svc.delete_faq(item_id, session)
