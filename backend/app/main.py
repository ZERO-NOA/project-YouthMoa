"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import benefits
from app.core.errors import WelfareAPIError, validation_message
from app.core.welfare_config import get_settings
from app.db.database import Base, engine
from app.models import User, Benefit, Favorite, ViewHistory


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 개발 초기 단계에서 테이블 생성
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="청년 지원 혜택 통합 조회 API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(WelfareAPIError)
async def welfare_error_handler(_: Request, exc: WelfareAPIError):
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _: Request,
    exc: RequestValidationError,
):
    """입력값 검증 실패를 팀 명세에 맞는 422 응답으로 반환한다."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": validation_message(list(exc.errors())),
            }
        },
    )


@app.get("/health")
def health_check():
    # API 키 자체는 노출하지 않고 설정 여부만 반환한다.
    return {
        "status": "ok",
        "service_key_configured": bool(settings.service_key),
    }


app.include_router(benefits.router)