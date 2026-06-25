"""Address normalization toolkit for Shopee Vietnam location cleanup."""

from .admin_units import AdminCatalog, MatchResult, Province, Ward
from .legacy_mapping import LegacyAdminMapping, LegacyMappingResult
from .order_lookup import (
    build_order_suggestion_label,
    build_scan_display_lines,
    find_order_matches,
    find_order_suffix_matches,
    normalize_order_code,
)
from .processor import AddressResolver, ResolverConfig

__all__ = [
    "AddressResolver",
    "AdminCatalog",
    "LegacyAdminMapping",
    "LegacyMappingResult",
    "MatchResult",
    "Province",
    "ResolverConfig",
    "Ward",
    "build_order_suggestion_label",
    "build_scan_display_lines",
    "find_order_matches",
    "find_order_suffix_matches",
    "normalize_order_code",
]
