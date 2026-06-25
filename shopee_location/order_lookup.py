from __future__ import annotations

import re
from typing import Any

import pandas as pd


def normalize_order_code(value: object) -> str:
    text = _clean_text(value)
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text.strip()


def find_order_matches(dataframe: pd.DataFrame, order_column: str, scanned_code: object) -> pd.DataFrame:
    code = normalize_order_code(scanned_code)
    if not code or order_column not in dataframe.columns:
        return dataframe.iloc[0:0]
    normalized_codes = dataframe[order_column].map(normalize_order_code)
    return dataframe.loc[normalized_codes == code]


def find_order_suffix_matches(
    dataframe: pd.DataFrame,
    order_column: str,
    suffix: object,
    min_length: int = 2,
    max_length: int = 6,
    max_results: int = 50,
) -> pd.DataFrame:
    code_suffix = normalize_order_code(suffix)
    if not (min_length <= len(code_suffix) <= max_length) or order_column not in dataframe.columns:
        return dataframe.iloc[0:0]
    normalized_codes = dataframe[order_column].map(normalize_order_code)
    mask = normalized_codes.map(lambda code: code.endswith(code_suffix))
    return dataframe.loc[mask].head(max_results)


def build_order_suggestion_label(row: pd.Series, order_column: str) -> str:
    location = value_for_display(row, "shopee_location_value")
    if not location:
        location = " | ".join(
            part
            for part in (
                value_for_display(row, "province_new"),
                value_for_display(row, "ward_new"),
            )
            if part
        )
    parts = [
        value_for_display(row, order_column),
        location,
        value_for_display(row, "hamlet_or_area"),
        value_for_display(row, "house_number_or_street"),
    ]
    return " | ".join(part for part in parts if part)


def value_for_display(row: pd.Series, column: str) -> str:
    if column not in row.index:
        return ""
    return _clean_text(row[column])


def build_scan_display_lines(row: pd.Series) -> tuple[str, str]:
    shopee_location_value = value_for_display(row, "shopee_location_value")
    province_new = value_for_display(row, "province_new")
    ward_new = value_for_display(row, "ward_new")
    hamlet_or_area = value_for_display(row, "hamlet_or_area")
    house_number_or_street = value_for_display(row, "house_number_or_street")
    return (
        " | ".join([shopee_location_value, hamlet_or_area, house_number_or_street]),
        " | ".join([province_new, ward_new, hamlet_or_area, house_number_or_street]),
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"[\r\n\t]+", "", str(value)).strip()
