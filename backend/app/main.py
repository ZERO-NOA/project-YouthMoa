"""FastAPI application entry point (starter placeholder)."""

from fastapi import FastAPI

app = FastAPI(
    title="Youth Benefits API",
    description="대학생·청년 지원 혜택 통합 조회 서비스",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
