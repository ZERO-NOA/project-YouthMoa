# Backend

Python과 FastAPI를 사용하여 외부 공공 API 연동, 혜택 검색, 회원 인증 및 데이터베이스 기능을 구현합니다.

## 1. 기술 스택

- Python 3.13
- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite
- HTTPX
- Pydantic

## 2. 주요 개발 기능

- 지자체 복지서비스 OpenAPI 연동
- 외부 API 응답 파싱 및 데이터 정규화
- 혜택 목록 및 상세 조회
- 키워드 검색 및 카테고리 필터
- 회원가입 및 로그인
- 사용자 정보 저장 및 인증 처리

## 3. 폴더 구조

```text
app/
├── main.py       # FastAPI 진입점
├── api/          # REST API 라우터
├── services/     # 외부 API 연동 및 비즈니스 로직
├── models/       # 데이터베이스 모델
├── schemas/      # 요청·응답 스키마
├── db/           # DB 연결 및 세션
└── core/         # 환경 설정 및 인증
```

## 4. 개발 환경 설정

### 가상환경 생성

Windows PowerShell 기준입니다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 패키지 설치

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 환경변수 설정

프로젝트 루트의 `.env.example`을 참고하여 `backend/.env`를 생성합니다.

외부 API 인증키와 비밀키 등은 환경변수로 관리합니다.

### 서버 실행

`backend/` 디렉터리에서 실행합니다.

```powershell
uvicorn app.main:app --reload
```

기본 주소:
- 서버: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

## 5. 내부 API 초안

| Method | Endpoint | 기능 |
|---|---|---|
| GET | `/health` | 서버 상태 확인 |
| GET | `/api/benefits` | 혜택 목록 및 검색 |
| GET | `/api/benefits/{id}` | 혜택 상세 조회 |
| POST | `/api/auth/signup` | 회원가입 |
| POST | `/api/auth/login` | 로그인 |

※ 혜택 API의 검색 파라미터와 인증 방식은 실제 구현 및 API 명세 확정 후 반영합니다.

## 6. 개발 시 주의 사항

- 외부 API 오류와 타임아웃을 처리합니다.
- 외부 API의 XML 응답을 필요한 공통 데이터 구조로 변환합니다.
- 비밀번호는 평문으로 저장하지 않습니다.
- 인증키와 비밀키를 코드에 직접 작성하지 않습니다.
- 사용자 입력값을 검증하고 오류 응답 형식을 통일합니다.
- 실제 공공 API 호출 한도를 고려하여 불필요한 요청을 줄입니다.