"""복지 서비스 로직: 스냅샷 → 디스크/메모리 캐시 → 공공 API.

공공 API 는 일일 호출 한도가 있으므로(개발계정 기준 통상 1,000건 내외 — 활용신청 화면에서 확인)
같은 요청은 TTL 캐시로 재사용한다.

DB 담당(김동영)은 `collect_all()` 로 목록 전체를 가져가 DB에 적재할 수 있다.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Iterator, Optional

from app.services.clients.welfare_client import WelfareClient
from app.core.errors import WelfareAPIError
from app.services.parsers import welfare_parser as parser
from app.services.store.detail_store import DetailStore
from app.services.store.snapshot import SnapshotStore


class TTLCache:
    """단순 인메모리 TTL 캐시(스레드 안전). 프로세스 재시작 시 초기화된다."""

    def __init__(self, ttl: int, clock: Callable[[], float] = time.monotonic, max_items: int = 512):
        self._ttl = ttl
        self._clock = clock
        self._max = max_items
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            hit = self._data.get(key)
            if not hit:
                return None
            expires, value = hit
            if expires < self._clock():
                return None  # 만료. 삭제하지 않고 get_stale() 용으로 남겨 둔다.
            return value

    def get_stale(self, key):
        """만료 여부와 관계없이 마지막으로 저장된 값을 돌려준다(없으면 None)."""
        with self._lock:
            hit = self._data.get(key)
            return hit[1] if hit else None

    def set(self, key, value) -> None:
        if self._ttl <= 0:
            return
        with self._lock:
            if len(self._data) >= self._max:  # 가장 오래된 항목 제거
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[key] = (self._clock() + self._ttl, value)


# 공공 API 쪽 일시 장애일 때만 오래된 캐시로 대신 응답한다(잘못된 요청 등은 그대로 오류).
_STALE_OK_CODES = {
    "UPSTREAM_TIMEOUT", "UPSTREAM_UNREACHABLE", "UPSTREAM_5XX",
    "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",
}


def _codes(value: Optional[str]) -> tuple:
    return tuple(c.strip() for c in (value or "").split(",") if c.strip())


class WelfareService:
    """조회 우선순위

    목록: 스냅샷(로컬 파일) → 메모리 캐시 → 공공 API(느리고 간헐적으로 멈춤)
    상세: 메모리 캐시 → 디스크 캐시 → 공공 API (실패 시 오래된 캐시로 대체)
    source: "auto"(기본, 가능하면 스냅샷) | "live"(항상 공공 API) | "snapshot"(스냅샷만, 못 답하면 503)
    """

    def __init__(
        self,
        client: WelfareClient,
        *,
        default_life: str = "",  # 기본 생애주기 코드. 쉼표로 여러 개 가능(예: "003,004")
        search_code: str = "003",
        list_ttl: int = 600,
        detail_ttl: int = 3600,
        clock: Callable[[], float] = time.monotonic,
        snapshot: Optional[SnapshotStore] = None,
        detail_store: Optional[DetailStore] = None,
        source: str = "auto",
    ):
        self._client = client
        self._default_life = default_life
        self._search_code = search_code
        self._list_cache = TTLCache(list_ttl, clock)
        self._detail_cache = TTLCache(detail_ttl, clock)
        self._snapshot = snapshot
        self._detail_store = detail_store
        self._source = source

    # ------------------------------------------------------------------ 목록
    def search(
        self,
        *,
        keyword: Optional[str] = None,
        life: Optional[str] = None,
        theme: Optional[str] = None,
        target: Optional[str] = None,
        province: Optional[str] = None,
        city: Optional[str] = None,
        page: int = 1,
        size: int = 10,
        youth_only: bool = True,
    ) -> dict:
        """목록 검색.

        life/theme 는 코드를 쉼표로 이어 여러 개 보낼 수 있다(실측: 합집합 동작).
        '|' 는 하나의 값으로 취급되어 결과가 0건이 되므로 쓰지 않는다.
        life 가 없고 youth_only 면 기본 생애주기 코드를 적용한다.
        """
        life_param = life or (self._default_life if youth_only and self._default_life else None)

        local = self._search_local(keyword, life_param, theme, target, province, city, page, size)
        if local is not None:
            return local
        if self._source == "snapshot":
            raise WelfareAPIError(
                "SNAPSHOT_UNAVAILABLE",
                "스냅샷으로 처리할 수 없는 요청이거나 스냅샷이 없습니다(scripts/collect_snapshot.py 실행 필요).",
                503,
            )
        return self._search_live(keyword, life_param, theme, target, province, city, page, size)

    def _search_local(self, keyword, life_param, theme, target, province, city, page, size) -> Optional[dict]:
        """스냅샷으로 정확히 답할 수 있을 때만 결과를 돌려준다. 아니면 None."""
        if self._source == "live" or self._snapshot is None:
            return None
        if not self._snapshot.refresh():
            return None
        life_codes = _codes(life_param)
        # 전연령(life 없음)·대상특성(target) 필터는 스냅샷 범위 밖 → 공공 API 로 처리
        if not life_codes or target or not self._snapshot.covers(life_codes):
            return None
        result = self._snapshot.search(
            keyword=keyword, life_codes=life_codes, theme_codes=_codes(theme),
            province=province, city=city, page=page, size=size,
        )
        if result is None:  # 로컬에서 해석 못 하는 코드
            return None
        return {**result, "source": "snapshot", "as_of": self._snapshot.meta.get("collected_at")}

    def _search_live(self, keyword, life_param, theme, target, province, city, page, size) -> dict:
        key = (keyword, life_param, theme, target, province, city, page, size)
        cached = self._list_cache.get(key)
        if cached is not None:
            return cached
        try:
            xml = self._client.fetch_list(
                page=page,
                size=size,
                keyword=keyword,
                life=life_param,
                theme=theme,
                target=target,
                province=province,
                city=city,
                search_code=self._search_code,
            )
            result = {**parser.parse_list(xml, page=page, size=size), "source": "live", "as_of": None}
        except WelfareAPIError as e:
            stale = self._list_cache.get_stale(key) if e.code in _STALE_OK_CODES else None
            if stale is None:
                raise
            return stale
        self._list_cache.set(key, result)
        return result

    # ------------------------------------------------------------------ 상세
    def detail(self, serv_id: str) -> dict:
        return self._with_link(serv_id, self._detail_core(serv_id))

    def _detail_core(self, serv_id: str) -> dict:
        cached = self._detail_cache.get(serv_id)
        if cached is not None:
            return cached
        if self._detail_store is not None:
            on_disk = self._detail_store.get(serv_id)
            if on_disk is not None:
                self._detail_cache.set(serv_id, on_disk)
                return on_disk
        try:
            result = parser.parse_detail(self._client.fetch_detail(serv_id))
        except WelfareAPIError as e:
            if e.code in _STALE_OK_CODES:
                stale = self._detail_cache.get_stale(serv_id)
                if stale is None and self._detail_store is not None:
                    stale = self._detail_store.get(serv_id, allow_stale=True)  # 만료된 디스크 캐시라도
                if stale is not None:
                    return stale
            raise
        self._detail_cache.set(serv_id, result)
        if self._detail_store is not None:
            self._detail_store.set(serv_id, result)
        return result

    def _with_link(self, serv_id: str, detail: dict) -> dict:
        """상세 응답에는 복지로 링크가 없어서, 스냅샷(목록 응답)에 있는 링크를 붙여 준다."""
        if self._snapshot is None or not self._snapshot.refresh():  # 서버 시작 직후 첫 요청이 상세여도 로드되도록
            return detail
        item = self._snapshot.find(serv_id)
        url = item.get("detail_url") if item else None
        return {**detail, "detail_url": url} if url else detail

    # ------------------------------------------------------- 수집(스냅샷·DB 적재용)
    def fetch_live_page(self, *, life: Optional[str], page: int, size: int) -> dict:
        """스냅샷 수집기용: 캐시·스냅샷을 거치지 않고 공공 API 에서 한 페이지를 받는다."""
        xml = self._client.fetch_list(
            page=page, size=size, life=life or self._default_life or None, search_code=self._search_code
        )
        return parser.parse_list(xml, page=page, size=size)

    def collect_all(
        self,
        *,
        life: Optional[str] = None,
        theme: Optional[str] = None,
        province: Optional[str] = None,
        page_size: int = 100,
        max_pages: int = 50,
    ) -> Iterator[dict]:
        """목록을 끝까지 순회하며 항목을 하나씩 돌려준다(id 기준 중복 제거). 항상 공공 API 를 직접 호출한다.

        life 를 생략하면 기본 생애주기(청소년+청년 합집합)를 쓴다.
        max_pages 는 일일 호출 한도 보호 장치다.
        """
        life_param = life or (self._default_life or None)
        seen: set = set()
        for page in range(1, max_pages + 1):
            result = self._search_live(None, life_param, theme, None, province, None, page, page_size)
            items = result["items"]
            if not items:
                return
            for item in items:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                yield item
            if page * page_size >= result["total_count"]:
                return
