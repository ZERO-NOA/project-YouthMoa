"""표준 라이브러리 unittest 만 사용 (pytest 없이도 실행 가능).

실행: (backend/ 에서)  python -m unittest discover -s tests -v
fixtures 의 XML 은 문서/사례를 바탕으로 만든 '가짜' 응답이다.
실제 응답과의 일치 여부는 scripts/smoke_test.py 로 확인한다.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.clients.welfare_client import WelfareClient  # noqa: E402
from app.core.errors import WelfareAPIError, validation_message  # noqa: E402
from app.services.parsers import welfare_parser as parser  # noqa: E402
from app.services.welfare_service import WelfareService  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class ParserListTests(unittest.TestCase):
    def test_parse_list_basic(self):
        r = parser.parse_list(fx("list_sample.xml"))
        self.assertEqual(r["total_count"], 2)
        self.assertEqual(r["page"], 1)
        self.assertEqual(len(r["items"]), 2)

    def test_item_fields_normalized(self):
        a = parser.parse_list(fx("list_sample.xml"))["items"][0]
        self.assertEqual(a["id"], "WLF00001")
        self.assertEqual(a["title"], "청년 월세 지원")
        self.assertEqual(a["life_stages"], ["청년"])
        self.assertEqual(a["province"], "서울특별시")
        self.assertEqual(a["city"], "강남구")
        self.assertEqual(a["department"], "주택정책과")
        self.assertEqual(a["apply_type"], "방문")
        self.assertEqual(a["views"], 1234)
        self.assertEqual(a["updated_at"], "2026-07-14")

    def test_multi_values_and_empty_fields(self):
        b = parser.parse_list(fx("list_sample.xml"))["items"][1]
        self.assertEqual(b["life_stages"], ["청소년", "청년", "임신·출산"])  # 가운뎃점 공백 정규화
        self.assertEqual(b["themes"], ["교육", "생활지원"])
        self.assertEqual(b["targets"], [])
        self.assertIsNone(b["detail_url"])
        self.assertIsNone(b["views"])  # 숫자가 아니면 None
        self.assertIsNone(b["city"])  # 빈 태그는 None
        self.assertIsNone(b["apply_type"])

    def test_empty_list(self):
        xml = "<wantedList><totalCount>0</totalCount><resultCode>0</resultCode></wantedList>"
        r = parser.parse_list(xml)
        self.assertEqual(r["items"], [])
        self.assertEqual(r["total_count"], 0)


class ParserDetailTests(unittest.TestCase):
    def test_detail_fields(self):
        d = parser.parse_detail(fx("detail_sample.xml"))
        self.assertEqual(d["id"], "WLF00001")
        self.assertEqual(d["target_detail"], "만 19~34세 무주택 청년")
        self.assertEqual(d["benefit"], "월 최대 20만원, 최대 12개월")
        self.assertEqual(d["start_date"], "2025-01-01")
        self.assertEqual(d["overview"], "무주택 청년 월세 지원 사업")
        self.assertEqual(d["end_date"], "2026-12-31")
        self.assertEqual(d["apply_type"], "방문")
        self.assertEqual(d["apply_method"], "주민센터 방문 신청")
        self.assertEqual(d["life_stages"], ["청년"])
        self.assertEqual(d["province"], "서울특별시")
        self.assertEqual(d["views"], 77)

    def test_nested_lists_structured(self):
        d = parser.parse_detail(fx("detail_sample.xml"))
        self.assertEqual(d["contacts"], [{"name": "주택정책과", "content": "031-790-5511"}])
        self.assertEqual(d["laws"], [{"name": "청년기본조례", "content": None}])
        self.assertEqual(len(d["forms"]), 2)  # 같은 태그 반복 → 리스트
        self.assertTrue(d["forms"][0]["content"].startswith("https://"))
        # 구분코드(010/030/040)가 결과에 섞여 나오면 안 된다
        self.assertNotIn("010", str(d["contacts"]))

    def test_missing_nested_is_empty_list(self):
        xml = "<wantedDtl><servId>X</servId><servNm>t</servNm></wantedDtl>"
        d = parser.parse_detail(xml)
        self.assertEqual((d["contacts"], d["laws"], d["forms"]), ([], [], []))

    def test_single_nested_item_is_still_list(self):
        d = parser.parse_detail(fx("detail_sample.xml"))
        self.assertIsInstance(d["laws"], list)

    def test_detail_not_found(self):
        with self.assertRaises(WelfareAPIError) as cm:
            parser.parse_detail(fx("detail_empty.xml"))
        self.assertEqual(cm.exception.http_status, 404)

    def test_wrapper_tag_fallback(self):
        xml = (
            "<response><body><item><servId>X1</servId><servNm>테스트</servNm>"
            "</item></body></response>"
        )
        self.assertEqual(parser.parse_detail(xml)["id"], "X1")


class NoDataTests(unittest.TestCase):
    """실측: 결과가 0건이면 API 가 resultCode=40 'NO DATA FOUND' 를 돌려준다."""

    def test_list_no_data_is_empty_not_error(self):
        r = parser.parse_list(fx("no_data.xml"), page=2, size=10)
        self.assertEqual(r, {"total_count": 0, "page": 2, "size": 10, "items": []})

    def test_detail_no_data_is_404(self):
        with self.assertRaises(WelfareAPIError) as cm:
            parser.parse_detail(fx("no_data.xml"))
        self.assertEqual((cm.exception.code, cm.exception.http_status), ("NOT_FOUND", 404))

    def test_normalize_name(self):
        self.assertEqual(parser.normalize_name("임신 · 출산"), "임신·출산")
        self.assertEqual(parser.normalize_name(" 보호·돌봄 "), "보호·돌봄")


class ParserErrorTests(unittest.TestCase):
    def test_unregistered_key(self):
        with self.assertRaises(WelfareAPIError) as cm:
            parser.parse_list(fx("gateway_error.xml"))
        self.assertEqual(cm.exception.code, "SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
        self.assertEqual(cm.exception.http_status, 503)

    def test_quota_exceeded(self):
        with self.assertRaises(WelfareAPIError) as cm:
            parser.parse_list(fx("quota_error.xml"))
        self.assertEqual(cm.exception.http_status, 429)

    def test_body_result_code_error(self):
        with self.assertRaises(WelfareAPIError) as cm:
            parser.parse_list(fx("body_error.xml"))
        self.assertEqual(cm.exception.code, "UPSTREAM_RESULT_ERROR")  # 40 이 아닌 오류는 그대로 오류

    def test_non_xml_body(self):
        for bad in ("", "   ", "<html><body>oops", '{"a":1}'):
            with self.assertRaises(WelfareAPIError):
                parser.parse_list(bad)


class ValidationMessageTests(unittest.TestCase):
    def test_names_only_no_values_echoed(self):
        errs = [{"loc": ("query", "size"), "msg": "x", "input": "SECRET-VALUE"},
                {"loc": ("query", "page"), "msg": "y", "input": 0},
                {"loc": ("query", "size"), "msg": "dup"}]
        msg = validation_message(errs)
        self.assertEqual(msg, "잘못된 요청 파라미터입니다: size, page")
        self.assertNotIn("SECRET-VALUE", msg)

    def test_empty_or_unknown_location(self):
        self.assertEqual(validation_message([]), "잘못된 요청입니다.")
        self.assertEqual(validation_message([{"loc": ("body",)}]), "잘못된 요청입니다.")
        self.assertEqual(validation_message(None), "잘못된 요청입니다.")


class FakeHttp:
    """http_get 대용. responses 를 순서대로 소진한다."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, params, timeout):
        self.calls.append((url, dict(params), timeout))
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


