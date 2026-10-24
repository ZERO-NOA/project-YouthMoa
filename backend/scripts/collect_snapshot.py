"""청소년·청년 목록 스냅샷을 수집해 파일로 저장한다.

실행: (backend/ 에서)  python scripts\\collect_snapshot.py
옵션: --fresh        이전에 중단된 진행분을 무시하고 처음부터
      --life 003,004  수집할 생애주기 코드(기본: 설정의 DEFAULT_LIFE_CODE)
      --delay 1.0     페이지 사이 대기(초)

- 호출 수: 100건씩 약 18회. 공공 API 가 느릴 수 있어(평균 9초, 최대 57초 관측) 수 분 걸릴 수 있다.
- 중간에 실패/중단돼도 다시 실행하면 이어서 받는다.
- 결과: backend/data/welfare_snapshot.json  (서버는 파일이 바뀌면 자동으로 다시 읽는다)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.clients.welfare_client import WelfareClient  # noqa: E402
from app.core.welfare_config import env_report, get_settings  # noqa: E402
from app.core.errors import WelfareAPIError  # noqa: E402
from app.services.welfare_service import WelfareService  # noqa: E402
from app.services.store.collector import collect_snapshot  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--life", default=None)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--page-size", type=int, default=100)
    args = ap.parse_args()

    s = get_settings()
    if not s.service_key:
        print("DATA_GO_KR_SERVICE_KEY 를 찾지 못했습니다:")
        print(env_report())
        return 1
    life = tuple(c.strip() for c in (args.life or s.default_life_code).split(",") if c.strip())
    # 수집은 오래 걸려도 끝까지 받는 게 목적 → 타임아웃을 넉넉히, 재시도 2회
    client = WelfareClient(s.service_key, base_url=s.base_url, timeout=40, retries=2)
    service = WelfareService(client, default_life=",".join(life), search_code=s.search_code)

    print(f"스냅샷 수집 시작: 생애주기 {','.join(life)} / 저장 위치 {s.snapshot_path}")
    try:
        meta = collect_snapshot(
            lambda page, size: service.fetch_live_page(life=",".join(life), page=page, size=size),
            s.snapshot_path, life_codes=life, page_size=args.page_size,
            delay=args.delay, fresh=args.fresh,
        )
    except WelfareAPIError as e:
        print(f"\n공공 API 오류: {e.code} — {e.message}\n다시 실행하면 받은 곳부터 이어서 진행합니다.")
        return 2
    except RuntimeError as e:
        print(f"\n{e}")
        return 3
    except KeyboardInterrupt:
        print("\n중단했습니다. 다시 실행하면 받은 곳부터 이어서 진행합니다.")
        return 130
    print(f"\n완료: {meta['count']}건 저장 (공공 API 보고 총 {meta['reported_total']}건, {meta['elapsed_sec']}초)")
    print(f"수집 시각(UTC): {meta['collected_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
