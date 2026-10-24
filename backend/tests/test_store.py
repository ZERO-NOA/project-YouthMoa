"""스냅샷·디테일 저장소·수집기·서비스 연동 테스트 (표준 unittest)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.clients.welfare_client import WelfareClient  # noqa: E402
from app.core.errors import WelfareAPIError  # noqa: E402
from app.services.welfare_service import WelfareService  # noqa: E402
from app.services.store.collector import collect_snapshot  # noqa: E402
from app.services.store.detail_store import DetailStore  # noqa: E402
from app.services.store.snapshot import SnapshotStore, write_snapshot  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def fx(name):
    return (FIX / name).read_text(encoding="utf-8")


class FakeHttp:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, params, timeout):
        self.calls.append((url, dict(params)))
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


def make_client(http, **kw):
    return WelfareClient("KEY", http_get=http, sleep=lambda s: None, **kw)


def item(i, life=("청년",), themes=("주거",), prov="서울특별시", city="강남구", title=None, summary="요약"):
    return {"id": f"S{i:03d}", "title": title or f"서비스{i}", "summary": summary, "province": prov, "city": city,
            "department": None, "life_stages": list(life), "themes": list(themes), "targets": [],
            "support_cycle": None, "provision_type": None, "apply_type": None,
            "detail_url": f"https://bokjiro/{i}", "views": i, "updated_at": None}


ITEMS = [
    item(1, life=("청년",), themes=("주거",), title="청년 월세 지원"),
    item(2, life=("청소년",), themes=("교육",), prov="부산광역시", city="해운대구", title="청소년 교육비"),
    item(3, life=("청소년", "청년"), themes=("일자리", "교육"), title="청년 일자리 교육"),
    item(4, life=("청년", "노년"), themes=("주거",), prov="경기도", city="하남시", summary="월세 보조"),
    item(5, life=(), themes=(), title="분류 없음"),
]
META = {"life_codes": ["003", "004"], "collected_at": "2026-10-24T00:00:00+00:00", "reported_total": 5}


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "snap.json"
        write_snapshot(self.path, ITEMS, META)
        self.snap = SnapshotStore(self.path)
        self.assertTrue(self.snap.refresh())

    def tearDown(self):
        self.tmp.cleanup()

    def ids(self, **kw):
        r = self.snap.search(**kw)
        return [i["id"] for i in r["items"]]

    def test_life_filter_is_union_of_names(self):
        self.assertEqual(self.ids(life_codes=("004",), size=10), ["S001", "S003", "S004"])
        self.assertEqual(self.ids(life_codes=("003",), size=10), ["S002", "S003"])
        self.assertEqual(self.ids(life_codes=("003", "004"), size=10), ["S001", "S002", "S003", "S004"])

    def test_items_without_life_are_excluded_when_filtering(self):
        self.assertNotIn("S005", self.ids(life_codes=("003", "004"), size=10))

    def test_theme_province_city(self):
        self.assertEqual(self.ids(life_codes=("004",), theme_codes=("040",), size=10), ["S001", "S004"])
        self.assertEqual(self.ids(life_codes=("003", "004"), province="부산광역시", size=10), ["S002"])
        self.assertEqual(self.ids(life_codes=("004",), province="경기도", city="하남시", size=10), ["S004"])
        self.assertEqual(self.ids(life_codes=("004",), theme_codes=("050", "100"), size=10), ["S003"])  # 주제 합집합

    def test_keyword_tokens_and_case_and_summary(self):
        self.assertEqual(self.ids(life_codes=("004",), keyword="월세", size=10), ["S001", "S004"])  # 제목 + 요약
        self.assertEqual(self.ids(life_codes=("004",), keyword="청년 월세", size=10), ["S001"])  # 모든 단어 포함
        self.assertEqual(self.ids(life_codes=("004",), keyword="없는단어", size=10), [])

    def test_pagination_and_total(self):
        r = self.snap.search(life_codes=("003", "004"), page=2, size=2)
        self.assertEqual((r["total_count"], r["page"], r["size"]), (4, 2, 2))
        self.assertEqual([i["id"] for i in r["items"]], ["S003", "S004"])
        self.assertEqual(self.snap.search(life_codes=("004",), page=9, size=2)["items"], [])

    def test_unknown_code_means_cannot_answer_locally(self):
        self.assertIsNone(self.snap.search(life_codes=("999",)))
        self.assertIsNone(self.snap.search(life_codes=("004",), theme_codes=("XYZ",)))

    def test_covers(self):
        self.assertTrue(self.snap.covers(("004",)))
        self.assertTrue(self.snap.covers(("003", "004")))
        self.assertFalse(self.snap.covers(("004", "005")))
        self.assertFalse(self.snap.covers(()))

    def test_find_by_id(self):
        self.assertEqual(self.snap.find("S002")["title"], "청소년 교육비")
        self.assertIsNone(self.snap.find("nope"))

    def test_refresh_picks_up_new_file_and_survives_corruption(self):
        write_snapshot(self.path, ITEMS[:1], META)
        import os
        os.utime(self.path, (self.snap._mtime + 5, self.snap._mtime + 5))  # mtime 해상도 문제 방지
        self.snap.refresh()
        self.assertEqual(len(self.snap.search(life_codes=("004",), size=10)["items"]), 1)
        self.path.write_text("{ 깨진 json", encoding="utf-8")
        os.utime(self.path, (self.snap._mtime + 10, self.snap._mtime + 10))
        self.assertTrue(self.snap.refresh())  # 직전 데이터 유지
        self.assertEqual(len(self.snap.search(life_codes=("004",), size=10)["items"]), 1)

    def test_missing_file(self):
        s = SnapshotStore(Path(self.tmp.name) / "none.json")
        self.assertFalse(s.refresh())
        self.assertFalse(s.available)

    def test_failed_write_keeps_old_file_and_leaves_no_temp(self):
        before = self.path.read_text(encoding="utf-8")
        with self.assertRaises(TypeError):
            write_snapshot(self.path, [{"id": "x", "bad": object()}], META)  # JSON 직렬화 불가
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], ["snap.json"])


class DetailStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = [1000.0]
        self.store = DetailStore(Path(self.tmp.name) / "d", ttl_seconds=100, clock=lambda: self.now[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_ttl_and_stale(self):
        self.assertTrue(self.store.set("WLF1", {"title": "가"}))
        self.assertEqual(self.store.get("WLF1"), {"title": "가"})
        self.now[0] += 101
        self.assertIsNone(self.store.get("WLF1"))
        self.assertEqual(self.store.get("WLF1", allow_stale=True), {"title": "가"})

    def test_unsafe_ids_rejected_and_nothing_written_outside(self):
        for bad in ("../evil", "a/b", "a\\b", "", " ", "x" * 65, "..", "a.json", None):
            self.assertFalse(self.store.set(bad, {"x": 1}), bad)
            self.assertIsNone(self.store.get(bad), bad)
        self.assertFalse((Path(self.tmp.name) / "evil.json").exists())

    def test_corrupt_file_is_a_miss(self):
        self.store.set("WLF2", {"a": 1})
        (Path(self.tmp.name) / "d" / "WLF2.json").write_text("not json", encoding="utf-8")
        self.assertIsNone(self.store.get("WLF2", allow_stale=True))


def fake_pages(total, size_per_page_items=None):
    """fetch_page(page, size) 가짜. 1..total 의 id 를 페이지로 나눠 돌려준다."""
    calls = []

    def fetch(page, size):
        calls.append(page)
        start = (page - 1) * size
        ids = range(start + 1, min(start + size, total) + 1)
        return {"total_count": total, "page": page, "size": size, "items": [item(i) for i in ids]}

    fetch.calls = calls
    return fetch


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "snap.json"
        self.quiet = lambda msg: None

    def tearDown(self):
        self.tmp.cleanup()

    def run_collect(self, fetch, **kw):
        return collect_snapshot(fetch, self.path, life_codes=("003", "004"), page_size=100,
                                sleep=lambda s: None, log=self.quiet, **kw)

    def test_collects_all_pages_and_writes_meta(self):
        fetch = fake_pages(250)
        meta = self.run_collect(fetch)
        self.assertEqual(fetch.calls, [1, 2, 3])
        self.assertEqual(meta["count"], 250)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["items"]), 250)
        self.assertEqual(data["meta"]["life_codes"], ["003", "004"])
        self.assertEqual(data["meta"]["reported_total"], 250)
        self.assertFalse(Path(str(self.path) + ".partial.json").exists())  # 완료 후 진행 파일 삭제

    def test_dedupes_items_across_pages(self):
        def fetch(page, size):  # 2페이지가 1페이지와 일부 겹치는 경우(수집 중 목록이 변동)
            ids = [1, 2, 3] if page == 1 else [3, 4, 5]
            return {"total_count": 5, "items": [item(i) for i in ids]}
        meta = collect_snapshot(fetch, self.path, life_codes=("004",), page_size=3,
                                sleep=lambda s: None, log=self.quiet)
        self.assertEqual(meta["count"], 5)

    def test_resume_after_failure_does_not_refetch_done_pages(self):
        good = fake_pages(250)

        def flaky(page, size):
            if page == 3 and not getattr(flaky, "recovered", False):
                raise WelfareAPIError("UPSTREAM_TIMEOUT", "t", 504)
            return good(page, size)

        with self.assertRaises(WelfareAPIError):
            self.run_collect(flaky)
        self.assertTrue(Path(str(self.path) + ".partial.json").exists())
        self.assertFalse(self.path.exists())  # 미완성 결과는 정식 파일로 나오지 않는다
        flaky.recovered = True
        good.calls.clear()
        meta = self.run_collect(flaky)
        self.assertEqual(good.calls, [3])  # 1,2페이지는 다시 받지 않음
        self.assertEqual(meta["count"], 250)

    def test_fresh_ignores_partial(self):
        part = Path(str(self.path) + ".partial.json")
        part.write_text(json.dumps({"life_codes": ["003", "004"], "page_size": 100, "reported_total": 250,
                                    "next_page": 3, "items": [item(1)]}), encoding="utf-8")
        fetch = fake_pages(250)
        self.run_collect(fetch, fresh=True)
        self.assertEqual(fetch.calls, [1, 2, 3])

    def test_partial_with_different_params_is_not_reused(self):
        part = Path(str(self.path) + ".partial.json")
        part.write_text(json.dumps({"life_codes": ["004"], "page_size": 100, "reported_total": 250,
                                    "next_page": 3, "items": [item(1)]}), encoding="utf-8")
        fetch = fake_pages(250)
        self.run_collect(fetch)  # life_codes 가 달라서 처음부터
        self.assertEqual(fetch.calls, [1, 2, 3])

    def test_incomplete_collection_never_overwrites_existing_snapshot(self):
        write_snapshot(self.path, ITEMS, META)
        before = self.path.read_text(encoding="utf-8")

        def short(page, size):  # 총 1000건이라면서 100건만 주고 끝
            return {"total_count": 1000, "items": [item(i) for i in range(1, 101)] if page == 1 else []}

        with self.assertRaises(RuntimeError):
            self.run_collect(short)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)


def live_service(http, **kw):
    return WelfareService(make_client(http), default_life="003,004", clock=lambda: 0.0, **kw)


class ServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "snap.json"
        write_snapshot(self.path, ITEMS, META)
        self.snap = SnapshotStore(self.path)
        self.http = FakeHttp((200, fx("list_sample.xml")))

    def tearDown(self):
        self.tmp.cleanup()

    def svc(self, **kw):
        return live_service(self.http, snapshot=self.snap, **kw)

    def test_default_search_served_from_snapshot_without_api_call(self):
        r = self.svc().search(size=10)
        self.assertEqual(self.http.calls, [])
        self.assertEqual(r["source"], "snapshot")
        self.assertEqual(r["as_of"], META["collected_at"])
        self.assertEqual(r["total_count"], 4)

    def test_filters_work_through_service(self):
        r = self.svc().search(keyword="월세", province="서울특별시", size=10)
        self.assertEqual([i["id"] for i in r["items"]], ["S001"])

    def test_falls_back_to_live_when_snapshot_cannot_answer(self):
        s = self.svc()
        s.search(life="005")  # 수집 범위 밖 생애주기
        s.search(youth_only=False)  # 전연령
        s.search(target="020")  # 대상특성 필터는 스냅샷에 없음
        s.search(theme="ABC")  # 해석 불가 코드
        self.assertEqual(len(self.http.calls), 4)
        self.assertEqual(s.search(life="005")["source"], "live")

    def test_live_source_ignores_snapshot(self):
        self.svc(source="live").search()
        self.assertEqual(len(self.http.calls), 1)

    def test_snapshot_source_never_calls_api(self):
        s = self.svc(source="snapshot")
        self.assertEqual(s.search()["source"], "snapshot")
        with self.assertRaises(WelfareAPIError) as cm:
            s.search(youth_only=False)
        self.assertEqual((cm.exception.code, cm.exception.http_status), ("SNAPSHOT_UNAVAILABLE", 503))
        self.assertEqual(self.http.calls, [])

    def test_missing_snapshot_file_falls_back_to_live_in_auto(self):
        s = live_service(self.http, snapshot=SnapshotStore(Path(self.tmp.name) / "nope.json"))
        self.assertEqual(s.search()["source"], "live")
        self.assertEqual(len(self.http.calls), 1)

    def test_collect_all_bypasses_snapshot(self):
        list(self.svc().collect_all(page_size=10))
        self.assertEqual(len(self.http.calls), 1)  # 스냅샷이 있어도 공공 API 를 직접 호출

    def test_detail_gets_link_from_snapshot(self):
        http = FakeHttp((200, fx("detail_sample.xml").replace("WLF00001", "S001")))
        s = live_service(http, snapshot=self.snap)
        d = s.detail("S001")
        self.assertEqual(d["detail_url"], "https://bokjiro/1")
        self.assertEqual(s.detail("S001")["detail_url"], "https://bokjiro/1")  # 캐시 경로에서도 유지

    def test_detail_disk_cache_avoids_api(self):
        store = DetailStore(Path(self.tmp.name) / "d")
        http = FakeHttp((200, fx("detail_sample.xml")))
        live_service(http, detail_store=store).detail("WLF00001")
        self.assertEqual(len(http.calls), 1)
        http2 = FakeHttp((200, fx("detail_sample.xml")))
        again = live_service(http2, detail_store=store).detail("WLF00001")  # 새 서비스(=서버 재시작)
        self.assertEqual(http2.calls, [])
        self.assertEqual(again["title"], "청년 월세 지원")

    def test_expired_disk_cache_used_when_api_times_out(self):
        now = [0.0]
        store = DetailStore(Path(self.tmp.name) / "d", ttl_seconds=10, clock=lambda: now[0])
        http = FakeHttp((200, fx("detail_sample.xml")))
        live_service(http, detail_store=store).detail("WLF00001")
        now[0] = 9999  # 디스크 캐시 만료
        http2 = FakeHttp(TimeoutError("t"))
        s2 = WelfareService(make_client(http2, retries=0), detail_store=store, clock=lambda: 0.0)
        self.assertEqual(s2.detail("WLF00001")["title"], "청년 월세 지원")  # 만료됐어도 장애 시 대체 응답
        self.assertEqual(len(http2.calls), 1)

    def test_detail_not_found_is_not_cached_to_disk(self):
        store = DetailStore(Path(self.tmp.name) / "d")
        http = FakeHttp((200, fx("no_data.xml")))
        with self.assertRaises(WelfareAPIError):
            live_service(http, detail_store=store).detail("NOPE1")
        self.assertIsNone(store.get("NOPE1", allow_stale=True))


if __name__ == "__main__":
    unittest.main()
