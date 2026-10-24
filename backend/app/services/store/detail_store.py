"""상세 응답 디스크 캐시. 한 번 받은 상세는 파일로 남겨 공공 API 호출(건당 1회)을 줄인다."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable, Optional

from app.services.store.snapshot import _atomic_write_json

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class DetailStore:
    def __init__(self, directory, ttl_seconds: int = 7 * 86400, clock: Callable[[], float] = time.time):
        self._dir = Path(directory)
        self._ttl = ttl_seconds
        self._clock = clock

    def _path(self, serv_id: str) -> Optional[Path]:
        # servId 는 외부 입력이다. 파일명으로 쓰기 전에 허용 문자만 통과시켜 경로 조작(../)을 막는다.
        if not isinstance(serv_id, str) or not _SAFE_ID.match(serv_id):
            return None
        return self._dir / f"{serv_id}.json"

    def get(self, serv_id: str, allow_stale: bool = False) -> Optional[dict]:
        path = self._path(serv_id)
        if path is None:
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            data, saved_at = payload["data"], float(payload["saved_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if not allow_stale and self._clock() - saved_at > self._ttl:
            return None
        return data

    def set(self, serv_id: str, data: dict) -> bool:
        path = self._path(serv_id)
        if path is None:
            return False
        try:
            _atomic_write_json(path, {"saved_at": self._clock(), "data": data})
            return True
        except OSError:
            return False  # 디스크 문제로 캐시를 못 써도 응답 자체는 계속한다
