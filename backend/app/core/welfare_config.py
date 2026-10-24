"""환경설정.

서비스키 등 민감 정보는 코드에 넣지 않고 환경변수(.env)로만 읽는다.
.env 는 레포 루트(project-YouthMoa/.env)에 두고, 커밋하지 않는다(.gitignore 확인).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]  # app/core/welfare_config.py → backend/
_REPO_ROOT = _BACKEND.parent  # .../project-YouthMoa
ENV_FILES = (_BACKEND / ".env", _REPO_ROOT / ".env")  # 앞쪽이 우선


def _read_env_file(path: Path) -> dict:
    """.env 를 직접 파싱한다 (python-dotenv 불필요, BOM·CRLF·따옴표 처리)."""
    for enc in ("utf-8-sig", "cp949"):  # 메모장/CMD 로 만든 파일 모두 대응
        try:
            text = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return {}
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        key, _, val = line.partition("=")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key.strip()] = val
    return out


def load_env() -> list:
    """.env 를 읽어 환경변수에 채운다(이미 설정된 값은 덮어쓰지 않음).
    반환: 실제로 읽은 파일 경로 목록."""
    loaded = []
    for path in ENV_FILES:
        if path.is_file():
            loaded.append(str(path))
            for k, v in _read_env_file(path).items():
                os.environ.setdefault(k, v)
    return loaded


def env_report() -> str:
    """진단용: 키 값은 숨기고 파일 존재 여부, 변수 이름, 길이만 보여준다."""
    lines = []
    for path in ENV_FILES:
        if path.is_file():
            vals = _read_env_file(path)
            desc = ", ".join(f"{k}({len(v)}자)" for k, v in vals.items()) or "(읽은 변수 없음)"
            lines.append(f"  [있음] {path} → {desc}")
        else:
            lines.append(f"  [없음] {path}")
    return "\n".join(lines)


LOADED_ENV_FILES = load_env()


def _split_codes(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.replace("|", ",").split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    service_key: str
    base_url: str
    timeout_sec: float
    retries: int
    list_cache_ttl: int  # 초
    detail_cache_ttl: int  # 초
    default_life_code: str  # 기본 생애주기 코드. 쉼표로 여러 개(실측: "003,004" = 합집합)
    search_code: str  # srchKeyCode 기본값
    cors_origins: tuple[str, ...]
    source: str  # auto | live | snapshot
    snapshot_path: str
    detail_dir: str
    detail_disk_ttl: int  # 초


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_key=os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip(),
        base_url=os.getenv(
            "WELFARE_API_BASE_URL",
            "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations",
        ).rstrip("/"),
        timeout_sec=float(os.getenv("WELFARE_API_TIMEOUT", "15")),
        retries=int(os.getenv("WELFARE_API_RETRIES", "1")),
        list_cache_ttl=int(os.getenv("WELFARE_LIST_CACHE_TTL", "600")),
        detail_cache_ttl=int(os.getenv("WELFARE_DETAIL_CACHE_TTL", "3600")),
        default_life_code=",".join(_split_codes(os.getenv("DEFAULT_LIFE_CODE", "003,004"))),
        search_code=os.getenv("WELFARE_SEARCH_CODE", "003"),
        source=os.getenv("WELFARE_SOURCE", "auto").strip().lower(),
        snapshot_path=os.getenv("WELFARE_SNAPSHOT_PATH", str(_BACKEND / "data" / "welfare_snapshot.json")),
        detail_dir=os.getenv("WELFARE_DETAIL_DIR", str(_BACKEND / "data" / "details")),
        detail_disk_ttl=int(os.getenv("WELFARE_DETAIL_DISK_TTL", str(7 * 86400))),
        cors_origins=_split_codes(
            os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        ),
    )
