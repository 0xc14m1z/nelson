import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UpdatedAtMixin, UUIDPrimaryKey

user_default_models = Table(
    "user_default_models",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("llm_model_id", ForeignKey("llm_models.id", ondelete="CASCADE"), primary_key=True),
)


class User(UUIDPrimaryKey, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    billing_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="own_keys")

    settings: Mapped["UserSettings"] = relationship(  # noqa: UP037
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # noqa: F821, UP037
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSettings(UUIDPrimaryKey, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    max_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="settings")  # noqa: UP037
