# Frontend

React와 Vite를 활용하여 대학생·청년 지원 혜택 통합 조회 웹의 사용자 인터페이스를 구현합니다.

## 1. 기술 스택

- React
- Vite
- JavaScript
- Tailwind CSS
- FastAPI

## 2. 주요 개발 기능

- 메인 페이지 및 서비스 소개
- 지원 혜택 목록 화면
- 카테고리별 조회 화면
- 검색창 및 검색 결과
- 지원 혜택 상세 페이지
- 회원가입 및 로그인 페이지
- API 응답에 따른 로딩·오류·빈 결과 표시

## 3. 폴더 구조

```text
src/
├── components/    # 공통 UI 컴포넌트
├── pages/         # 페이지 단위 컴포넌트
├── services/      # 백엔드 API 호출
├── hooks/         # 공통 React Hooks
├── App.jsx        # 라우팅 및 앱 구성
└── main.jsx       # 앱 진입점
```

## 4. 개발 환경 설정

Node.js LTS 버전을 설치한 뒤 다음 명령어를 실행합니다.

```bash
npm install
npm run dev
```

브라우저에 표시되는 로컬 개발 주소로 접속합니다.

아직 Vite 프로젝트를 생성하지 않았다면 프로젝트 루트에서 다음 명령어를 실행할 수 있습니다.

```bash
npm create vite@latest . -- --template react
npm install
```

기존 파일이 있다면 덮어쓰지 않도록 주의합니다.

## 5. 백엔드 연결

프론트엔드는 공공 API를 직접 호출하지 않고, 백엔드에서 제공하는 REST API를 호출합니다.

예시:
- `GET /api/benefits`: 혜택 목록 조회
- `GET /api/benefits/{id}`: 혜택 상세 조회
- `POST /api/auth/signup`: 회원가입
- `POST /api/auth/login`: 로그인

※ 실제 경로와 요청·응답 형식은 팀에서 합의한 API 명세를 따릅니다.

## 6. 개발 시 주의 사항

- API 호출 주소를 코드 곳곳에 직접 작성하지 않고 환경변수로 관리합니다.
- 공공 API 인증키를 프론트엔드에 노출하지 않습니다.
- API 오류와 검색 결과가 없는 상황을 구분해 표시합니다.
- 공통 UI는 `components/`에 작성하여 재사용합니다.
- GitHub에 `node_modules/`와 빌드 결과물을 올리지 않습니다.