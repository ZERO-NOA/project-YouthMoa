"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import benefits
from app.core.errors import WelfareAPIError, validation_message
from app.core.welfare_config import get_settings

settings = get_settings()

app = FastAPI(
    title="Youth Benefits API",
    description="대학생·청년 지원 혜택 통합 조회 서비스",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST"],  # 회원 API(POST) 추가를 고려
    allow_headers=["*"],
)


@app.exception_handler(WelfareAPIError)
async def welfare_error_handler(_: Request, exc: WelfareAPIError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    """입력값 검증 실패는 팀 명세대로 422 로 응답하되, 다른 오류와 같은 {"error": ...} 형식을 쓴다."""
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_REQUEST", "message": validation_message(exc.errors())}},
    )


@app.get("/health")
def health_check():
    # 키 값은 노출하지 않고 설정 여부만 알려준다.
    return {"status": "ok", "service_key_configured": bool(settings.service_key)}


app.include_router(benefits.router)
