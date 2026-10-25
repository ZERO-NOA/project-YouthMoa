from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.database import Base, engine
from app.models import User, Benefit, Favorite



@asynccontextmanager
async def lifespan(app: FastAPI):
    # 개발 초기 단계에서 테이블 생성
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="청년 지원 혜택 통합 조회 API",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    return {"status": "ok"}