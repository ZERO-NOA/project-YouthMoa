"""내부 표준 응답 스키마.

프론트엔드·DB 담당과 합의하는 '계약'이다. 필드를 바꾸면 docs/api-spec.md 도 함께 수정한다.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class WelfareSummary(BaseModel):
    """목록 카드에 필요한 최소 정보"""

    id: Optional[str] = Field(None, description="서비스 ID (상세 조회 키)")
    title: Optional[str] = Field(None, description="서비스명")
    summary: Optional[str] = Field(None, description="서비스 요약")
    province: Optional[str] = Field(None, description="시·도 (예: 서울특별시)")
    city: Optional[str] = Field(None, description="시·군·구 (예: 강남구)")
    department: Optional[str] = Field(None, description="담당 부서")
    life_stages: List[str] = Field(default_factory=list, description="생애주기")
    themes: List[str] = Field(default_factory=list, description="관심주제")
    targets: List[str] = Field(default_factory=list, description="대상 특성")
    support_cycle: Optional[str] = Field(None, description="지원주기")
    provision_type: Optional[str] = Field(None, description="제공유형")
    apply_type: Optional[str] = Field(None, description="신청 방법명(예: 방문/온라인)")
    detail_url: Optional[str] = Field(None, description="복지로 상세 링크")
    views: Optional[int] = Field(None, description="조회수")
    updated_at: Optional[str] = Field(None, description="최종 수정일(YYYY-MM-DD)")


class RelatedInfo(BaseModel):
    """문의처/근거 법령/서식 한 건. name=이름, content=전화번호 또는 URL"""

    name: Optional[str] = None
    content: Optional[str] = None


class WelfareListResponse(BaseModel):
    total_count: int
    page: int
    size: int
    items: List[WelfareSummary]
    source: Optional[str] = Field(None, description="snapshot(로컬 저장본) | live(공공 API 직접 호출)")
    as_of: Optional[str] = Field(None, description="스냅샷 수집 시각(ISO, UTC). live 면 null")


class WelfareDetail(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    overview: Optional[str] = Field(None, description="서비스 개요")
    province: Optional[str] = None
    city: Optional[str] = None
    department: Optional[str] = None
    life_stages: List[str] = Field(default_factory=list)
    themes: List[str] = Field(default_factory=list)
    targets: List[str] = Field(default_factory=list)
    support_cycle: Optional[str] = None
    provision_type: Optional[str] = None
    target_detail: Optional[str] = Field(None, description="지원 대상")
    criteria: Optional[str] = Field(None, description="선정 기준")
    benefit: Optional[str] = Field(None, description="지원 내용(급여)")
    apply_type: Optional[str] = Field(None, description="신청 방법명")
    apply_method: Optional[str] = Field(None, description="신청 방법 상세")
    contacts: List[RelatedInfo] = Field(default_factory=list, description="문의처(name=부서, content=전화)")
    laws: List[RelatedInfo] = Field(default_factory=list, description="근거 법령/조례(name)")
    forms: List[RelatedInfo] = Field(default_factory=list, description="서식(name, content=다운로드 URL)")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    detail_url: Optional[str] = Field(None, description="복지로 상세 링크(스냅샷에 있을 때만)")
    views: Optional[int] = None
    updated_at: Optional[str] = None


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
