import os
import tempfile
import uuid
import zipfile
import aiofiles
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from starlette.background import BackgroundTask

from app.db.session import get_session
from app.models.settings import ShopSettings, FaqItem

router = APIRouter(prefix="/settings", tags=["settings"])

MEDIA_DIR = Path("/app/media")
LOGS_DIR = Path(__file__).resolve().parents[2] / "media" / "logs"


# ── helpers ──────────────────────────────────────────────

async def _get_settings(session: AsyncSession) -> ShopSettings:
    res = await session.execute(select(ShopSettings).where(ShopSettings.id == 1))
    s = res.scalar_one_or_none()
    if not s:
        s = ShopSettings(id=1)
        session.add(s)
        await session.flush()
    return s


# ── ShopSettings ─────────────────────────────────────────

@router.get("/")
async def get_settings(session: AsyncSession = Depends(get_session)):
    s = await _get_settings(session)
    return _settings_dict(s)


class SettingsUpdate(BaseModel):
    shop_name: Optional[str] = None
    reviews_enabled: Optional[bool] = None
    welcome_message: Optional[str] = None
    seller_contact: Optional[str] = None
    admin_contact: Optional[str] = None
    hide_out_of_stock: Optional[bool] = None
    payment_qr_comment: Optional[str] = None
    legal_name: Optional[str] = None


@router.patch("/")
async def update_settings(data: SettingsUpdate, session: AsyncSession = Depends(get_session)):
    s = await _get_settings(session)
    if data.shop_name is not None:
        s.shop_name = data.shop_name
    if data.reviews_enabled is not None:
        s.reviews_enabled = data.reviews_enabled
    if data.welcome_message is not None:
        s.welcome_message = data.welcome_message
    if data.seller_contact is not None:
        s.seller_contact = data.seller_contact
    if data.admin_contact is not None:
        s.admin_contact = data.admin_contact
    if data.hide_out_of_stock is not None:
        s.hide_out_of_stock = data.hide_out_of_stock
    if data.payment_qr_comment is not None:
        s.payment_qr_comment = data.payment_qr_comment
    if data.legal_name is not None:
        s.legal_name = data.legal_name
    await session.commit()
    return _settings_dict(s)


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/svg+xml"):
        raise HTTPException(400, "Unsupported image type")
    s = await _get_settings(session)
    if s.logo_filename:
        old = MEDIA_DIR / s.logo_filename
        if old.exists():
            old.unlink()
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    filename = f"logo_{uuid.uuid4().hex[:8]}.{ext}"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(MEDIA_DIR / filename, "wb") as f:
        await f.write(await file.read())
    s.logo_filename = filename
    await session.commit()
    return {"logo_url": f"/media/{filename}"}


@router.delete("/logo")
async def delete_logo(session: AsyncSession = Depends(get_session)):
    s = await _get_settings(session)
    if s.logo_filename:
        p = MEDIA_DIR / s.logo_filename
        if p.exists():
            p.unlink()
        s.logo_filename = None
        await session.commit()
    return {"status": "ok"}


@router.post("/stamp")
async def upload_stamp(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Unsupported image type")
    s = await _get_settings(session)
    if s.stamp_filename:
        old = MEDIA_DIR / s.stamp_filename
        if old.exists():
            old.unlink()
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    filename = f"stamp_{uuid.uuid4().hex[:8]}.{ext}"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(MEDIA_DIR / filename, "wb") as f:
        await f.write(await file.read())
    s.stamp_filename = filename
    await session.commit()
    return {"stamp_url": f"/media/{filename}"}


@router.delete("/stamp")
async def delete_stamp(session: AsyncSession = Depends(get_session)):
    s = await _get_settings(session)
    if s.stamp_filename:
        p = MEDIA_DIR / s.stamp_filename
        if p.exists():
            p.unlink()
        s.stamp_filename = None
        await session.commit()
    return {"status": "ok"}


@router.post("/payment-qr")
async def upload_payment_qr(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Unsupported image type")
    s = await _get_settings(session)
    if s.payment_qr_filename:
        old = MEDIA_DIR / s.payment_qr_filename
        if old.exists():
            old.unlink()
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    filename = f"payment_qr_{uuid.uuid4().hex[:8]}.{ext}"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(MEDIA_DIR / filename, "wb") as f:
        await f.write(await file.read())
    s.payment_qr_filename = filename
    await session.commit()
    return {"payment_qr_url": f"/media/{filename}"}


@router.delete("/payment-qr")
async def delete_payment_qr(session: AsyncSession = Depends(get_session)):
    s = await _get_settings(session)
    if s.payment_qr_filename:
        p = MEDIA_DIR / s.payment_qr_filename
        if p.exists():
            p.unlink()
        s.payment_qr_filename = None
        await session.commit()
    return {"status": "ok"}


@router.get("/logs/download")
async def download_logs():
    log_files = sorted(
        [p for p in LOGS_DIR.glob("*.log*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not log_files:
        raise HTTPException(404, "Логи ещё не созданы")
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_file.close()
    with zipfile.ZipFile(temp_file.name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in log_files:
            archive.write(path, arcname=path.name)
    filename = f"kaza-shop-logs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    return FileResponse(
        temp_file.name,
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(os.unlink, temp_file.name),
    )


def _settings_dict(s: ShopSettings) -> dict:
    return {
        "shop_name": s.shop_name,
        "logo_filename": s.logo_filename,
        "logo_url": f"/media/{s.logo_filename}" if s.logo_filename else None,
        "reviews_enabled": s.reviews_enabled,
        "welcome_message": s.welcome_message,
        "seller_contact": s.seller_contact,
        "admin_contact": s.admin_contact,
        "hide_out_of_stock": s.hide_out_of_stock,
        "stamp_filename": s.stamp_filename,
        "stamp_url": f"/media/{s.stamp_filename}" if s.stamp_filename else None,
        "payment_qr_filename": s.payment_qr_filename,
        "payment_qr_url": f"/media/{s.payment_qr_filename}" if s.payment_qr_filename else None,
        "payment_qr_comment": s.payment_qr_comment,
        "legal_name": s.legal_name,
    }


# ── FAQ ──────────────────────────────────────────────────

faq_router = APIRouter(prefix="/faq", tags=["faq"])


class FaqCreate(BaseModel):
    question: str
    answer: str
    sort_order: int = 0
    is_active: bool = True


class FaqUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


@faq_router.get("/")
async def list_faq(session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(FaqItem).order_by(FaqItem.sort_order.asc(), FaqItem.id.asc())
    )
    return [_faq_dict(f) for f in res.scalars().all()]


@faq_router.post("/")
async def create_faq(data: FaqCreate, session: AsyncSession = Depends(get_session)):
    item = FaqItem(**data.dict())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _faq_dict(item)


@faq_router.patch("/{item_id}")
async def update_faq(item_id: int, data: FaqUpdate, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(FaqItem).where(FaqItem.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(item, k, v)
    await session.commit()
    return _faq_dict(item)


@faq_router.delete("/{item_id}")
async def delete_faq(item_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(FaqItem).where(FaqItem.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    await session.delete(item)
    await session.commit()
    return {"status": "deleted"}


def _faq_dict(f: FaqItem) -> dict:
    return {
        "id": f.id, "question": f.question, "answer": f.answer,
        "sort_order": f.sort_order, "is_active": f.is_active,
    }