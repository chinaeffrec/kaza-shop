from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class SubCategory(Base):
    __tablename__ = "subcategories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))

    category: Mapped["Category"] = relationship("Category", back_populates="subcategories")
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="subcategory", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<SubCategory {self.name}>"