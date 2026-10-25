
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Benefit(Base):
    __tablename__ = "benefits"

    __table_args__ = (
        UniqueConstraint(
            "external_id",
            name="uq_benefits_external_id",
        ),
        Index("idx_benefits_title", "title"),
        Index("idx_benefits_province_city", "province", "city"),
    )

    # DB 내부 기본 키
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # 공공 API의 제도 ID (servId)
    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # 지원 제도 기본 정보
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    overview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 담당 기관 및 지역
    department: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    province: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # 대상 및 분야
    life_stages: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    themes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    targets: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    target_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    criteria: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 지원 내용 및 신청 정보
    benefit: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    support_cycle: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    provision_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    apply_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    apply_method: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 신청 기간
    start_date: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    end_date: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    # 관련 정보: 각 항목은 {name, content} 형태의 목록
    contacts: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    laws: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    forms: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # 신청 상세 페이지
    detail_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 공공 API에서 제공하는 조회수 및 수정일
    views: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    updated_at: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    # DB 관리 정보
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    )
    record_updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    # 다른 테이블과의 관계
    favorites = relationship(
        "Favorite",
        back_populates="benefit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    view_histories = relationship(
        "ViewHistory",
        back_populates="benefit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
