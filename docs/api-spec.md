# API 명세서

## 1. 외부 API 정보

- API명: 지자체 복지서비스 OpenAPI
- 제공처: 공공데이터포털 (한국사회보장정보원)
- 공식 문서: https://www.data.go.kr/data/15108347/openapi.do
- 데이터 형식: XML (실제 호출로 확인)
- 인증 방식: 쿼리 파라미터 `serviceKey` (공공데이터포털 일반 인증키)
- 호출: 목록 `LcgvWelfarelist`, 상세 `LcgvWelfaredetailed`
- 실측 결과(필드명·코드·한계)는 [external-api-notes.md](external-api-notes.md) 에 정리했습니다.

## 2. 내부 API 공통 규칙

- 기본 응답 형식: JSON
- HTTP 상태 코드를 사용하여 요청 성공 및 오류를 구분합니다.
- 외부 API 인증키는 백엔드에서만 사용합니다.
- 검색 조건이 없는 경우 전체 조회 또는 기본 목록을 반환하도록 설계합니다.
  - 기본 목록은 **청소년·청년 대상 서비스**입니다. 전체 연령은 `all_ages=true` (공공 API 직접 호출, 느림).
- 오류 응답은 항상 같은 형식입니다. (5. 오류 처리 참고)
- 공공 API 응답이 느려(평균 9초, 최대 57초 관측) **목록은 로컬 스냅샷에서 즉시 응답**합니다. (7. 데이터 갱신 참고)

## 3. 혜택 API

### 혜택 목록 조회

- Method: `GET`
- Endpoint: `/api/benefits`

검색 파라미터:

| Parameter | 타입 | 기본 | 설명 |
|---|---|---|---|
| `keyword` | string | - | 제목·요약 검색어. 공백으로 여러 단어를 쓰면 모두 포함된 항목 |
| `category` | string | - | 혜택 카테고리: 주거 / 일자리 / 교육 / 금융 / 생활지원 / 건강 / 문화 (`theme`이 있으면 무시). *문화는 현재 결과 0건* |
| `page` | int | 1 | 페이지 번호 (1부터) |
| `size` | int | 10 | 페이지당 결과 수 (1~100) |
| `life_stage` | string | `003,004` | 생애주기 코드. 쉼표로 여러 개(합집합). 생략하면 청소년+청년 |
| `theme` | string | - | 관심주제 코드. 쉼표로 여러 개(합집합, 예: `040,050`) |
| `province` | string | - | 시·도 이름 (예: `서울특별시`) |
| `city` | string | - | 시·군·구 이름 (예: `강남구`) |
| `target` | string | - | 대상 특성 코드 (스냅샷 미지원 → 공공 API 직접 호출) |
| `all_ages` | bool | false | true면 생애주기 기본 필터 해제 (공공 API 직접 호출) |

응답 `200`
```json
{
  "total_count": 1762,
  "page": 1,
  "size": 10,
  "source": "snapshot",
  "as_of": "2026-10-25T02:17:00+00:00",
  "items": [
    {
      "id": "WLF00001",
      "title": "청년 월세 지원",
      "summary": "무주택 청년에게 월세를 지원합니다.",
      "province": "서울특별시",
      "city": "강남구",
      "department": "주택정책과",
      "life_stages": ["청년"],
      "themes": ["주거"],
      "targets": [],
      "support_cycle": "월",
      "provision_type": "현금지급",
      "apply_type": "방문",
      "detail_url": "https://www.bokjiro.go.kr/...",
      "views": 1234,
      "updated_at": "2026-07-14"
    }
  ]
}
```
- 값이 없으면 문자열 필드는 `null`, 배열 필드는 `[]`. 결과가 없으면 오류가 아니라 `200` + `"items": []`.
- `source`: `snapshot`(로컬 저장본, 수 ms) / `live`(공공 API 직접 호출, 수 초~1분). `as_of`: 스냅샷 수집 시각(UTC) — 화면에 "OO 기준"으로 보여주기 좋습니다.
- **로딩 표시를 두세요.** 스냅샷 밖의 요청(`all_ages`, `target`, 다른 생애주기)은 느릴 수 있습니다.

### 혜택 상세 조회

- Method: `GET`
- Endpoint: `/api/benefits/{id}`  (`id`는 목록 응답의 `id`)

상세 정보와 응답 필드:

| 상세 정보 | 필드 |
|---|---|
| 서비스명 | `title` |
| 서비스 설명 | `overview` |
| 지원 대상 | `target_detail` |
| 선정 기준 | `criteria` |
| 지원 내용 | `benefit` |
| 신청 방법 | `apply_type`(방문/온라인 등), `apply_method`(상세 안내) |
| 관련 기관 | `province`, `city`, `department`, `contacts`(부서·전화) |
| 근거 법령 / 서식 | `laws`, `forms` |
| 공식 안내 링크 | `detail_url` (스냅샷에 있는 항목만) |

