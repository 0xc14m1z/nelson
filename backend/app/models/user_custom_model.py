import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class UserCustomModel(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "user_custom_models"
    __table_args__ = (
        UniqueConstraint("user_id", "llm_model_id", name="uq_user_custom_model"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    llm_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )

    llm_model: Mapped["LLMModel"] = relationship()  # noqa: F821, UP037
