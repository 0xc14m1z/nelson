import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class LLMModel(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "llm_models"
    __table_args__ = (UniqueConstraint("provider_id", "slug", name="uq_provider_slug"),)

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    input_price_per_mtok: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0")
    )
    output_price_per_mtok: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, nullable=False, default=128000)

    provider: Mapped["Provider"] = relationship(back_populates="models")  # noqa: F821
