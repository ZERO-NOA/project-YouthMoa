"""공공 API XML 응답 → 내부 표준 dict 변환.

프론트/DB 팀은 공공 API 의 필드명(servNm 등)을 몰라도 되도록,
여기서 내부 표준 필드명으로 한 번 변환해서 내보낸다.

공공 API 가 필드명을 바꾸거나 다른 API 를 추가하더라도 이 파일만 고치면 된다.

⚠️ 필드명은 Swagger/실사용 사례 기준이다. 실제 응답과 다르면
   scripts/smoke_test.py 로 원본 XML 을 저장해 _LIST_KEYS/_DETAIL_KEYS 를 맞춘다.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Optional

from app.core.errors import WelfareAPIError, from_gateway_code

# ---------------------------------------------------------------- 필드 매핑
# 내부 필드명 -> 공공 API 후보 태그(앞에서부터 우선 적용)
# ✅ 2026-10 실제 응답(smoke_test)으로 확인된 태그명 기준.
_LIST_KEYS = {
    "id": ("servId",),
    "title": ("servNm",),
    "summary": ("servDgst",),
    "province": ("ctpvNm",),  # 시·도
    "city": ("sggNm",),  # 시·군·구
    "department": ("bizChrDeptNm",),  # 담당 부서
    "life_stages": ("lifeNmArray",),
    "themes": ("intrsThemaNmArray",),
    "targets": ("trgterIndvdlNmArray",),  # 응답에 없을 수 있음(선택)
    "support_cycle": ("sprtCycNm",),
    "provision_type": ("srvPvsnNm",),
    "apply_type": ("aplyMtdNm",),  # 신청 방법명(예: 방문/온라인)
    "detail_url": ("servDtlLink",),
    "views": ("inqNum",),
    "updated_at": ("lastModYmd",),
}

_DETAIL_KEYS = {
    "id": ("servId",),
    "title": ("servNm",),
    "overview": ("servDgst",),
    "province": ("ctpvNm",),
    "city": ("sggNm",),
    "department": ("bizChrDeptNm",),
    "life_stages": ("lifeNmArray",),
    "themes": ("intrsThemaNmArray",),
    "targets": ("trgterIndvdlNmArray",),
    "support_cycle": ("sprtCycNm",),
    "provision_type": ("srvPvsnNm",),
    "target_detail": ("sprtTrgtCn",),
    "criteria": ("slctCritCn",),
    "benefit": ("alwServCn",),
    "apply_type": ("aplyMtdNm",),
    "apply_method": ("aplyMtdCn",),
    "start_date": ("enfcBgngYmd",),
    "end_date": ("enfcEndYmd",),
    "views": ("inqNum",),
    "updated_at": ("lastModYmd",),
}

_MULTI_FIELDS = {"life_stages", "themes", "targets"}
_DATE_FIELDS = {"updated_at", "start_date", "end_date"}
_SUCCESS_CODES = {"0", "00", "000"}


# ---------------------------------------------------------------- XML 유틸
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]  # 네임스페이스 제거


def _to_obj(el: ET.Element) -> Any:
    """엘리먼트를 dict/str 로 변환. 같은 태그가 반복되면 list 로 모은다."""
    children = list(el)
    if not children:
        return (el.text or "").strip()
    out: dict[str, Any] = {}
    for ch in children:
        key, val = _local(ch.tag), _to_obj(ch)
        if key in out:
            if not isinstance(out[key], list):
                out[key] = [out[key]]
            out[key].append(val)
        else:
            out[key] = val
    return out


def _parse_xml(text: str) -> ET.Element:
    if not text or not text.strip():
        raise WelfareAPIError("EMPTY_RESPONSE", "외부 API 응답이 비어 있습니다.", 502)
    try:
        return ET.fromstring(text.strip())
    except ET.ParseError:
        # JSON/HTML 오류 페이지 등은 본문 일부만 힌트로 남긴다(키가 들어갈 일 없음).
        raise WelfareAPIError(
            "INVALID_XML", "외부 API 응답을 XML로 해석할 수 없습니다.", 502
        ) from None


def _find_first(root: ET.Element, name: str) -> Optional[ET.Element]:
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _find_text(root: ET.Element, name: str) -> str:
    el = _find_first(root, name)
    return (el.text or "").strip() if el is not None else ""


def check_envelope(root: ET.Element) -> None:
    """게이트웨이 오류(<OpenAPI_ServiceResponse>)와 본문 오류(resultCode)를 검사."""
    reason = _find_text(root, "returnReasonCode")
    auth_msg = _find_text(root, "returnAuthMsg")
    if _local(root.tag) == "OpenAPI_ServiceResponse" or reason or auth_msg:
        raise from_gateway_code(reason or "99", auth_msg or _find_text(root, "errMsg"))

    code = _find_text(root, "resultCode")
    msg = _find_text(root, "resultMessage") or _find_text(root, "resultMsg")
    # 실측: 결과가 0건이면 이 API 는 빈 목록이 아니라 resultCode=40 ("NO DATA FOUND") 을 돌려준다.
    if code == "40" or "NO DATA" in msg.upper():
        raise WelfareAPIError("NO_DATA", "조회 결과가 없습니다.", 404)
    if code and code not in _SUCCESS_CODES:
        raise WelfareAPIError(
            "UPSTREAM_RESULT_ERROR", f"외부 API 오류 {code}: {msg}".strip(), 502
        )


# ---------------------------------------------------------------- 값 정규화
def normalize_name(name: str) -> str:
    """'임신 · 출산' → '임신·출산' (응답마다 가운뎃점 앞뒤 공백이 달라 통일)."""
    return re.sub(r"\s*·\s*", "·", name.strip())


def _split_multi(value: str) -> list[str]:
    return [normalize_name(p) for p in re.split(r"[,|]", value) if p.strip()]


def _iso_date(value: str) -> Optional[str]:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return None


def _first(d: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _normalize(raw: dict, mapping: dict[str, tuple[str, ...]]) -> dict:
    out: dict[str, Any] = {}
    for field, keys in mapping.items():
        val = _first(raw, keys)
        if field in _MULTI_FIELDS:
            out[field] = _split_multi(val)
        elif field in _DATE_FIELDS:
            out[field] = _iso_date(val)
        elif field == "views":
            out[field] = int(val) if val.isdigit() else None
        else:
            out[field] = val or None
    return out


def _as_list(v: Any) -> list:
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


def _flatten_texts(item: Any) -> str:
    """중첩 항목에서 비어 있지 않은 텍스트를 ' - '로 이어 붙인다."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        parts = [_flatten_texts(v) for v in item.values()]
        return " - ".join(p for p in parts if p)
    return ""


