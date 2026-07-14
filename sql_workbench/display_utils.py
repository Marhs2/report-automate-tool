"""셀 표시 · JSON 가독성 유틸."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

# 그리드에 그대로 넣으면 Treeview가 줄바꿈 때문에 세로로 깨져 보임
_WS_RE = re.compile(r"[\r\n\t]+")
LONG_TEXT_COLS = {
    "raw_text",
    "parsed_json",
    "completed_tasks",
    "in_progress_tasks",
    "issues",
    "requests",
    "next_plans",
    "important_summary",
}


def format_cell(value: Any, col_name: str = "", max_len: int = 80) -> str:
    """Treeview용 한 줄 미리보기."""
    if value is None:
        return "∅"
    text = str(value)
    text = _WS_RE.sub(" ", text).strip()
    if col_name.lower().endswith("json") or col_name.lower() == "parsed_json":
        pretty = try_pretty_json(value, compact=True)
        if pretty:
            text = _WS_RE.sub(" ", pretty).strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def try_pretty_json(value: Any, compact: bool = False, indent: int = 2) -> Optional[str]:
    """JSON/이중 인코딩 JSON을 읽기 좋게 변환. 실패 시 None."""
    if value is None:
        return None
    obj: Any = value
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8")
        except Exception:
            return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            obj = json.loads(s)
        except Exception:
            return None
        # 이중 인코딩: "\"{\\n ...}\"" 형태
        if isinstance(obj, str):
            try:
                obj = json.loads(obj)
            except Exception:
                pass
    if not isinstance(obj, (dict, list)):
        return None
    if compact:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def format_detail(value: Any, col_name: str = "") -> str:
    """상세 패널/전체 보기용 텍스트."""
    if value is None:
        return "(NULL)"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    pretty = try_pretty_json(value)
    if pretty is not None:
        return pretty
    return str(value)


def suggest_col_width(col_name: str, sample_values: list[Any] | None = None) -> int:
    """컬럼 기본 폭 추정."""
    name = col_name.lower()
    if name in {"id"} or name.endswith("_id"):
        return 70
    if "date" in name or name.endswith("_at"):
        return 140
    if name in LONG_TEXT_COLS or name.endswith("json") or "text" in name:
        return 220
    if name in {"name", "title"}:
        return 160

    max_w = max(len(col_name) * 10 + 24, 90)
    if sample_values:
        for v in sample_values[:20]:
            s = format_cell(v, col_name, max_len=60)
            max_w = max(max_w, min(320, len(s) * 8 + 20))
    return min(max_w, 320)


def is_long_text_column(col_name: str, col_type: str = "") -> bool:
    name = col_name.lower()
    t = (col_type or "").upper()
    if name in LONG_TEXT_COLS:
        return True
    if "json" in name or name.endswith("_text") or "summary" in name:
        return True
    if t in {"TEXT", "BLOB", "CLOB"} and name not in {"name"}:
        return name not in {"name", "type", "status"}
    return False
