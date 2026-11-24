"""Dynamic rule substitution engine for Bokbut_it shortcuts."""

from __future__ import annotations

import re
from datetime import datetime

KOREAN_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")

AVAILABLE_TAGS: list[tuple[str, str]] = [
    ("{오늘날짜}", "YYYY-MM-DD"),
    ("{오늘날짜_간략}", "YY.MM.DD"),
    ("{현재시간}", "HH:MM"),
    ("{요일}", "한글 요일"),
    ("{클립보드}", "클립보드 원문"),
    ("{클립보드_숫자만}", "숫자만 추출"),
    ("{입력:항목명}", "실행 시 입력"),
]

_TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")
_INPUT_TAG_PATTERN = re.compile(r"\{입력:([^{}]+)\}")


def extract_input_fields(template: str) -> list[str]:
    """Return unique {입력:항목명} field names in order of appearance."""
    seen: set[str] = set()
    fields: list[str] = []
    for match in _INPUT_TAG_PATTERN.finditer(template):
        name = match.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            fields.append(name)
    return fields


def render_template(
    template: str,
    clipboard_text: str = "",
    input_values: dict[str, str] | None = None,
    now: datetime | None = None,
) -> str:
    """Evaluate all dynamic rule tags in a single pass and return the rendered text."""
    current = now or datetime.now()
    inputs = input_values or {}

    def _replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token == "오늘날짜":
            return current.strftime("%Y-%m-%d")
        if token == "오늘날짜_간략":
            return current.strftime("%y.%m.%d")
        if token == "현재시간":
            return current.strftime("%H:%M")
        if token == "요일":
            return KOREAN_WEEKDAYS[current.weekday()]
        if token == "클립보드":
            return clipboard_text
        if token == "클립보드_숫자만":
            return re.sub(r"\D", "", clipboard_text)
        if token.startswith("입력:"):
            field_name = token[3:].strip()
            return inputs.get(field_name, "")
        return match.group(0)

    return _TOKEN_PATTERN.sub(_replace, template)