```json
{
  "id": "WLF00001",
  "title": "청년 월세 지원",
  "overview": "무주택 청년 월세 지원 사업",
  "province": "서울특별시",
  "city": "강남구",
  "department": "주택정책과",
  "life_stages": ["청년"],
  "themes": ["주거"],
  "targets": [],
  "support_cycle": "월",
  "provision_type": "현금지급",
  "target_detail": "만 19~34세 무주택 청년",
  "criteria": "중위소득 150% 이하",
  "benefit": "월 최대 20만원, 최대 12개월",
  "apply_type": "방문",
  "apply_method": "주민센터 방문 신청",
  "contacts": [{ "name": "주택정책과", "content": "031-790-5511" }],
  "laws": [{ "name": "청년기본조례", "content": null }],
  "forms": [{ "name": "신청서.hwp", "content": "https://www.bokjiro.go.kr/...download..." }],
  "start_date": "2025-01-01",
  "end_date": "2026-12-31",
  "detail_url": "https://www.bokjiro.go.kr/...",
  "views": 77,
  "updated_at": "2026-07-14"
}
```
- `contacts`: `name`=담당 부서, `content`=전화번호 / `laws`: `name`=근거 조례 / `forms`: `name`=서식 이름, `content`=다운로드 URL.
- 신청 마감일은 별도 필드가 없습니다. `end_date`(시행 종료일)는 마감일과 다를 수 있습니다.
- 상세는 처음 열 때만 공공 API를 호출하고(수 초~1분), 이후는 서버 저장본에서 즉시 응답합니다.

### 코드표 조회

- Method: `GET`
- Endpoint: `/api/benefits/codes`

생애주기·관심주제 코드와 카테고리 매핑을 반환합니다. `verified_*`는 실제 호출로 확인된 코드, `empty_theme`(`020`, `060`, `140`)은 현재 결과가 0건인 코드입니다. 프론트는 결과가 없는 카테고리 탭을 숨기거나 키워드 검색으로 대체하세요.

## 4. 회원 API

### 회원가입

- Method: `POST`
- Endpoint: `/api/auth/signup`

예상 입력:
- 이메일 또는 로그인 ID
- 비밀번호

### 로그인

- Method: `POST`
- Endpoint: `/api/auth/login`

인증 성공·실패 응답과 세션 또는 토큰 처리 방식은 팀에서 합의합니다.

## 5. 오류 처리

- `400`: 잘못된 요청
- `401`: 인증 필요 또는 인증 실패
- `404`: 대상 리소스 없음
- `422`: 입력값 검증 실패
- `429`: 외부 API 일일 호출 한도 초과 (추가)
- `500`: 서버 내부 오류
- `502` 또는 `503`: 외부 API 오류 또는 서비스 이용 불가

혜택 API의 오류 응답은 다음 형식으로 통일합니다.
```json
{ "error": { "code": "NOT_FOUND", "message": "해당 복지서비스를 찾을 수 없습니다." } }
```

| HTTP | `code` 예 | 발생 상황 | 프론트 처리 제안 |
|---|---|---|---|
| 404 | `NOT_FOUND` | 없는 `id` | "찾을 수 없어요" 안내 |
| 422 | `INVALID_REQUEST` | `size=1000`, `page=0` 등 범위 밖 값. 메시지에는 문제된 파라미터 **이름**만 포함 | 입력값 확인 |
| 429 | `LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR` | 공공 API 일일 한도 초과 | 잠시 후 다시 시도 |
| 502 / 504 | `UPSTREAM_TIMEOUT` 등 | 공공 API 장애·지연. 같은 요청의 이전 결과가 있으면 만료됐더라도 그 값을 대신 응답 | 재시도 버튼 |
| 503 | `SERVICE_KEY_MISSING`, `SNAPSHOT_UNAVAILABLE` | 서버 설정 문제(키 미설정, 스냅샷 전용 모드에서 처리 불가 요청) | 관리자 확인 |

## 6. 변경 관리

API 경로, 필드명, 응답 구조를 변경할 경우 팀원들과 공유하고 이 문서를 함께 갱신합니다.

## 7. 데이터 갱신 (스냅샷)

목록 데이터는 청소년·청년 대상 약 1,760건을 `backend/data/welfare_snapshot.json` 에 저장해 두고 검색·필터·페이지를 로컬에서 처리합니다.

```
python scripts/collect_snapshot.py     # 약 18회 호출, 수 분. 중단돼도 다시 실행하면 이어받음
```
- 서버는 파일이 바뀌면 **재시작 없이** 다시 읽습니다. 갱신은 주 1회 정도를 권장합니다.
- 파일 형식: `{"meta": {"collected_at", "life_codes", "count", "reported_total", "version"}, "items": [<목록 응답의 items 와 같은 구조>]}`
- DB 담당: 이 `items` 를 그대로 DB에 적재할 수 있습니다(같은 필드). 상세는 건당 1회 호출이라 전부 미리 받지 않고 **처음 열 때 받아 저장**하는 방식을 권장합니다.
- 설정: `WELFARE_SOURCE` = `auto`(기본: 가능하면 스냅샷) / `live`(항상 공공 API) / `snapshot`(스냅샷만, 데모용).
