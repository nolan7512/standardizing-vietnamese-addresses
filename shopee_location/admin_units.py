from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Optional

from .normalization import normalize_admin_name, normalize_text


DEFAULT_DATA_URL = (
    "https://raw.githubusercontent.com/thanglequoc/"
    "vietnamese-provinces-database/master/json/"
    "vn_only_simplified_json_generated_data_vn_units_minified.json"
)
DEFAULT_DATA_PATH = Path("data/admin_units.json")


@dataclass(frozen=True)
class Province:
    code: str
    name: str
    full_name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Ward:
    code: str
    name: str
    full_name: str
    province_code: str
    province_name: str
    province_full_name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class MatchResult:
    item: Province | Ward | None
    score: float
    method: str
    ambiguous: bool = False
    alternatives: tuple[str, ...] = ()

    @property
    def found(self) -> bool:
        return self.item is not None


class AdminCatalog:
    def __init__(self, provinces: list[Province], wards: list[Ward]) -> None:
        self.provinces = provinces
        self.wards = wards
        self.provinces_by_code = {province.code: province for province in provinces}
        self.wards_by_code = {ward.code: ward for ward in wards}
        self.wards_by_province: dict[str, list[Ward]] = {}
        for ward in wards:
            self.wards_by_province.setdefault(ward.province_code, []).append(ward)

    @classmethod
    def load(
        cls,
        path: Path | str = DEFAULT_DATA_PATH,
        url: str = DEFAULT_DATA_URL,
        refresh: bool = False,
    ) -> "AdminCatalog":
        data_path = Path(path)
        if refresh or not data_path.exists():
            data_path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(url, headers={"User-Agent": "ShopeeLocationNormalizer/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload_text = response.read().decode("utf-8")
            data_path.write_text(payload_text, encoding="utf-8")
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: list[dict]) -> "AdminCatalog":
        provinces: list[Province] = []
        wards: list[Ward] = []
        for province_data in payload:
            province_name = province_data.get("Name") or _strip_admin_prefix(province_data.get("FullName", ""))
            province_full_name = province_data.get("FullName") or province_name
            province = Province(
                code=str(province_data.get("Code", "")),
                name=province_name,
                full_name=province_full_name,
                aliases=_aliases(province_name, province_full_name, province_data.get("NameEn")),
            )
            provinces.append(province)
            for ward_data in province_data.get("Wards", []):
                ward_name = ward_data.get("Name") or _strip_admin_prefix(ward_data.get("FullName", ""))
                ward_full_name = ward_data.get("FullName") or ward_name
                wards.append(
                    Ward(
                        code=str(ward_data.get("Code", "")),
                        name=ward_name,
                        full_name=ward_full_name,
                        province_code=province.code,
                        province_name=province.name,
                        province_full_name=province.full_name,
                        aliases=_aliases(ward_name, ward_full_name, ward_data.get("NameEn")),
                    )
                )
        return cls(provinces, wards)

    def match_province(self, text: object, min_score: float = 0.78) -> MatchResult:
        return _best_match(text, self.provinces, min_score=min_score)

    def match_ward(
        self,
        text: object,
        province_code: str | None = None,
        min_score: float = 0.78,
    ) -> MatchResult:
        candidates = self.wards_by_province.get(province_code, []) if province_code else self.wards
        return _best_match(text, candidates, min_score=min_score)


def _strip_admin_prefix(value: object) -> str:
    text = str(value or "").strip()
    for prefix in (
        "Thành phố ",
        "Tỉnh ",
        "Phường ",
        "Xã ",
        "Đặc khu ",
        "Thị trấn ",
        "Quận ",
        "Huyện ",
    ):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _aliases(*values: object) -> tuple[str, ...]:
    aliases: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        for alias in {text, _strip_admin_prefix(text), normalize_admin_name(text), normalize_text(text)}:
            alias = alias.strip()
            if alias and alias not in aliases:
                aliases.append(alias)
    normalized = {normalize_admin_name(alias) for alias in aliases}
    if "ho chi minh" in normalized:
        aliases.extend(alias for alias in ("HCM", "TP HCM", "TP.HCM", "TPHCM", "Sài Gòn", "Sai Gon") if alias not in aliases)
    if "ha noi" in normalized:
        aliases.extend(alias for alias in ("HN",) if alias not in aliases)
    if "da nang" in normalized:
        aliases.extend(alias for alias in ("DN",) if alias not in aliases)
    return tuple(aliases)


def _best_match(text: object, candidates: Iterable[Province | Ward], min_score: float) -> MatchResult:
    query = normalize_admin_name(text)
    if not query:
        return MatchResult(None, 0.0, "empty")

    scored: list[tuple[float, str, Province | Ward]] = []
    for candidate in candidates:
        score, method = _score_candidate(query, candidate.aliases)
        if score >= min_score:
            scored.append((score, method, candidate))

    if not scored:
        return MatchResult(None, 0.0, "no_match")

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, method, best_item = scored[0]
    alternatives = tuple(_display_name(item) for score, _method, item in scored[1:4] if best_score - score <= 0.04)
    ambiguous = len(alternatives) > 0 and best_score < 0.97
    return MatchResult(best_item, round(best_score, 4), method, ambiguous, alternatives)


def _score_candidate(query: str, aliases: tuple[str, ...]) -> tuple[float, str]:
    best_score = 0.0
    best_method = "ratio"
    for alias in aliases:
        normalized_alias = normalize_admin_name(alias)
        if not normalized_alias:
            continue
        if _contains_phrase(query, normalized_alias):
            score, method = 1.0, "contains"
        elif len(query) >= 4 and _contains_phrase(normalized_alias, query):
            score, method = 0.95, "reverse_contains"
        else:
            score = SequenceMatcher(None, query, normalized_alias).ratio()
            method = "ratio"
            if len(normalized_alias) <= 3 and score < 1.0:
                score *= 0.65
        if score > best_score:
            best_score, best_method = score, method
    return best_score, best_method


def _contains_phrase(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return f" {needle} " in f" {haystack} "


def _display_name(item: Province | Ward) -> str:
    if isinstance(item, Ward):
        return f"{item.province_full_name} / {item.full_name}"
    return item.full_name
