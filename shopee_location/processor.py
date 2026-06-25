from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .admin_units import AdminCatalog, MatchResult, Province, Ward
from .geocoding import (
    GeocodeResult,
    GoogleGeocoder,
    district_component_text,
    province_component_text,
    ward_component_text,
)
from .legacy_mapping import LegacyAdminMapping, LegacyMappingResult
from .normalization import (
    extract_group_or_to,
    extract_hamlet_or_area,
    extract_house_number_or_street,
    extract_explicit_ward,
    extract_legacy_district,
    join_non_empty,
    normalize_admin_name,
)


@dataclass(frozen=True)
class ResolverConfig:
    auto_ok_threshold: float = 0.82
    review_threshold: float = 0.45


@dataclass
class _CandidateState:
    province: Province | None = None
    ward: Ward | None = None
    province_sources: set[str] = field(default_factory=set)
    ward_sources: set[str] = field(default_factory=set)
    selected_conflict: bool = False
    ambiguous: bool = False


class AddressResolver:
    def __init__(
        self,
        catalog: AdminCatalog,
        geocoder: GoogleGeocoder | None = None,
        legacy_mapping: LegacyAdminMapping | None = None,
        config: ResolverConfig | None = None,
    ) -> None:
        self.catalog = catalog
        self.geocoder = geocoder
        self.legacy_mapping = legacy_mapping
        self.config = config or ResolverConfig()

    def resolve(
        self,
        address_text: object,
        selected_location: object = "",
        selected_province: object = "",
        selected_district_or_ward: object = "",
    ) -> dict[str, Any]:
        address = str(address_text or "").strip()
        if not address:
            return _failed_result("empty_address", "Không có địa chỉ cụ thể.")

        hamlet = extract_hamlet_or_area(address)
        group = extract_group_or_to(address)
        house_number_or_street = extract_house_number_or_street(address)
        legacy_district = extract_legacy_district(join_non_empty(address, selected_location, selected_district_or_ward))

        state = _CandidateState()
        reasons: list[str] = []
        hint_text = join_non_empty(selected_location, selected_province, selected_district_or_ward)
        full_text = join_non_empty(address, hint_text)

        selected_province_match = self.catalog.match_province(hint_text, min_score=0.78)
        if selected_province_match.found:
            _apply_province(state, selected_province_match, "selected")

        selected_ward_match = self.catalog.match_ward(
            hint_text,
            province_code=state.province.code if state.province else None,
            min_score=0.78,
        )
        if selected_ward_match.found:
            _apply_ward(state, selected_ward_match, "selected")

        address_province_match = self.catalog.match_province(address, min_score=0.88)
        if address_province_match.found:
            _apply_province(state, address_province_match, "address_text")

        explicit_address_ward = extract_explicit_ward(address)
        if explicit_address_ward:
            address_ward_match = self.catalog.match_ward(
                explicit_address_ward,
                province_code=state.province.code if state.province else None,
                min_score=0.95,
            )
            if address_ward_match.found and _is_exact_admin_label(explicit_address_ward, address_ward_match.item):
                _apply_ward(state, address_ward_match, "address_text")
        elif state.province:
            unprefixed_text = _remove_known_local_parts(address, hamlet, group)
            address_ward_match = self.catalog.match_ward(
                unprefixed_text,
                province_code=state.province.code,
                min_score=0.90,
            )
            if address_ward_match.found:
                _apply_ward(state, address_ward_match, "address_text")

        legacy_mapping_result = self._match_legacy_mapping(full_text)
        if legacy_mapping_result.found:
            if legacy_mapping_result.legacy_district and not legacy_district:
                legacy_district = legacy_mapping_result.legacy_district
            if legacy_mapping_result.ambiguous or not legacy_mapping_result.unique_new_pair:
                state.ambiguous = True
                reasons.append(
                    "Bảng mapping cũ-mới có nhiều ứng viên: "
                    + "; ".join(legacy_mapping_result.alternatives)
                )
            else:
                new_city, new_ward = legacy_mapping_result.unique_new_pair
                mapped_province_match = self.catalog.match_province(new_city, min_score=0.78)
                if mapped_province_match.found:
                    if state.province and state.province.code != mapped_province_match.item.code and "selected" in state.province_sources:
                        state.selected_conflict = True
                        reasons.append("Mapping cũ-mới suy ra tỉnh/thành khác lựa chọn của khách.")
                    _apply_province(state, mapped_province_match, "legacy_mapping")
                mapped_ward_match = self.catalog.match_ward(
                    new_ward,
                    province_code=state.province.code if state.province else None,
                    min_score=0.78,
                )
                if mapped_ward_match.found:
                    if state.ward and state.ward.code != mapped_ward_match.item.code and "selected" in state.ward_sources:
                        state.selected_conflict = True
                        reasons.append("Mapping cũ-mới suy ra xã/phường khác lựa chọn của khách.")
                    _apply_ward(state, mapped_ward_match, "legacy_mapping")

        geocode = self._geocode(full_text)
        if geocode.raw_status == "DISABLED":
            reasons.append("Google Geocoding chưa bật vì thiếu API key.")
        elif geocode.raw_status and geocode.raw_status != "OK":
            reasons.append(f"Google Geocoding trả về {geocode.raw_status}.")

        if geocode.ok:
            google_province_match = self.catalog.match_province(province_component_text(geocode), min_score=0.78)
            if google_province_match.found:
                if state.province and state.province.code != google_province_match.item.code and "selected" in state.province_sources:
                    state.selected_conflict = True
                    reasons.append("Tỉnh/thành Google suy ra khác lựa chọn của khách.")
                _apply_province(state, google_province_match, "google")

            google_ward_match = self.catalog.match_ward(
                ward_component_text(geocode),
                province_code=state.province.code if state.province else None,
                min_score=0.78,
            )
            if google_ward_match.found:
                if state.ward and state.ward.code != google_ward_match.item.code and "selected" in state.ward_sources:
                    state.selected_conflict = True
                    reasons.append("Xã/phường Google suy ra khác lựa chọn của khách.")
                _apply_ward(state, google_ward_match, "google")

            google_district = district_component_text(geocode)
            if google_district and not legacy_district:
                legacy_district = google_district

        confidence = self._score(state, geocode, hamlet, group)
        if state.ambiguous:
            confidence = max(0.0, confidence - 0.08)
            reasons.append("Có nhiều địa danh gần giống nhau.")
        if state.selected_conflict:
            confidence = max(0.0, confidence - 0.10)

        status = self._status(state, geocode, confidence)
        if not state.province:
            reasons.append("Chưa xác định được tỉnh/thành.")
        if not state.ward:
            reasons.append("Chưa xác định được xã/phường/đặc khu.")
        if legacy_district and not state.ward:
            reasons.append("Có quận/huyện cũ nhưng chưa có bảng mapping cũ-mới local để tự chuyển chắc chắn.")
        if not geocode.ok:
            reasons.append("Chưa có tọa độ chắc chắn.")
        if status == "auto_ok":
            reasons.append("Đủ tín hiệu để tự động chấp nhận.")

        return {
            "province_code_new": state.province.code if state.province else "",
            "province_new": state.province.full_name if state.province else "",
            "ward_code_new": state.ward.code if state.ward else "",
            "ward_new": state.ward.full_name if state.ward else "",
            "shopee_location_value": _shopee_value(state.province, state.ward),
            "legacy_district_guess": legacy_district,
            "house_number_or_street": house_number_or_street,
            "hamlet_or_area": hamlet,
            "group_or_to": group,
            "latitude": geocode.latitude if geocode.ok else "",
            "longitude": geocode.longitude if geocode.ok else "",
            "confidence": round(confidence, 3),
            "status": status,
            "reason": " ".join(dict.fromkeys(reason for reason in reasons if reason)),
        }

    def resolve_many(
        self,
        rows: Iterable[Mapping[str, Any]],
        column_map: Mapping[str, str | None],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for row in rows:
            result = self.resolve(
                address_text=_row_value(row, column_map.get("address")),
                selected_location=_row_value(row, column_map.get("selected_location")),
                selected_province=_row_value(row, column_map.get("selected_province")),
                selected_district_or_ward=_row_value(row, column_map.get("selected_district_or_ward")),
            )
            results.append(result)
        return results

    def _geocode(self, full_text: str) -> GeocodeResult:
        if not self.geocoder:
            return GeocodeResult(raw_status="DISABLED", error_message="No geocoder configured")
        query = join_non_empty(full_text, "Việt Nam")
        try:
            return self.geocoder.geocode(query)
        except Exception as exc:  # The UI should keep the batch moving.
            return GeocodeResult(raw_status="ERROR", error_message=str(exc))

    def _match_legacy_mapping(self, full_text: str) -> LegacyMappingResult:
        if not self.legacy_mapping:
            return LegacyMappingResult((), 0.0, "disabled")
        try:
            return self.legacy_mapping.match(full_text)
        except Exception:
            return LegacyMappingResult((), 0.0, "error")

    def _score(self, state: _CandidateState, geocode: GeocodeResult, hamlet: str, group: str) -> float:
        score = 0.0
        if state.province:
            if "legacy_mapping" in state.province_sources:
                score += 0.34
            elif "google" in state.province_sources:
                score += 0.30
            elif "address_text" in state.province_sources:
                score += 0.22
            elif "selected" in state.province_sources:
                score += 0.12
        if state.ward:
            if "legacy_mapping" in state.ward_sources:
                score += 0.36
            elif "google" in state.ward_sources:
                score += 0.30
            elif "address_text" in state.ward_sources:
                score += 0.24
            elif "selected" in state.ward_sources:
                score += 0.12
        if geocode.ok:
            score += 0.20
            if geocode.location_type in {"ROOFTOP", "RANGE_INTERPOLATED", "GEOMETRIC_CENTER"}:
                score += 0.05
            if geocode.partial_match:
                score -= 0.10
        if hamlet:
            score += 0.03
        if group:
            score += 0.02
        return min(1.0, max(0.0, score))

    def _status(self, state: _CandidateState, geocode: GeocodeResult, confidence: float) -> str:
        if confidence < self.config.review_threshold and not state.province and not state.ward:
            return "failed"
        if state.province and state.ward and geocode.ok and confidence >= self.config.auto_ok_threshold:
            return "auto_ok"
        return "needs_review"


def _apply_province(state: _CandidateState, match: MatchResult, source: str) -> None:
    item = match.item
    if not isinstance(item, Province):
        return
    if state.province and state.province.code != item.code and source != "selected":
        state.province = item
        state.province_sources = {source}
    elif not state.province:
        state.province = item
        state.province_sources.add(source)
    elif state.province.code == item.code:
        state.province_sources.add(source)
    state.ambiguous = state.ambiguous or match.ambiguous


def _apply_ward(state: _CandidateState, match: MatchResult, source: str) -> None:
    item = match.item
    if not isinstance(item, Ward):
        return
    if state.ward and state.ward.code != item.code and source != "selected":
        state.ward = item
        state.ward_sources = {source}
    elif not state.ward:
        state.ward = item
        state.ward_sources.add(source)
    elif state.ward.code == item.code:
        state.ward_sources.add(source)
    state.ambiguous = state.ambiguous or match.ambiguous


def _row_value(row: Mapping[str, Any], column: str | None) -> Any:
    if not column:
        return ""
    value = row.get(column, "")
    return "" if value is None else value


def _shopee_value(province: Province | None, ward: Ward | None) -> str:
    if province and ward:
        return f"{province.full_name}, {ward.full_name}"
    if province:
        return province.full_name
    return ""


def _remove_known_local_parts(address: str, hamlet: str, group: str) -> str:
    cleaned = address
    for part in (hamlet, group):
        if part:
            cleaned = cleaned.replace(part, " ")
    return cleaned


def _is_exact_admin_label(query: str, item: Province | Ward | None) -> bool:
    if not item:
        return False
    query_key = normalize_admin_name(query)
    return query_key in {normalize_admin_name(item.name), normalize_admin_name(item.full_name)}


def _failed_result(status: str, reason: str) -> dict[str, Any]:
    return {
        "province_code_new": "",
        "province_new": "",
        "ward_code_new": "",
        "ward_new": "",
        "shopee_location_value": "",
        "legacy_district_guess": "",
        "house_number_or_street": "",
        "hamlet_or_area": "",
        "group_or_to": "",
        "latitude": "",
        "longitude": "",
        "confidence": 0.0,
        "status": "failed",
        "reason": reason or status,
    }
