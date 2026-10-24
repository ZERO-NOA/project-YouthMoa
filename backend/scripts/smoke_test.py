"""실제 API 를 호출해 코드·필드·필터를 검증하는 스크립트 (v4).

실행: (backend/ 에서)  python scripts\\smoke_test.py

- 호출 수: 약 25회(느리면 재시도 포함) (일일 한도 1,000건 중 극소량)
- 서비스키는 출력하지 않는다.
- 원본 XML 은 backend/.smoke_output/ 에 저장된다(커밋 금지).
- 끝의 '=== 결과 요약 ===' 블록을 복사해서 공유하면 된다.
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.clients.welfare_client import WelfareClient  # noqa: E402
from app.services.welfare_codes import CATEGORY_TO_THEMES, LIFE_STAGE, THEME  # noqa: E402
from app.core.welfare_config import env_report, get_settings  # noqa: E402
from app.core.errors import WelfareAPIError  # noqa: E402
from app.services.parsers import welfare_parser as P  # noqa: E402
from app.services.parsers.welfare_parser import normalize_name  # noqa: E402

OUT = ROOT / ".smoke_output"
OUT.mkdir(exist_ok=True)

results: list[tuple[str, str, str]] = []  # (상태, 항목, 메모)  상태: OK / FAIL / INFO

# 사용법: python scripts\\smoke_test.py        → 전체
#         python scripts\\smoke_test.py 7 4    → [1] + 7번, 4번 섹션만
ARGS = {a for a in sys.argv[1:] if a.isdigit()}


def want(n: int) -> bool:
    return n == 1 or not ARGS or str(n) in ARGS


CORE_LIST = {"id", "title", "summary", "province", "life_stages"}
CORE_DETAIL = {"id", "title", "target_detail", "criteria", "benefit", "apply_method"}


def record(status: str, name: str, note: str = "") -> None:
    results.append((status, name, note))
    print(f"  [{status:<4}] {name}" + (f" — {note}" if note else ""))


def ok(cond: bool) -> str:
    return "OK" if cond else "FAIL"


def raw_items(xml_text: str, container: str) -> list[dict]:
    root = P._parse_xml(xml_text)
    return [
        P._to_obj(el) for el in root.iter() if P._local(el.tag) == container
    ]


def detail_raw(xml_text: str) -> dict:
    """상세 응답에서 servId 를 자식으로 가진 노드를 dict 로 돌려준다(래퍼 태그명에 의존하지 않음)."""
    root = P._parse_xml(xml_text)
    for el in root.iter():
        if any(P._local(c.tag) == "servId" for c in el):
            obj = P._to_obj(el)
            return obj if isinstance(obj, dict) else {}
    return {}


def unmapped(tags: set, mapping: dict):
    known = {k for keys in mapping.values() for k in keys}
    extra = sorted(t for t in tags if t not in known and t not in {"resultCode", "resultMessage"})
    missing = sorted(f for f, keys in mapping.items() if not any(k in tags for k in keys))
    return extra, missing


def share(items: list, field: str, name: str):
    """field(리스트) 가 비어 있지 않은 항목 중 name 을 포함하는 비율. (포함 수, 대상 수)"""
    pool = [i for i in items if i.get(field)]
    hit = [i for i in pool if name in i[field]]
    return len(hit), len(pool)


LATENCIES: list = []


CLIENT = None  # 느린 호출의 시도별 내역을 보여주기 위한 참조


def attempts_text() -> str:
    a = getattr(CLIENT, "last_attempts", None) or []
    return ", ".join(f"{r} {sec:.1f}s" for r, sec in a)


def timed(label: str, fn):
    """호출 시간을 재서 기록한다. 3초 넘게 걸린 호출은 바로 알려준다."""
    if sys.stderr.isatty():  # 콘솔에서만: 지금 어떤 호출을 기다리는지 한 줄로 표시
        sys.stderr.write(f"\r      … 호출 중: {label} (최대 약 40초)".ljust(70))
        sys.stderr.flush()
    t0 = time.monotonic()
    try:
        return fn()
    finally:
        if sys.stderr.isatty():
            sys.stderr.write("\r" + " " * 70 + "\r")
            sys.stderr.flush()
        dt = time.monotonic() - t0
        LATENCIES.append(dt)
        if dt >= 3:
            print(f"      · 느린 호출: {label} {dt:.1f}초 (시도별: {attempts_text() or '기록 없음'})")


def fetch(client, label, **kw):
    """목록 호출 + 파싱. 실패하면 (None, None, 오류메시지)."""
    time.sleep(0.5)  # 과호출 방지
    try:
        xml = timed(label, lambda: client.fetch_list(**kw))
        return P.parse_list(xml), xml, None
    except WelfareAPIError as e:
        return None, None, f"{e.code}: {e.message}"


def print_summary(interrupted: bool = False) -> int:
    print("\n=== 결과 요약 (이 블록을 복사해서 공유하세요) ===")
    if interrupted:
        print("※ 사용자가 중단해서 아래는 중단 시점까지의 결과입니다.")
    for status, name, note in results:
        print(f"{status:<4} | {name} | {note}")
    if LATENCIES:
        print(f"호출 {len(LATENCIES)}회 응답시간: 평균 {statistics.mean(LATENCIES):.1f}초, 최대 {max(LATENCIES):.1f}초")
    print(f"원본 XML 저장 위치: {OUT}")
    return 130 if interrupted else (0 if all(st != "FAIL" for st, _, _ in results) else 2)


def main() -> int:
    s = get_settings()
    print("=== YouthMoa 공공 API 스모크 테스트 v4 ===")
    if not s.service_key:
        print("DATA_GO_KR_SERVICE_KEY 를 찾지 못했습니다. .env 탐색 결과:")
        print(env_report())
        return 1
    print(f"서비스키 설정됨 (길이 {len(s.service_key)}자, 값은 출력하지 않음)")
    # 점검용: 호출당 최대 20초 x 2회(재시도 1회). 멈춘 호출 때문에 오래 기다리지 않도록 한다.
    client = WelfareClient(s.service_key, base_url=s.base_url, timeout=20, retries=1)
    global CLIENT
    CLIENT = client
    code = s.search_code

    # [1] 목록 -------------------------------------------------------------
    print("\n[1] 목록 조회 (필터 없음)")
    parsed, xml, err = fetch(client, "목록", size=5, search_code=code)
    base_total, first_id = None, None
    if err:
        record("FAIL", "목록 호출", err)
        return 2
    (OUT / "list_raw.xml").write_text(xml, encoding="utf-8")
    base_total = parsed["total_count"]
    record("OK", "목록 호출·파싱", f"전체 {base_total}건")
    raws = raw_items(xml, "servList")
    tags = set(raws[0].keys()) if raws else set()
    extra, missing = unmapped(tags, P._LIST_KEYS)
    core_miss = [m for m in missing if m in CORE_LIST]
    record(ok(not core_miss), "목록 필드 매핑(핵심)", f"핵심 누락={core_miss or '없음'}")
    if [m for m in missing if m not in CORE_LIST]:
        print(f"      · 응답에 없는 선택 필드: {[m for m in missing if m not in CORE_LIST]}")
    if extra:
        print(f"      · 매핑되지 않은 실제 태그: {extra}")
    print("      · 원본 값 샘플(구분자 확인용):")
    for r in raws[:3]:
        print(f"        - {r.get('servNm')} | 시도={r.get('ctpvNm')!r} 시군구={r.get('sggNm')!r}")
        print(f"          생애주기={r.get('lifeNmArray')!r} 주제={r.get('intrsThemaNmArray')!r}")
    if parsed["items"]:
        first_id = parsed["items"][0]["id"]
        it = parsed["items"][0]
        print(f"      · 변환 결과: {it['title']} / {it['province']} {it['city']} / 생애주기={it['life_stages']} / 주제={it['themes']}")

    if want(2):
        # [2] 상세 -------------------------------------------------------------
        print("\n[2] 상세 조회")
        if first_id:
            time.sleep(0.3)
            try:
                dxml = timed('상세', lambda: client.fetch_detail(first_id))
                (OUT / "detail_raw.xml").write_text(dxml, encoding="utf-8")
                det = P.parse_detail(dxml)
                raw = [detail_raw(dxml)]
                tags = set(raw[0].keys())
                extra, missing = unmapped(tags, P._DETAIL_KEYS)
                core_miss = [m for m in missing if m in CORE_DETAIL]
                record("OK", "상세 호출·파싱", det["title"])
                record(ok(not core_miss), "상세 필드 매핑(핵심)", f"핵심 누락={core_miss or '없음'}")
                if [m for m in missing if m not in CORE_DETAIL]:
                    print(f"      · 응답에 없는 선택 필드: {[m for m in missing if m not in CORE_DETAIL]}")
                if extra:
                    print(f"      · 매핑되지 않은 실제 태그: {extra}")
                print(f"      · 중첩 목록 개수 — 문의처 {len(det['contacts'])}, 근거 {len(det['laws'])}, 서식 {len(det['forms'])}")
                for key in ("inqplCtadrList", "baslawList", "basfrmList"):
                    v = raw[0].get(key)
                    if v:
                        print(f"      · {key} 원본 샘플: {str(v)[:160]}")
            except WelfareAPIError as e:
                record("FAIL", "상세 호출", f"{e.code}: {e.message}")
        else:
            record("FAIL", "상세 조회", "목록에서 servId 를 얻지 못함")

    if want(3):
        # [3] 생애주기 코드 -----------------------------------------------------
        print("\n[3] 생애주기 코드 검증 (필터 결과의 '전부'가 해당 이름을 포함해야 OK)")
        life_totals = {}
        for life_code in ("003", "004"):
            expected = normalize_name(LIFE_STAGE[life_code])
            r, _, err = fetch(client, life_code, size=30, life=life_code, search_code=code)
            if err:
                record("FAIL", f"lifeArray={life_code}", err)
                continue
            life_totals[life_code] = r["total_count"]
            hit, pool = share(r["items"], "life_stages", expected)
            narrowed = bool(base_total) and 0 < r["total_count"] < base_total
            record(ok(pool > 0 and hit / pool >= 0.9 and narrowed),
                   f"코드 {life_code} = '{expected}'",
                   f"총 {r['total_count']}건 / 표본 {pool}건 중 '{expected}' 포함 {hit}건")
        if len(life_totals) == 2:
            r, _, err = fetch(client, "union", size=5, life="003,004", search_code=code)
            if r:
                a_, b_, u = life_totals["003"], life_totals["004"], r["total_count"]
                record(ok(max(a_, b_) <= u <= a_ + b_), "쉼표 합집합 '003,004'",
                       f"{u}건 (003={a_}, 004={b_}, 합집합이면 {max(a_, b_)} ≤ 값 ≤ {a_ + b_})")
            else:
                record("FAIL", "쉼표 합집합 '003,004'", err)

    if want(4):
        # [4] 관심주제 코드 (전체) -----------------------------------------------
        print("\n[4] 관심주제 코드 검증 (생애주기 필터 없이, 14개 전부)")
        theme_totals = {}
        for tcode, tname in THEME.items():
            expected = normalize_name(tname)
            r, _, err = fetch(client, tcode, size=30, theme=tcode, search_code=code)
            if err:
                record("FAIL", f"주제 {tcode}", err)
                continue
            theme_totals[tcode] = r["total_count"]
            hit, pool = share(r["items"], "themes", expected)
            names = sorted({n for i in r["items"] for n in i["themes"]})
            if r["total_count"] == 0:
                record("FAIL", f"주제 {tcode} = '{expected}'", "결과 0건 → 코드 의미 확인 필요")
            else:
                record(ok(pool > 0 and hit / pool >= 0.9), f"주제 {tcode} = '{expected}'",
                       f"총 {r['total_count']}건 / 표본 {pool}건 중 포함 {hit}건" + ("" if hit == pool else f" (응답 주제명={names[:5]})"))
        # 합집합 검증은 '둘 다 결과가 있고, 서로 포함 관계가 아닌' 쌍이어야 의미가 있다.
        # (예: 040 ⊂ 120 이면 합집합 결과가 120 과 같아져 판정 불가)
        tried, conclusive, first_pair = [], None, None
        for c1, c2 in (("040", "120"), ("050", "100"), ("070", "110"), ("010", "050")):
            a_, b_ = theme_totals.get(c1), theme_totals.get(c2)
            if not a_ or not b_:
                continue
            r, _, err = fetch(client, f"theme-union {c1},{c2}", size=5, theme=f"{c1},{c2}", search_code=code)
            if not r:
                tried.append(f"{c1},{c2}: 미지원({err})")
                continue
            u = r["total_count"]
            tried.append(f"{c1}={a_} + {c2}={b_} → {u}건")
            if first_pair is None:
                first_pair = (c1, c2, a_, b_, u)
            if u > max(a_, b_):
                conclusive = (c1, c2, u)
                break
            if len(tried) >= 3:
                break
        if conclusive:
            record("INFO", "주제 쉼표 합집합", f"동작함: {tried[-1]} (큰 쪽보다 많음)")
        elif first_pair:
            c1, c2, a_, b_, u = first_pair
            r, _, _ = fetch(client, f"theme-union {c2},{c1}", size=5, theme=f"{c2},{c1}", search_code=code)
            rev = r["total_count"] if r else None
            if rev is not None and a_ != b_ and u == b_ and rev == a_:
                verdict = (f"마지막 값만 적용되는 것으로 보임 ({c1},{c2}={u}건=뒤 코드 {c2} 단독, "
                           f"{c2},{c1}={rev}건=뒤 코드 {c1} 단독) → 주제 다중값은 사용 금지")
            elif rev is not None and rev != u:
                verdict = f"순서에 따라 결과가 다름({c1},{c2}={u}건 / {c2},{c1}={rev}건) → 신뢰할 수 없음, 사용 금지"
            else:
                verdict = f"판정 불가(순서를 바꿔도 {rev}건): " + " | ".join(tried)
            record("INFO", "주제 쉼표 합집합", verdict)
        else:
            record("INFO", "주제 쉼표 합집합", "결과가 있는 코드 쌍을 찾지 못해 건너뜀")

    if want(5):
        # [5] 지역 필터 ----------------------------------------------------------
        print("\n[5] 지역 필터")
        r, _, err = fetch(client, "region", size=30, province="서울특별시", search_code=code)
        if r:
            hit = sum(1 for i in r["items"] if i["province"] == "서울특별시")
            record(ok(r["total_count"] > 0 and hit == len(r["items"])), "ctpvNm=서울특별시",
                   f"총 {r['total_count']}건, 표본 {len(r['items'])}건 중 서울 {hit}건")
        else:
            record("FAIL", "ctpvNm 필터", err)
        r, _, err = fetch(client, "city", size=30, province="서울특별시", city="강남구", search_code=code)
        if r and r["items"]:
            hit = sum(1 for i in r["items"] if i["city"] == "강남구")
            record(ok(hit == len(r["items"])), "sggNm=강남구 (시·군·구 필터)",
                   f"총 {r['total_count']}건, 표본 {len(r['items'])}건 중 강남구 {hit}건")
        else:
            record("INFO", "sggNm 필터", f"결과 없음/미지원 ({err or '0건'})")

    if want(6):
        # [6] 키워드 -------------------------------------------------------------
        print("\n[6] 키워드 검색")
        r, _, err = fetch(client, "키워드", size=3, keyword="월세", search_code=code)
        if r:
            record(ok(base_total is None or r["total_count"] < base_total), "키워드 검색",
                   f"'월세' {r['total_count']}건 / 무필터 {base_total}건: {[i['title'] for i in r['items']][:3]}")
        else:
            record("FAIL", "키워드 검색", err)

    if want(7):
        # [7] 페이지 크기·넘김 ------------------------------------------------------
        print("\n[7] 페이지 크기·넘김")
        r1, _, err = fetch(client, "size100", size=100, page=1, life="003,004", search_code=code)
        if r1:
            record(ok(len(r1["items"]) == 100), "numOfRows=100",
                   f"{len(r1['items'])}건 수신 (100이 안 되면 최대 허용 건수가 더 작은 것)")
            r2, _, err2 = fetch(client, "page2", size=100, page=2, life="003,004", search_code=code)
            if r2:
                ids1, ids2 = {i["id"] for i in r1["items"]}, {i["id"] for i in r2["items"]}
                record(ok(bool(ids2) and not (ids1 & ids2)), "2페이지가 1페이지와 겹치지 않음",
                       f"1p {len(ids1)}건, 2p {len(ids2)}건, 중복 {len(ids1 & ids2)}건")
            else:
                record("FAIL", "2페이지 조회", err2)
        else:
            record("FAIL", "numOfRows=100", err)

    return print_summary()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # Ctrl+C: 지금까지 모은 결과를 보여주고 끝낸다
        sys.exit(print_summary(interrupted=True))
