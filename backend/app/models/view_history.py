
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ViewHistory(Base):
    __tablename__ = "view_history"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "benefit_id",
            name="uq_view_history_user_benefit",
        ),
        Index("idx_view_history_user_last_viewed", "user_id", "last_viewed_at"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    # 조회한 회원
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 조회한 지원 제도
    benefit_id: Mapped[int] = mapped_column(
        ForeignKey("benefits.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 해당 회원이 이 제도를 조회한 횟수
    view_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )

    # 해당 회원의 가장 최근 조회 시각
    last_viewed_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # 최초 조회 시각
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="view_histories",
    )

    benefit = relationship(
        "Benefit",
        back_populates="view_histories",
    )
