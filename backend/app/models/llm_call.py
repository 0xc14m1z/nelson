import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class LLMCall(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "llm_calls"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    llm_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_models.id"), index=True
    )
    round_number: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))  # responder, critic, summarizer
    prompt: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("Session", back_populates="llm_calls")
    llm_model = relationship("LLMModel")
