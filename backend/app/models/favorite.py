
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Favorite(Base):
    __tablename__ = "favorites"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "benefit_id",
            name="uq_favorites_user_benefit",
        ),
        Index("idx_favorites_benefit", "benefit_id"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    # 즐겨찾기를 등록한 회원
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 즐겨찾기한 지원 제도
    benefit_id: Mapped[int] = mapped_column(
        ForeignKey("benefits.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="favorites",
    )

    benefit = relationship(
        "Benefit",
        back_populates="favorites",
    )
