"""목록 스냅샷: 공공 API 를 한 번 순회해 받은 목록을 JSON 파일로 저장하고, 검색·필터는 로컬에서 처리한다.

왜 필요한가
- 실측 응답시간: 평균 8.9초, 최대 57초(2026-10-24). 사용자 요청마다 공공 API 를 부르면 화면이 멈춘다.
- 청소년+청년 목록은 약 1,760건 → 100건씩 18회 호출이면 전부 받을 수 있다.

필터 의미는 공공 API 와 같게 맞춘다: 코드 → 이름으로 바꿔 항목의 이름 목록과 교집합이 있으면 통과(쉼표 = 합집합).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, Optional

from app.services.welfare_codes import LIFE_STAGE, THEME
from app.services.parsers.welfare_parser import normalize_name

SNAPSHOT_VERSION = 1


def _atomic_write_json(path: Path, payload: dict) -> None:
    """임시 파일에 쓴 뒤 교체한다. 쓰는 도중 중단돼도 기존 파일이 깨지지 않는다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_snapshot(path: Path, items: list, meta: dict) -> None:
    meta = {**meta, "version": SNAPSHOT_VERSION, "count": len(items)}
    _atomic_write_json(Path(path), {"meta": meta, "items": items})


def _names(codes: Iterable[str], table: dict) -> Optional[set]:
    """코드 → 이름 집합. 모르는 코드가 하나라도 있으면 None(= 로컬에서 판단 불가)."""
    out = set()
    for c in codes:
        if c not in table:
            return None
        out.add(normalize_name(table[c]))
    return out


class SnapshotStore:
    def __init__(self, path):
        self._path = Path(path)
        self._items: list = []
        self._by_id: dict = {}
        self.meta: dict = {}
        self._mtime: Optional[float] = None

    @property
    def available(self) -> bool:
        return bool(self._items)

    def refresh(self) -> bool:
        """파일이 바뀌었으면 다시 읽는다(서버 재시작 없이 새 스냅샷 반영). 사용 가능하면 True."""
        try:
            mtime = self._path.stat().st_mtime
        except OSError:
            self._items, self._by_id, self.meta, self._mtime = [], {}, {}, None
            return False
        if mtime == self._mtime:
            return self.available
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            items = data["items"]
            meta = data.get("meta", {})
            if not isinstance(items, list):
                raise ValueError("items must be a list")
        except (OSError, ValueError, KeyError):
            return self.available  # 깨진 파일이면 직전 상태를 유지
        self._items, self.meta, self._mtime = items, meta, mtime
        self._by_id = {i.get("id"): i for i in items if i.get("id")}
        return self.available

    def covers(self, life_codes: tuple) -> bool:
        """요청한 생애주기가 모두 수집 범위 안에 있어야 스냅샷으로 정확히 답할 수 있다."""
        return bool(life_codes) and set(life_codes) <= set(self.meta.get("life_codes", []))

    def find(self, serv_id: str) -> Optional[dict]:
        return self._by_id.get(serv_id)

    def search(
        self,
        *,
        keyword: Optional[str] = None,
        life_codes: tuple = (),
        theme_codes: tuple = (),
        province: Optional[str] = None,
        city: Optional[str] = None,
        page: int = 1,
        size: int = 10,
    ) -> Optional[dict]:
        """필터 적용 결과. 코드를 해석할 수 없으면 None(호출자가 공공 API 로 대신 처리)."""
        life_names = _names(life_codes, LIFE_STAGE) if life_codes else set()
        theme_names = _names(theme_codes, THEME) if theme_codes else set()
        if life_names is None or theme_names is None:
            return None

        tokens = [t.lower() for t in (keyword or "").split() if t]
        prov, cty = (province or "").strip(), (city or "").strip()

        def ok(item: dict) -> bool:
            if life_names and not (life_names & set(item.get("life_stages") or [])):
                return False
            if theme_names and not (theme_names & set(item.get("themes") or [])):
                return False
            if prov and item.get("province") != prov:
                return False
            if cty and item.get("city") != cty:
                return False
            if tokens:
                hay = f"{item.get('title') or ''} {item.get('summary') or ''}".lower()
                if not all(t in hay for t in tokens):
                    return False
            return True

        hits = [i for i in self._items if ok(i)]
        start = (max(page, 1) - 1) * size
        return {
            "total_count": len(hits),
            "page": page,
            "size": size,
            "items": hits[start : start + size],
        }
