from __future__ import annotations

import re
import unicodedata
from typing import Optional


_SPACE_RE = re.compile(r"\s+")

_ADMIN_PREFIX_RE = re.compile(
    r"\b("
    r"tinh|thanh\s+pho|tp|quan|huyen|thi\s+xa|tx|thi\s+tran|tt|"
    r"phuong|p|xa|x|dac\s+khu"
    r")\b"
)

_GROUP_RE = re.compile(
    r"\b("
    r"tổ(?:\s+dân\s+phố|\s+dân\s+cư)?|to(?:\s+dan\s+pho|\s+dan\s+cu)?|"
    r"nhóm|nhom"
    r")\s*(?:số|so)?\s*[:#.-]?\s*([0-9A-Za-zÀ-ỹ/-]+)",
    re.IGNORECASE,
)

_HAMLET_RE = re.compile(
    r"\b("
    r"ấp|ap|thôn|thon|khu\s+phố|khu\s+pho|khóm|khom|"
    r"bản|ban|buôn|buon|làng|lang"
    r")\s+([^,;\n]+)",
    re.IGNORECASE,
)

_LEGACY_DISTRICT_RE = re.compile(
    r"\b("
    r"quận|quan|huyện|huyen|thị\s+xã|thi\s+xa|tx\.?|"
    r"thành\s+phố|thanh\s+pho|tp\.?"
    r")\s+([^,;\n]+)",
    re.IGNORECASE,
)

_EXPLICIT_WARD_RE = re.compile(
    r"\b("
    r"phường|phuong|p\.?|xã|xa|x\.?|thị\s+trấn|thi\s+tran|tt\.?|"
    r"đặc\s+khu|dac\s+khu"
    r")\s+([^,;\n]+)",
    re.IGNORECASE,
)

_PROVINCE_RE = re.compile(
    r"\b("
    r"tỉnh|tinh|thành\s+phố|thanh\s+pho|tp\.?"
    r")\s+([^,;\n]+)",
    re.IGNORECASE,
)

_STREET_KEYWORD_RE = re.compile(
    r"\b("
    r"đường|duong|quốc\s+lộ|quoc\s+lo|ql\.?|tỉnh\s+lộ|tinh\s+lo|tl\.?|"
    r"hẻm|hem|ngõ|ngo|ngách|ngach|kiệt|kiet"
    r")\b",
    re.IGNORECASE,
)

_HOUSE_NUMBER_START_RE = re.compile(
    r"^\s*(?:số\s+nhà|so\s+nha|số|so|no\.?|#)?\s*\d+[0-9A-Za-zÀ-ỹ/.-]*\b",
    re.IGNORECASE,
)


def strip_accents(value: object) -> str:
    """Return a Vietnamese string without tone marks, mapping đ to d."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def collapse_spaces(value: str) -> str:
    return _SPACE_RE.sub(" ", value).strip()


def normalize_text(value: object) -> str:
    """Normalize text for matching while preserving enough token boundaries."""
    text = strip_accents(value).lower()
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[/|]+", " ", text)
    text = re.sub(r"[(){}\[\]\"'`]", " ", text)
    text = re.sub(r"[,:;]+", " ", text)
    text = re.sub(r"\btp\.", "tp ", text)
    text = re.sub(r"\bq\.", "quan ", text)
    text = re.sub(r"\bh\.", "huyen ", text)
    text = re.sub(r"\bp\.", "phuong ", text)
    text = re.sub(r"\bx\.", "xa ", text)
    text = re.sub(r"\bt\.", "tinh ", text)
    text = re.sub(r"[^0-9a-zA-Z\s.-]", " ", text)
    return collapse_spaces(text)


def normalize_admin_name(value: object) -> str:
    """Normalize an administrative label and remove common admin prefixes."""
    text = normalize_text(value)
    text = _ADMIN_PREFIX_RE.sub(" ", text)
    text = re.sub(r"\b(truc\s+thuoc\s+trung\s+uong|municipality|city|ward|commune)\b", " ", text)
    return collapse_spaces(text)


def compact_key(value: object) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "", normalize_text(value))


def clean_extracted(value: Optional[str]) -> str:
    if not value:
        return ""
    return collapse_spaces(str(value).strip(" ,;:-"))


def extract_group_or_to(address: object) -> str:
    match = _GROUP_RE.search(str(address or ""))
    if not match:
        return ""
    prefix = clean_extracted(match.group(1))
    number = clean_extracted(match.group(2))
    return clean_extracted(f"{prefix} {number}")


def extract_hamlet_or_area(address: object) -> str:
    match = _HAMLET_RE.search(str(address or ""))
    if not match:
        return ""
    prefix = clean_extracted(match.group(1))
    name = clean_extracted(match.group(2))
    return clean_extracted(f"{prefix} {name}")


def extract_house_number_or_street(address: object) -> str:
    """Extract the house number / street portion before local admin details."""
    text = str(address or "").strip()
    if not text:
        return ""

    first_segment = re.split(r"[,;\n]", text, maxsplit=1)[0].strip()
    if not first_segment:
        return ""

    stop_positions = []
    for pattern in (_GROUP_RE, _HAMLET_RE, _EXPLICIT_WARD_RE, _LEGACY_DISTRICT_RE, _PROVINCE_RE):
        match = pattern.search(first_segment)
        if match:
            stop_positions.append(match.start())

    if stop_positions:
        stop = min(stop_positions)
        before_local_admin = clean_extracted(first_segment[:stop])
        if before_local_admin and _looks_like_house_or_street(before_local_admin):
            return before_local_admin
        return ""

    if _looks_like_house_or_street(first_segment):
        return clean_extracted(first_segment)
    return ""


def extract_legacy_district(address: object) -> str:
    """Extract a likely old district-level label from free text if present."""
    text = str(address or "")
    for match in _LEGACY_DISTRICT_RE.finditer(text):
        label = clean_extracted(f"{match.group(1)} {match.group(2)}")
        normalized = normalize_text(label)
        if normalized.startswith(("thanh pho ho chi minh", "tp ho chi minh")):
            continue
        return label
    return ""


def extract_explicit_ward(address: object) -> str:
    """Return a ward/commune phrase only when the text has a ward-level prefix."""
    match = _EXPLICIT_WARD_RE.search(str(address or ""))
    if not match:
        return ""
    return clean_extracted(f"{match.group(1)} {match.group(2)}")


def join_non_empty(*parts: object) -> str:
    return ", ".join(str(part).strip() for part in parts if str(part or "").strip())


def _looks_like_house_or_street(value: object) -> bool:
    text = clean_extracted(str(value or ""))
    return bool(_HOUSE_NUMBER_START_RE.search(text) or _STREET_KEYWORD_RE.search(text))