def _nested_lines(raw: dict, *list_keys: str) -> list[str]:
    for key in list_keys:
        if key in raw:
            lines = [_flatten_texts(i) for i in _as_list(raw[key])]
            return [ln for ln in lines if ln]
    return []


def _related_list(raw: dict, key: str) -> list[dict]:
    """문의처·법령·서식 목록을 [{name, content}] 로 변환한다.

    실측 구조: {wlfareInfoDtlCd: 구분코드, wlfareInfoReldNm: 이름, wlfareInfoReldCn: 내용(전화/URL)}
    구분코드(010 문의처, 030 법령, 040 서식)는 목록 종류로 이미 구분되므로 버린다.
    """
    out = []
    for item in _as_list(raw.get(key)):
        if not isinstance(item, dict):
            text = _flatten_texts(item).strip()
            if text:
                out.append({"name": text, "content": None})
            continue
        name = (item.get("wlfareInfoReldNm") or "").strip() or None
        content = (item.get("wlfareInfoReldCn") or "").strip() or None
        if name or content:
            out.append({"name": name, "content": content})
    return out


# ---------------------------------------------------------------- 공개 함수
def parse_list(xml_text: str, page: int = 1, size: int = 0) -> dict:
    """목록 응답 → {total_count, page, size, items[]}. 결과 0건이면 빈 목록을 돌려준다."""
    root = _parse_xml(xml_text)
    try:
        check_envelope(root)
    except WelfareAPIError as e:
        if e.code == "NO_DATA":
            return {"total_count": 0, "page": page, "size": size, "items": []}
        raise

    items = []
    for el in root.iter():
        if _local(el.tag) == "servList":
            raw = _to_obj(el)
            if isinstance(raw, dict):
                items.append(_normalize(raw, _LIST_KEYS))

    def _int(name: str, default: int = 0) -> int:
        t = _find_text(root, name)
        return int(t) if t.isdigit() else default

    return {
        "total_count": _int("totalCount", len(items)),
        "page": _int("pageNo", 1),
        "size": _int("numOfRows", len(items)),
        "items": items,
    }


def parse_detail(xml_text: str) -> dict:
    """상세 응답 → 내부 표준 dict. 항목이 없으면 NOT_FOUND."""
    root = _parse_xml(xml_text)
    try:
        check_envelope(root)
    except WelfareAPIError as e:
        if e.code == "NO_DATA":
            raise WelfareAPIError("NOT_FOUND", "해당 복지서비스를 찾을 수 없습니다.", 404) from None
        raise

    node = _find_first(root, "wantedDtl")
    if node is None:
        # 래퍼 태그가 다르면 servId 를 자식으로 가진 엘리먼트를 상세 노드로 본다.
        for parent in root.iter():
            if any(_local(c.tag) == "servId" for c in parent):
                node = parent
                break
    raw = _to_obj(node) if node is not None else {}
    if not isinstance(raw, dict) or not _first(raw, ("servId", "servNm")):
        raise WelfareAPIError("NOT_FOUND", "해당 복지서비스를 찾을 수 없습니다.", 404)

    detail = _normalize(raw, _DETAIL_KEYS)
    detail["contacts"] = _related_list(raw, "inqplCtadrList")  # 문의처(부서명·전화)
    detail["laws"] = _related_list(raw, "baslawList")  # 근거 법령/조례
    detail["forms"] = _related_list(raw, "basfrmList")  # 서식(이름·다운로드 URL)
    return detail
