import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKey


class DefaultModel(UUIDPrimaryKey, Base):
    __tablename__ = "default_models"
    __table_args__ = (UniqueConstraint("llm_model_id", name="uq_default_model"),)

    llm_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    llm_model: Mapped["LLMModel"] = relationship()  # noqa: F821, UP037