def make_client(http, **kw):
    return WelfareClient("KEY", http_get=http, sleep=lambda s: None, **kw)


class ClientTests(unittest.TestCase):
    def test_missing_key(self):
        with self.assertRaises(WelfareAPIError) as cm:
            WelfareClient("")
        self.assertEqual(cm.exception.code, "SERVICE_KEY_MISSING")

    def test_encoding_key_is_unquoted_once(self):
        http = FakeHttp((200, "<x/>"))
        c = WelfareClient("abc%2Bdef%3D%3D", http_get=http)
        c.fetch_list()
        self.assertEqual(http.calls[0][1]["serviceKey"], "abc+def==")

    def test_none_params_omitted_and_required_sent(self):
        http = FakeHttp((200, "<x/>"))
        make_client(http).fetch_list(page=2, size=5, keyword=None, life="004")
        params = http.calls[0][1]
        self.assertNotIn("searchWrd", params)
        self.assertNotIn("intrsThemaArray", params)
        self.assertEqual(params["lifeArray"], "004")
        self.assertEqual(params["srchKeyCode"], "003")
        self.assertEqual(params["pageNo"], 2)
        self.assertTrue(http.calls[0][0].endswith("/LcgvWelfarelist"))

    def test_region_params_sent_only_when_given(self):
        http = FakeHttp((200, "<x/>"))
        c = make_client(http)
        c.fetch_list(province="서울특별시", city="강남구")
        c.fetch_list()
        self.assertEqual(http.calls[0][1]["ctpvNm"], "서울특별시")
        self.assertEqual(http.calls[0][1]["sggNm"], "강남구")
        self.assertNotIn("ctpvNm", http.calls[1][1])

    def test_detail_params(self):
        http = FakeHttp((200, "<x/>"))
        make_client(http).fetch_detail(" WLF1 ")
        self.assertEqual(http.calls[0][1]["servId"], "WLF1")
        self.assertTrue(http.calls[0][0].endswith("/LcgvWelfaredetailed"))

    def test_empty_id_rejected(self):
        with self.assertRaises(WelfareAPIError) as cm:
            make_client(FakeHttp((200, "<x/>"))).fetch_detail("  ")
        self.assertEqual(cm.exception.http_status, 400)

    def test_retry_on_5xx_then_success(self):
        http = FakeHttp((500, ""), (200, "<ok/>"))
        self.assertEqual(make_client(http, retries=2).fetch_list(), "<ok/>")
        self.assertEqual(len(http.calls), 2)

    def test_gives_up_after_retries(self):
        http = FakeHttp((503, ""))
        with self.assertRaises(WelfareAPIError) as cm:
            make_client(http, retries=2).fetch_list()
        self.assertEqual(len(http.calls), 3)
        self.assertEqual(cm.exception.code, "UPSTREAM_5XX")

    def test_timeout_maps_to_504(self):
        http = FakeHttp(TimeoutError("timed out"))
        with self.assertRaises(WelfareAPIError) as cm:
            make_client(http, retries=1).fetch_list()
        self.assertEqual(cm.exception.http_status, 504)

    def test_error_message_never_contains_key(self):
        http = FakeHttp(OSError("failed http://x?serviceKey=KEY"))
        with self.assertRaises(WelfareAPIError) as cm:
            make_client(http, retries=0).fetch_list()
        self.assertNotIn("KEY", cm.exception.message)

    def test_4xx_body_is_passed_to_parser(self):
        http = FakeHttp((401, fx("gateway_error.xml")))
        body = make_client(http).fetch_list()
        with self.assertRaises(WelfareAPIError):
            parser.parse_list(body)
        self.assertEqual(len(http.calls), 1)  # 4xx 는 재시도하지 않음


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = [0.0]
        self.http = FakeHttp((200, fx("list_sample.xml")))
        self.svc = WelfareService(
            make_client(self.http),
            default_life="003,004",
            list_ttl=100,
            detail_ttl=100,
            clock=lambda: self.now[0],
        )

    def test_default_life_is_comma_union(self):
        self.svc.search()
        self.assertEqual(self.http.calls[0][1]["lifeArray"], "003,004")

    def test_pipe_never_sent(self):
        self.svc.search(theme="040")
        self.svc.search(life="003")
        for _, params, _ in self.http.calls:
            self.assertNotIn("|", str(params.get("lifeArray", "")))

    def test_all_ages_skips_default(self):
        self.svc.search(youth_only=False)
        self.assertNotIn("lifeArray", self.http.calls[0][1])

    def test_explicit_life_wins(self):
        self.svc.search(life="007")
        self.assertEqual(self.http.calls[0][1]["lifeArray"], "007")

    def test_region_filter_passed_and_cached_separately(self):
        self.svc.search(province="서울특별시")
        self.svc.search(province="부산광역시")
        self.assertEqual(len(self.http.calls), 2)
        self.assertEqual(self.http.calls[0][1]["ctpvNm"], "서울특별시")

    def test_empty_search_returns_empty_list_and_is_cached(self):
        http = FakeHttp((200, fx("no_data.xml")))
        svc = WelfareService(make_client(http), clock=lambda: 0.0)
        r = svc.search(keyword="없는말", page=3, size=7)
        self.assertEqual((r["items"], r["total_count"], r["page"], r["size"]), ([], 0, 3, 7))
        svc.search(keyword="없는말", page=3, size=7)
        self.assertEqual(len(http.calls), 1)

    def test_cache_hit_and_expiry(self):
        self.svc.search(keyword="월세")
        self.svc.search(keyword="월세")
        self.assertEqual(len(self.http.calls), 1)  # 캐시 적중
        self.svc.search(keyword="교육")
        self.assertEqual(len(self.http.calls), 2)  # 다른 키
        self.now[0] = 101
        self.svc.search(keyword="월세")
        self.assertEqual(len(self.http.calls), 3)  # TTL 만료

    def test_detail_cached(self):
        http = FakeHttp((200, fx("detail_sample.xml")))
        svc = WelfareService(make_client(http), clock=lambda: 0.0)
        svc.detail("WLF00001")
        svc.detail("WLF00001")
        self.assertEqual(len(http.calls), 1)

    def test_errors_are_not_cached(self):
        http = FakeHttp((200, fx("quota_error.xml")), (200, fx("list_sample.xml")))
        svc = WelfareService(make_client(http), clock=lambda: 0.0)
        with self.assertRaises(WelfareAPIError):
            svc.search()
        self.assertEqual(len(svc.search()["items"]), 2)

    def test_stale_cache_served_when_upstream_times_out(self):
        now = [0.0]
        http = FakeHttp((200, fx("list_sample.xml")), TimeoutError("t"))
        svc = WelfareService(make_client(http, retries=0), list_ttl=10, clock=lambda: now[0])
        fresh = svc.search(keyword="월세")
        now[0] = 999  # TTL 만료
        stale = svc.search(keyword="월세")  # 공공 API 타임아웃 → 만료된 값으로 응답
        self.assertEqual(stale, fresh)
        self.assertEqual(len(http.calls), 2)

    def test_no_stale_fallback_for_other_keys_or_errors(self):
        http = FakeHttp(TimeoutError("t"))
        svc = WelfareService(make_client(http, retries=0), clock=lambda: 0.0)
        with self.assertRaises(WelfareAPIError) as cm:  # 캐시된 값이 없으면 그대로 오류
            svc.search(keyword="처음")
        self.assertEqual(cm.exception.code, "UPSTREAM_TIMEOUT")

    def test_stale_not_used_for_client_errors(self):
        now = [0.0]
        http = FakeHttp((200, fx("list_sample.xml")), (200, fx("body_error.xml")))
        svc = WelfareService(make_client(http), list_ttl=10, clock=lambda: now[0])
        svc.search(keyword="x")
        now[0] = 999
        with self.assertRaises(WelfareAPIError):  # 잘못된 요청 오류는 옛 데이터로 덮지 않는다
            svc.search(keyword="x")

    def test_stale_detail_on_quota_exceeded(self):
        now = [0.0]
        http = FakeHttp((200, fx("detail_sample.xml")), (200, fx("quota_error.xml")))
        svc = WelfareService(make_client(http), detail_ttl=10, clock=lambda: now[0])
        first = svc.detail("WLF00001")
        now[0] = 999
        self.assertEqual(svc.detail("WLF00001"), first)

    def test_collect_all_uses_default_union_in_one_pass_and_dedupes(self):
        http = FakeHttp((200, fx("list_sample.xml")))
        svc = WelfareService(make_client(http), default_life="003,004", clock=lambda: 0.0)
        items = list(svc.collect_all(page_size=10))
        self.assertEqual([i["id"] for i in items], ["WLF00001", "WLF00002"])
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(http.calls[0][1]["lifeArray"], "003,004")

    def test_collect_all_paginates(self):
        page = fx("list_sample.xml").replace("<totalCount>2</totalCount>", "<totalCount>25</totalCount>")
        http = FakeHttp((200, page))
        svc = WelfareService(make_client(http), clock=lambda: 0.0)
        list(svc.collect_all(page_size=10, max_pages=10))
        self.assertEqual(len(http.calls), 3)  # 25건 / 10 = 3페이지

    def test_collect_all_respects_max_pages(self):
        page = fx("list_sample.xml").replace("<totalCount>2</totalCount>", "<totalCount>9999</totalCount>")
        http = FakeHttp((200, page))
        svc = WelfareService(make_client(http), clock=lambda: 0.0)
        list(svc.collect_all(page_size=10, max_pages=3))
        self.assertEqual(len(http.calls), 3)

    def test_collect_all_stops_on_empty(self):
        http = FakeHttp((200, fx("no_data.xml")))
        svc = WelfareService(make_client(http), clock=lambda: 0.0)
        self.assertEqual(list(svc.collect_all()), [])
        self.assertEqual(len(http.calls), 1)


if __name__ == "__main__":
    unittest.main()
