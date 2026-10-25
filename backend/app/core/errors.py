"""외부 API 연동 중 발생하는 오류를 한 곳에서 정의한다.

주의: 오류 메시지에 요청 URL(= 서비스키 포함)을 절대 넣지 않는다.
"""
from __future__ import annotations

# 공공데이터포털 공통 에러코드 (returnReasonCode)
GATEWAY_ERRORS = {
    "01": ("APPLICATION_ERROR", "외부 API 서버 내부 오류"),
    "02": ("DB_ERROR", "외부 API DB 오류"),
    "03": ("NODATA_ERROR", "데이터 없음"),
    "04": ("HTTP_ERROR", "외부 API HTTP 오류"),
    "05": ("SERVICETIMEOUT_ERROR", "외부 API 응답 시간 초과"),
    "10": ("INVALID_REQUEST_PARAMETER_ERROR", "요청 파라미터가 올바르지 않음"),
    "11": ("NO_MANDATORY_REQUEST_PARAMETERS_ERROR", "필수 파라미터 누락"),
    "12": ("NO_OPENAPI_SERVICE_ERROR", "해당 API 서비스 없음"),
    "20": ("SERVICE_ACCESS_DENIED_ERROR", "서비스 접근 거부(활용신청/승인 확인)"),
    "22": ("LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR", "일일 호출 한도 초과"),
    "30": ("SERVICE_KEY_IS_NOT_REGISTERED_ERROR", "등록되지 않은 서비스키"),
    "31": ("DEADLINE_HAS_EXPIRED_ERROR", "서비스키 사용 기간 만료"),
    "32": ("UNREGISTERED_IP_ERROR", "등록되지 않은 IP"),
    "99": ("UNKNOWN_ERROR", "알 수 없는 오류"),
}


class WelfareAPIError(Exception):
    """공공 API 호출/파싱 실패. router 에서 HTTP 상태코드로 변환한다."""

    def __init__(self, code: str, message: str, http_status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def from_gateway_code(reason_code: str, detail: str = "") -> WelfareAPIError:
    name, msg = GATEWAY_ERRORS.get(reason_code, ("UPSTREAM_ERROR", "외부 API 오류"))
    status = {
        "22": 429,  # 한도 초과
        "03": 404,
        "10": 400,
        "11": 400,
        "20": 503,
        "30": 503,
        "31": 503,
        "32": 503,
        "12": 503,
    }.get(reason_code, 502)
    return WelfareAPIError(name, f"{msg}{f' ({detail})' if detail else ''}", status)


def validation_message(errors: list) -> str:
    """FastAPI 검증 오류 목록 → 사용자용 문장.

    잘못 입력된 '값'은 되돌려 주지 않고, 문제가 된 파라미터 '이름'만 알려준다.
    """
    names: list = []
    for e in errors or []:
        loc = [str(x) for x in e.get("loc", ()) if x not in ("query", "path", "body")]
        name = ".".join(loc)
        if name and name not in names:
            names.append(name)
    return f"잘못된 요청 파라미터입니다: {', '.join(names)}" if names else "잘못된 요청입니다."
