from datetime import datetime
from sqlalchemy import ForeignKey, Boolean, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)

    subcategory_id: Mapped[int] = mapped_column(
        ForeignKey("subcategories.id", ondelete="CASCADE")
    )

    price: Mapped[int] = mapped_column(Integer, nullable=False)           # цена в копейках
    discount_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    characteristics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    images: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)   # список file_id фото

    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    subcategory: Mapped["SubCategory"] = relationship("SubCategory", back_populates="products")

    def __repr__(self):
        return f"<Product {self.name} | {self.price}₽>"