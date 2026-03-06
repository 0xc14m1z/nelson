import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

session_models = Table(
    "session_models",
    Base.metadata,
    Column("session_id", ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("llm_model_id", ForeignKey("llm_models.id"), primary_key=True),
)


class Session(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    enquiry: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    max_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    models = relationship("LLMModel", secondary=session_models)
    llm_calls = relationship("LLMCall", back_populates="session", cascade="all, delete-orphan")
