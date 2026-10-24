"""한국사회보장정보원 지자체복지서비스 OpenAPI 클라이언트.

- 목록: GET {base}/LcgvWelfarelist
- 상세: GET {base}/LcgvWelfaredetailed
- 응답은 XML 문자열 그대로 반환한다. 파싱은 parsers 가 담당한다.

설계 포인트
1) 서비스키: Encoding 키/Decoding 키 어느 쪽을 .env 에 넣어도 동작하도록
   먼저 unquote 한 뒤 한 번만 인코딩한다(이중 인코딩 방지).
2) 오류 메시지·로그에 URL(=키)을 절대 남기지 않는다.
3) 테스트 가능하도록 HTTP 전송 함수(http_get)를 주입할 수 있다.
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional

from app.core.errors import WelfareAPIError

log = logging.getLogger(__name__)

LIST_PATH = "LcgvWelfarelist"
DETAIL_PATH = "LcgvWelfaredetailed"

# (url, params, timeout) -> (status_code, body_text)
HttpGet = Callable[[str, dict, float], "tuple[int, str]"]


def _read_with_deadline(resp, deadline: float) -> bytes:
    """본문을 조각으로 읽으며 전체 제한시간을 넘기면 TimeoutError.

    urllib 의 timeout 은 '소켓 1회 대기 시간'이라, 데이터가 조금씩 느리게 오면
    전체 시간이 timeout 을 훨씬 넘길 수 있다(실측: 설정 20초인데 호출이 49~57초).
    """
    chunks = []
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("response deadline exceeded")
        chunk = resp.read(8192)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _urllib_get(url: str, params: dict, timeout: float) -> "tuple[int, str]":
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    req = urllib.request.Request(
        f"{url}?{query}", headers={"User-Agent": "YouthMoa/0.1"}
    )
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _read_with_deadline(resp, deadline).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:  # 4xx/5xx 도 본문을 돌려준다
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body


class WelfareClient:
    def __init__(
        self,
        service_key: str,
        base_url: str = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations",
        timeout: float = 10.0,
        retries: int = 2,
        http_get: Optional[HttpGet] = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not service_key:
            raise WelfareAPIError(
                "SERVICE_KEY_MISSING",
                "DATA_GO_KR_SERVICE_KEY 가 설정되지 않았습니다(.env 확인).",
                503,
            )
        # Encoding 키(%2B 등 포함)를 넣어도 한 번만 인코딩되도록 정규화
        self._key = urllib.parse.unquote(service_key)
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._retries = max(0, retries)
        self._get = http_get or _urllib_get
        self._sleep = sleep
        # 마지막 호출의 시도별 (결과, 걸린 초). 느린 호출의 원인 진단용이며 스레드마다 달라질 수 있다.
        self.last_attempts: list = []

    # ------------------------------------------------------------------ public
    def fetch_list(
        self,
        *,
        page: int = 1,
        size: int = 10,
        keyword: Optional[str] = None,
        life: Optional[str] = None,
        theme: Optional[str] = None,
        target: Optional[str] = None,
        province: Optional[str] = None,
        city: Optional[str] = None,
        search_code: str = "003",
        order: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> str:
        """목록조회. 값이 없는 선택 파라미터는 아예 보내지 않는다."""
        params = {
            "callTp": "L",
            "pageNo": page,
            "numOfRows": size,
            "srchKeyCode": search_code,  # 필수 파라미터로 알려져 있음 → 항상 전송
            "searchWrd": keyword,
            "lifeArray": life,
            "intrsThemaArray": theme,
            "trgterIndvdlArray": target,
            "ctpvNm": province,  # ✅ 실측: 시·도 필터 동작
            "sggNm": city,  # ⏳ 시·군·구 필터는 smoke_test [6] 에서 확인
            "arrgOrd": order,
        }
        if extra:
            params.update(extra)
        return self._request(LIST_PATH, params)

    def fetch_detail(self, serv_id: str) -> str:
        if not serv_id or not serv_id.strip():
            raise WelfareAPIError("INVALID_ID", "servId 가 비어 있습니다.", 400)
        return self._request(DETAIL_PATH, {"callTp": "D", "servId": serv_id.strip()})

    # ----------------------------------------------------------------- private
    def _request(self, path: str, params: dict) -> str:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        clean["serviceKey"] = self._key
        url = f"{self._base}/{path}"

        last_err: Optional[WelfareAPIError] = None
        attempts: list = []
        self.last_attempts = attempts
        for attempt in range(self._retries + 1):
            t0 = time.monotonic()
            try:
                status, body = self._get(url, clean, self._timeout)
                attempts.append((str(status), time.monotonic() - t0))
            except TimeoutError:
                attempts.append(("timeout", time.monotonic() - t0))
                last_err = WelfareAPIError(
                    "UPSTREAM_TIMEOUT", "외부 API 응답 시간이 초과되었습니다.", 504
                )
            except OSError as e:  # 연결 실패 등. str(e) 에 URL 이 섞일 수 있어 타입만 기록
                attempts.append((type(e).__name__, time.monotonic() - t0))
                log.warning("welfare api network error: %s", type(e).__name__)
                last_err = WelfareAPIError(
                    "UPSTREAM_UNREACHABLE", "외부 API에 연결할 수 없습니다.", 502
                )
            else:
                if status >= 500:
                    last_err = WelfareAPIError(
                        "UPSTREAM_5XX", f"외부 API 서버 오류({status})", 502
                    )
                else:
                    # 4xx 도 게이트웨이 오류 XML 이 올 수 있어 본문을 파서로 넘긴다.
                    return body

            if attempt < self._retries:
                self._sleep(0.5 * (2**attempt))  # 0.5s, 1s ...
        assert last_err is not None
        raise last_err
