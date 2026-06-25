from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .normalization import normalize_admin_name, normalize_text


DEFAULT_LEGACY_MAPPING_URL = (
    "https://raw.githubusercontent.com/vietmap-company/"
    "vietnam_administrative_address/main/admin_mapping/"
    "admin_mapping_old_to_new_10_25.xlsx"
)
DEFAULT_LEGACY_MAPPING_PATH = Path("data/admin_mapping_old_to_new_10_25.xlsx")
DEFAULT_LEGACY_OVERRIDES_PATH = Path("data/legacy_mapping_overrides.csv")


@dataclass(frozen=True)
class LegacyMappingRecord:
    old_city: str
    old_district: str
    old_ward: str
    new_city: str
    new_ward: str
    old_city_key: str
    old_district_key: str
    old_ward_key: str
    old_city_full_key: str
    old_district_full_key: str
    old_ward_full_key: str


@dataclass(frozen=True)
class LegacyMappingResult:
    records: tuple[LegacyMappingRecord, ...]
    score: float
    method: str
    ambiguous: bool = False

    @property
    def found(self) -> bool:
        return bool(self.records)

    @property
    def unique_new_pair(self) -> tuple[str, str] | None:
        pairs = {(record.new_city, record.new_ward) for record in self.records}
        if len(pairs) != 1:
            return None
        return next(iter(pairs))

    @property
    def legacy_district(self) -> str:
        districts = [record.old_district for record in self.records if record.old_district]
        return districts[0] if districts else ""

    @property
    def alternatives(self) -> tuple[str, ...]:
        pairs = []
        for record in self.records:
            label = f"{record.new_city}, {record.new_ward}"
            if label not in pairs:
                pairs.append(label)
        return tuple(pairs[:5])


