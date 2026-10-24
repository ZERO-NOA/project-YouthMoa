"""혜택 API (팀 명세: docs/api-spec.md).

GET /api/benefits              목록·검색
GET /api/benefits/codes        코드표(생애주기·주제·카테고리 매핑)
GET /api/benefits/{benefit_id} 상세

데이터 출처: 지자체 복지서비스 OpenAPI (스냅샷 → 캐시 → 공공 API 순으로 조회)
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.welfare_config import get_settings
from app.schemas.welfare import ErrorResponse, WelfareDetail, WelfareListResponse
from app.services.clients.welfare_client import WelfareClient
from app.services.store.detail_store import DetailStore
from app.services.store.snapshot import SnapshotStore
from app.services.welfare_codes import CATEGORY_TO_THEMES, codes_payload
from app.services.welfare_service import WelfareService

router = APIRouter(prefix="/api/benefits", tags=["benefits"])

_ERRORS = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@lru_cache
def get_service() -> WelfareService:
    s = get_settings()
    client = WelfareClient(
        s.service_key, base_url=s.base_url, timeout=s.timeout_sec, retries=s.retries
    )
    return WelfareService(
        client,
        default_life=s.default_life_code,
        search_code=s.search_code,
        list_ttl=s.list_cache_ttl,
        detail_ttl=s.detail_cache_ttl,
        snapshot=SnapshotStore(s.snapshot_path),
        detail_store=DetailStore(s.detail_dir, ttl_seconds=s.detail_disk_ttl),
        source=s.source,
    )


def theme_from_category(category: Optional[str]) -> Optional[str]:
    """카테고리명 → 관심주제 코드(쉼표 합집합). 모르는 카테고리면 None."""
    codes = CATEGORY_TO_THEMES.get(category or "")
    return ",".join(codes) if codes else None


@router.get("/codes")
def get_codes():
    return codes_payload()


@router.get("", response_model=WelfareListResponse, responses=_ERRORS)
def list_benefits(
    keyword: Optional[str] = Query(None, description="제목·요약 검색어(공백으로 여러 단어 가능)"),
    category: Optional[str] = Query(
        None, description="카테고리명(주거/일자리/교육/금융/생활지원/건강/문화). theme 이 있으면 무시"
    ),
    life_stage: Optional[str] = Query(
        None, description="생애주기 코드. 쉼표로 여러 개 가능(예: 003,004). 생략하면 청소년+청년"
    ),
    theme: Optional[str] = Query(None, description="관심주제 코드. 쉼표로 여러 개 가능(예: 040,050)"),
    province: Optional[str] = Query(None, description="시·도 이름(예: 서울특별시)"),
    city: Optional[str] = Query(None, description="시·군·구 이름(예: 강남구)"),
    target: Optional[str] = Query(None, description="대상 특성 코드(스냅샷 미지원 → 공공 API 직접 호출)"),
    all_ages: bool = Query(False, description="true 면 기본 생애주기 필터를 적용하지 않음(공공 API 직접 호출)"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    service: WelfareService = Depends(get_service),
):
    return service.search(
        keyword=keyword,
        life=life_stage,
        theme=theme or theme_from_category(category),
        target=target,
        province=province,
        city=city,
        page=page,
        size=size,
        youth_only=not all_ages,
    )


@router.get("/{benefit_id}", response_model=WelfareDetail, responses=_ERRORS)
def get_benefit(benefit_id: str, service: WelfareService = Depends(get_service)):
    return service.detail(benefit_id)
