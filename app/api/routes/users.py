from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])

class UserRegister(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

@router.post("/register")
async def register_user(data: UserRegister, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(User).where(User.id == data.id))
    user = res.scalar_one_or_none()
    if not user:
        user = User(id=data.id, username=data.username,
                    first_name=data.first_name, last_name=data.last_name)
        session.add(user)
    else:
        # Обновляем данные если изменились
        user.username = data.username
        user.first_name = data.first_name
        user.last_name = data.last_name
    await session.commit()
    return {"ok": True}