class LegacyAdminMapping:
    def __init__(self, records: list[LegacyMappingRecord]) -> None:
        self.records = records
        self.records_by_old_ward: dict[str, list[LegacyMappingRecord]] = {}
        for record in records:
            self.records_by_old_ward.setdefault(record.old_ward_key, []).append(record)

    @classmethod
    def load(
        cls,
        path: Path | str = DEFAULT_LEGACY_MAPPING_PATH,
        url: str = DEFAULT_LEGACY_MAPPING_URL,
        overrides_path: Path | str | None = DEFAULT_LEGACY_OVERRIDES_PATH,
        refresh: bool = False,
    ) -> "LegacyAdminMapping":
        data_path = Path(path)
        if refresh or not data_path.exists():
            data_path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(url, headers={"User-Agent": "ShopeeLocationNormalizer/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                data_path.write_bytes(response.read())
        dataframe = pd.read_excel(data_path, sheet_name="admin_mapping")
        if overrides_path:
            override_file = Path(overrides_path)
            if override_file.exists():
                overrides = pd.read_csv(override_file, encoding="utf-8-sig")
                dataframe = pd.concat([dataframe, overrides], ignore_index=True)
        return cls.from_dataframe(dataframe)

    @classmethod
    def from_dataframe(cls, dataframe: pd.DataFrame) -> "LegacyAdminMapping":
        records: list[LegacyMappingRecord] = []
        required_columns = [
            "city_name_old",
            "district_name_old",
            "ward_name_old",
            "city_name_new",
            "ward_new_name",
        ]
        missing = sorted(set(required_columns).difference(dataframe.columns))
        if missing:
            raise ValueError(f"Legacy mapping is missing columns: {', '.join(missing)}")

        for row in dataframe[required_columns].dropna(how="any").itertuples(index=False):
            values = dict(zip(required_columns, row))
            old_city = str(values["city_name_old"]).strip()
            old_district = str(values["district_name_old"]).strip()
            old_ward = str(values["ward_name_old"]).strip()
            new_city = str(values["city_name_new"]).strip()
            new_ward = str(values["ward_new_name"]).strip()
            records.append(
                LegacyMappingRecord(
                    old_city=old_city,
                    old_district=old_district,
                    old_ward=old_ward,
                    new_city=new_city,
                    new_ward=new_ward,
                    old_city_key=_admin_key(old_city),
                    old_district_key=_admin_key(old_district),
                    old_ward_key=_admin_key(old_ward),
                    old_city_full_key=_full_key(old_city),
                    old_district_full_key=_full_key(old_district),
                    old_ward_full_key=_full_key(old_ward),
                )
            )
        return cls(records)

    def match(self, text: object, min_score: float = 0.70) -> LegacyMappingResult:
        query = _admin_key(text)
        full_query = _full_key(text)
        if not query:
            return LegacyMappingResult((), 0.0, "empty")

        candidates: list[tuple[float, LegacyMappingRecord]] = []
        for old_ward_key in _candidate_old_ward_keys(query, self.records_by_old_ward.keys()):
            records_for_ward = self.records_by_old_ward[old_ward_key]
            for record in records_for_ward:
                score = _score_record(
                    query,
                    full_query,
                    record,
                    allow_cityless=_is_unique_old_ward_district(record, records_for_ward),
                )
                if score >= min_score:
                    candidates.append((score, record))

        if not candidates:
            return LegacyMappingResult((), 0.0, "no_match")

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score = candidates[0][0]
        close = [record for score, record in candidates if best_score - score <= 0.10]
        unique_records = _unique_records(close)
        return LegacyMappingResult(
            records=tuple(unique_records),
            score=round(best_score, 4),
            method="legacy_mapping",
            ambiguous=len({(record.new_city, record.new_ward) for record in unique_records}) > 1,
        )


def _candidate_old_ward_keys(query: str, old_ward_keys: Iterable[str]) -> list[str]:
    matches: list[str] = []
    for key in old_ward_keys:
        if not key:
            continue
        if len(key) <= 2:
            if _contains_phrase(query, key):
                matches.append(key)
        elif _contains_phrase(query, key):
            matches.append(key)
    return matches


def _score_record(
    query: str,
    full_query: str,
    record: LegacyMappingRecord,
    allow_cityless: bool = False,
) -> float:
    strict_ward_match = _contains_phrase(full_query, record.old_ward_full_key)
    district_match = _contains_phrase(full_query, record.old_district_full_key) or (
        not record.old_district_key.isdigit()
        and record.old_district_key != record.old_ward_key
        and _contains_phrase(query, record.old_district_key)
    )
    city_match = any(_contains_phrase(query, alias) for alias in _city_aliases(record.old_city_key))
    enough_context = city_match or (
        allow_cityless
        and district_match
        and record.old_ward_key != record.old_district_key
    )
    loose_ward_match = (
        not record.old_ward_key.isdigit()
        and len(record.old_ward_key) >= 4
        and district_match
        and enough_context
        and _contains_phrase(query, record.old_ward_key)
    )
    ward_match = strict_ward_match or loose_ward_match

    if not ward_match:
        return 0.0

    score = 0.42
    if district_match:
        score += 0.35
    if city_match:
        score += 0.23

    # Numeric wards such as "Phường 1" or "Phường 22" are too risky without explicit ward context.
    if record.old_ward_key.isdigit() and not strict_ward_match:
        return 0.0
    if len(record.old_ward_key) <= 2 and (not strict_ward_match or not district_match):
        score -= 0.35

    return max(0.0, min(1.0, score))


def _is_unique_old_ward_district(record: LegacyMappingRecord, records: Iterable[LegacyMappingRecord]) -> bool:
    matches = {
        (candidate.old_city_key, candidate.old_district_key)
        for candidate in records
        if candidate.old_district_key == record.old_district_key
    }
    return len(matches) == 1


def _unique_records(records: Iterable[LegacyMappingRecord]) -> list[LegacyMappingRecord]:
    seen: set[tuple[str, str, str, str, str]] = set()
    unique: list[LegacyMappingRecord] = []
    for record in records:
        key = (record.old_city, record.old_district, record.old_ward, record.new_city, record.new_ward)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _admin_key(value: object) -> str:
    return normalize_admin_name(value)


def _full_key(value: object) -> str:
    return normalize_text(value)


def _contains_phrase(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return f" {needle} " in f" {haystack} "


def _city_aliases(city_key: str) -> tuple[str, ...]:
    aliases = {city_key}
    if city_key == "ho chi minh":
        aliases.update({"hcm", "tp hcm", "tphcm", "sai gon", "saigon"})
    elif city_key == "ha noi":
        aliases.update({"hn"})
    elif city_key == "da nang":
        aliases.update({"dn"})
    elif city_key == "can tho":
        aliases.update({"ct"})
    return tuple(aliases)
