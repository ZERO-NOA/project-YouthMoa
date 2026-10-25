from datetime import datetime

from sqlalchemy import (
    DateTime,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Benefit(Base):
    __tablename__ = "benefits"

    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "external_id",
            name="uq_benefits_source_external",
        ),
        Index("idx_benefits_category", "category"),
        Index("idx_benefits_region", "region"),
        Index("idx_benefits_title", "title"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    source_name: Mapped[str] = mapped_column(
        String(100),
        default="data.go.kr",
        nullable=False,
    )

    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    organization: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    target: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    region: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    support_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    application_period: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    application_method: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    detail_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    # 하나의 혜택에 여러 회원이 즐겨찾기를 등록할 수 있음
    favorites = relationship(
        "Favorite",
        back_populates="benefit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )