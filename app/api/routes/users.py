from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import require_bot_auth
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])

class UserRegister(BaseModel):
    id: int = Field(gt=0)
    username: Optional[str] = Field(default=None, max_length=64)
    first_name: Optional[str] = Field(default=None, max_length=64)
    last_name: Optional[str] = Field(default=None, max_length=64)

@router.post("/register")
async def register_user(
    data: UserRegister,
    session: AsyncSession = Depends(get_session),
    bot_user_id: int | None = Depends(require_bot_auth),
):
    if bot_user_id is None or bot_user_id != data.id:
        raise HTTPException(403, "user_id mismatch")
    res = await session.execute(select(User).where(User.id == data.id))
    user = res.scalar_one_or_none()
    if not user:
        user = User(id=data.id, username=data.username,
                    first_name=data.first_name, last_name=data.last_name)
        session.add(user)
    else:
        user.username = data.username
        user.first_name = data.first_name
        user.last_name = data.last_name
    await session.commit()
    return {"ok": True}
