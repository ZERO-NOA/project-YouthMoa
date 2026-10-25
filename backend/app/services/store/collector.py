"""스냅샷 수집기: 목록 전체를 페이지 단위로 받아 파일로 저장한다.

- 페이지마다 진행 상황을 임시 파일(.partial.json)에 저장 → 중간에 실패해도 이어서 받을 수 있다.
- 충분히 못 받았으면(보고된 총건수의 90% 미만) 기존 스냅샷을 덮어쓰지 않는다.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.services.store.snapshot import _atomic_write_json, write_snapshot

MIN_COMPLETENESS = 0.9


def collect_snapshot(
    fetch_page: Callable[[int, int], dict],  # (page, size) -> {"total_count", "items"}
    path,
    *,
    life_codes: tuple,
    page_size: int = 100,
    max_pages: int = 60,
    delay: float = 1.0,
    fresh: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> dict:
    path = Path(path)
    partial_path = path.with_name(path.name + ".partial.json")
    items: list = []
    seen: set = set()
    reported_total = 0
    next_page = 1

    if partial_path.exists() and not fresh:
        try:
            part = json.loads(partial_path.read_text(encoding="utf-8"))
            if part.get("life_codes") == list(life_codes) and part.get("page_size") == page_size:
                items, reported_total, next_page = part["items"], part["reported_total"], part["next_page"]
                seen = {i["id"] for i in items}
                log(f"이전 진행분 {len(items)}건을 이어받습니다 (다음 {next_page}페이지부터)")
        except (OSError, ValueError, KeyError):
            items, seen, reported_total, next_page = [], set(), 0, 1

    t_start = time.monotonic()
    for page in range(next_page, max_pages + 1):
        t0 = time.monotonic()
        result = fetch_page(page, page_size)  # 실패하면 예외 → partial 이 남아 다음 실행에서 이어짐
        reported_total = result["total_count"] or reported_total
        page_items = result["items"]
        added = 0
        for it in page_items:
            if it["id"] not in seen:
                seen.add(it["id"])
                items.append(it)
                added += 1
        log(f"  {page}페이지: {len(page_items)}건 수신(신규 {added}) / 누계 {len(items)} / 전체 {reported_total} "
            f"({time.monotonic() - t0:.1f}초)")
        done = not page_items or page * page_size >= reported_total
        _atomic_write_json(partial_path, {
            "life_codes": list(life_codes), "page_size": page_size, "reported_total": reported_total,
            "next_page": page + 1, "items": items,
        })
        if done:
            break
        sleep(delay)

    if reported_total and len(items) < reported_total * MIN_COMPLETENESS:
        raise RuntimeError(
            f"수집 건수가 부족합니다({len(items)}/{reported_total}). 기존 스냅샷은 유지합니다. "
            f"다시 실행하면 이어서 받습니다.")

    meta = {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "life_codes": list(life_codes),
        "reported_total": reported_total,
        "elapsed_sec": round(time.monotonic() - t_start, 1),
    }
    write_snapshot(path, items, meta)
    partial_path.unlink(missing_ok=True)
    return {**meta, "count": len(items)}
