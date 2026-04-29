from sqlalchemy import Text, String, Boolean, Column
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ShopSettings(Base):
    """Singleton-таблица: всегда одна строка с id=1"""
    __tablename__ = "shop_settings"

    welcome_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default="👋 Добро пожаловать!\n\nВыберите действие:"
    )

    seller_contact: Mapped[str | None] = mapped_column(String(256), nullable=True)
    admin_contact: Mapped[str | None] = mapped_column(String(256), nullable=True)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    shop_name: Mapped[str] = mapped_column(String(128), default="Kaza Shop")
    logo_filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reviews_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    hide_out_of_stock: Mapped[bool] = mapped_column(Boolean, default=False)

    stamp_filename = Column(String, nullable=True)
    payment_qr_filename = Column(String, nullable=True)
    payment_qr_comment = Column(String, nullable=True)
    legal_name = Column(String, nullable=True)


class FaqItem(Base):
    __tablename__ = "faq_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(String(512))
    answer: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
