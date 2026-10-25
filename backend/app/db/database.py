from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# SQLite 데이터베이스 파일 경로
DATABASE_URL = "sqlite:///./youth_benefits.db"


# 데이터베이스 연결
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


# SQLite 외래키 제약 조건 활성화
@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# DB 세션 생성기
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# 모든 모델의 공통 기반 클래스
class Base(DeclarativeBase):
    pass


# FastAPI에서 사용할 DB 세션 의존성
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()