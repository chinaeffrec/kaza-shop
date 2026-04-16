from sqlalchemy import String, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, MappedColumn
from datetime import datetime

from app.db.base import Base

#Product description/model
# Product:
# - id
# - name
# - category
# - price
# - characteristics
# - description
# - images
# - created_at
# - on_sale

class Product(Base):
    __tablename__ = "products"

#id, primary_key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
#product name
    name: Mapped[str] = mapped_column(String(255), nullable=False)
#category
    category: Mapped[str] = mapped_column(String(255), nullable=False)
#price of product
    price: Mapped[int] = mapped_column(nullable=False)
#description of product
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
#characteristics
    characteristics: Mapped[str | None] = mapped_column(Text, nullable=True)
#paths of product's images
    images: Mapped[str | None] = mapped_column(Text, nullable=True)
#creation date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
#on_sale
    on_sale: Mapped[bool] = mapped_column(default=False)