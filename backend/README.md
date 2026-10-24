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
│   └── benefits.py          # /api/benefits (혜택 목록·상세·코드표)
├── services/     # 외부 API 연동 및 비즈니스 로직
│   ├── welfare_service.py   # 스냅샷 → 캐시 → 공공 API 조회, 장애 시 만료 캐시 대체
│   ├── welfare_codes.py     # 생애주기·관심주제 코드표, 카테고리 매핑
│   ├── clients/             # 공공 API 호출 (재시도, 전체 시간 제한, 키 보호)
│   ├── parsers/             # XML → 내부 표준 dict 변환 (필드 매핑은 여기만 수정)
│   └── store/               # 목록 스냅샷, 상세 디스크 캐시, 수집기
├── models/       # 데이터베이스 모델
├── schemas/      # 요청·응답 스키마 (welfare.py: 혜택 응답)
├── db/           # DB 연결 및 세션
└── core/         # 환경 설정 및 인증
    ├── welfare_config.py    # .env 로딩·설정 (공공 API 연동용)
    └── errors.py            # 연동 오류 정의
scripts/          # smoke_test.py(실제 API 검증), collect_snapshot.py(목록 스냅샷 수집)
tests/            # 단위 테스트 (표준 unittest)
data/             # 스냅샷·상세 캐시 저장 위치
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

공공 API 연동에 필요한 값: `DATA_GO_KR_SERVICE_KEY` (공공데이터포털 일반 인증키, Encoding/Decoding 어느 쪽이든 가능). 그 밖의 선택 설정은 `.env.example`을 참고하세요.

### 서버 실행

`backend/` 디렉터리에서 실행합니다.

```powershell
uvicorn app.main:app --reload
```

기본 주소:
- 서버: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

## 5. 내부 API

| Method | Endpoint | 기능 |
|---|---|---|
| GET | `/health` | 서버 상태 확인 |
| GET | `/api/benefits` | 혜택 목록 및 검색 (`keyword`, `category`, `page`, `size`, `life_stage`, `theme`, `province`, `city`) |
| GET | `/api/benefits/{id}` | 혜택 상세 조회 |
| GET | `/api/benefits/codes` | 생애주기·관심주제·카테고리 코드표 |
| POST | `/api/auth/signup` | 회원가입 (초안) |
| POST | `/api/auth/login` | 로그인 (초안) |

혜택 API의 파라미터와 응답은 [docs/api-spec.md](../docs/api-spec.md) 에 확정되어 있습니다. 인증 방식은 합의 후 반영합니다.

## 6. 개발 시 주의 사항

- 외부 API 오류와 타임아웃을 처리합니다.
- 외부 API의 XML 응답을 필요한 공통 데이터 구조로 변환합니다.
- 비밀번호는 평문으로 저장하지 않습니다.
- 인증키와 비밀키를 코드에 직접 작성하지 않습니다.
- 사용자 입력값을 검증하고 오류 응답 형식을 통일합니다.
- 실제 공공 API 호출 한도를 고려하여 불필요한 요청을 줄입니다.

## 7. 공공 API 연동 파트 사용법

공공 API가 느리고 가끔 멈춥니다(평균 9초, 최대 57초 관측). 그래서 **목록은 스냅샷 파일에서, 상세는 처음 한 번만 호출해 디스크에 저장**합니다.

```powershell
# backend/ 에서 (.venv 활성화 후)
python scripts/collect_snapshot.py        # ① 청소년·청년 목록 스냅샷 수집 (약 18회 호출, 수 분). 중단돼도 이어받음
python -m unittest discover -s tests -v   # ② 단위 테스트 (pytest 로도 실행 가능)
python scripts/smoke_test.py              # ③ 실제 공공 API 검증 (약 25회 호출). 구간 선택: python scripts/smoke_test.py 4 7
uvicorn app.main:app --reload             # ④ 서버 실행
```

- 조회 순서: 목록 = 스냅샷 → 메모리 캐시 → 공공 API / 상세 = 메모리 → 디스크 → 공공 API (장애 시 만료된 캐시로 대체)
- 공공 API는 결과가 0건이면 오류코드 40을 돌려주므로 코드에서 빈 목록으로 변환합니다.
- 필드 매핑이 바뀌면 `app/services/parsers/welfare_parser.py` 의 `_LIST_KEYS` / `_DETAIL_KEYS` 만 수정하면 됩니다.
- 실측 결과와 한계는 [docs/external-api-notes.md](../docs/external-api-notes.md) 를 참고하세요.
