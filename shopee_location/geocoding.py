from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import requests


GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float | None = None
    longitude: float | None = None
    formatted_address: str = ""
    place_id: str = ""
    location_type: str = ""
    partial_match: bool = False
    components: tuple[dict[str, Any], ...] = ()
    raw_status: str = ""
    error_message: str = ""
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return self.latitude is not None and self.longitude is not None and self.raw_status == "OK"


class SQLiteGeocodeCache:
    def __init__(self, path: Path | str = "data/geocode_cache.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self, cache_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM geocode_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def set(self, cache_key: str, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO geocode_cache (cache_key, payload)
                VALUES (?, ?)
                """,
                (cache_key, json.dumps(payload, ensure_ascii=False)),
            )


class GoogleGeocoder:
    def __init__(
        self,
        api_key: str | None,
        cache_path: Path | str = "data/geocode_cache.sqlite",
        session: Any | None = None,
        timeout: int = 12,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.cache = SQLiteGeocodeCache(cache_path)
        self.session = session or requests.Session()
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def geocode(self, query: str, language: str = "vi", region: str = "vn") -> GeocodeResult:
        query = " ".join(str(query or "").split())
        if not query:
            return GeocodeResult(raw_status="EMPTY_QUERY", error_message="Missing address query")
        if not self.enabled:
            return GeocodeResult(raw_status="DISABLED", error_message="Missing GOOGLE_MAPS_API_KEY")

        cache_key = json.dumps(
            {"query": query, "language": language, "region": region, "provider": "google-v3"},
            ensure_ascii=False,
            sort_keys=True,
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return _parse_google_payload(cached, from_cache=True)

        params = {
            "address": query,
            "components": "country:VN",
            "language": language,
            "region": region,
            "key": self.api_key,
        }
        response = self.session.get(GOOGLE_GEOCODE_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        status = payload.get("status", "")
        if status in {"OK", "ZERO_RESULTS"}:
            self.cache.set(cache_key, payload)
        return _parse_google_payload(payload, from_cache=False)


def _parse_google_payload(payload: dict[str, Any], from_cache: bool) -> GeocodeResult:
    status = payload.get("status", "")
    if status != "OK" or not payload.get("results"):
        return GeocodeResult(
            raw_status=status,
            error_message=payload.get("error_message", "") or status or "No geocoding result",
            from_cache=from_cache,
        )

    result = payload["results"][0]
    location = result.get("geometry", {}).get("location", {})
    return GeocodeResult(
        latitude=location.get("lat"),
        longitude=location.get("lng"),
        formatted_address=result.get("formatted_address", ""),
        place_id=result.get("place_id", ""),
        location_type=result.get("geometry", {}).get("location_type", ""),
        partial_match=bool(result.get("partial_match", False)),
        components=tuple(result.get("address_components", [])),
        raw_status=status,
        from_cache=from_cache,
    )


def component_names(result: GeocodeResult, wanted_types: set[str]) -> list[str]:
    names: list[str] = []
    for component in result.components:
        types = set(component.get("types", []))
        if types.intersection(wanted_types):
            long_name = str(component.get("long_name", "")).strip()
            short_name = str(component.get("short_name", "")).strip()
            for name in (long_name, short_name):
                if name and name not in names:
                    names.append(name)
    return names


def province_component_text(result: GeocodeResult) -> str:
    names = component_names(result, {"administrative_area_level_1"})
    return " ".join(names + [result.formatted_address])


def ward_component_text(result: GeocodeResult) -> str:
    names = component_names(
        result,
        {
            "administrative_area_level_3",
            "administrative_area_level_4",
            "sublocality",
            "sublocality_level_1",
            "sublocality_level_2",
            "neighborhood",
            "premise",
        },
    )
    return " ".join(names + [result.formatted_address])


def district_component_text(result: GeocodeResult) -> str:
    names = component_names(
        result,
        {
            "administrative_area_level_2",
            "locality",
            "sublocality",
            "sublocality_level_1",
        },
    )
    return names[0] if names else ""
