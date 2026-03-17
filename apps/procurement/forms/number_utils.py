from __future__ import annotations


def normalize_localized_decimal_input(raw_value: str | None) -> str:
    if raw_value is None:
        return ""

    raw = str(raw_value).strip().replace(" ", "")
    if not raw:
        return ""

    has_comma = "," in raw
    has_dot = "." in raw

    if has_comma and has_dot:
        if raw.rfind(",") > raw.rfind("."):
            normalized = raw.replace(".", "").replace(",", ".")
        else:
            normalized = raw.replace(",", "")
        return normalized

    if has_dot:
        if _is_thousand_grouped(raw, "."):
            return raw.replace(".", "")
        return raw

    if has_comma:
        if _is_thousand_grouped(raw, ","):
            return raw.replace(",", "")
        return raw.replace(",", ".")

    return raw


def _is_thousand_grouped(value: str, separator: str) -> bool:
    parts = value.split(separator)
    if len(parts) <= 1:
        return False
    if not all(part.isdigit() for part in parts):
        return False
    if not (1 <= len(parts[0]) <= 3):
        return False
    return all(len(group) == 3 for group in parts[1:])
