from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from shopee_location import (
    AddressResolver,
    AdminCatalog,
    LegacyAdminMapping,
    build_order_suggestion_label,
    build_scan_display_lines,
    find_order_matches,
    find_order_suffix_matches,
    normalize_order_code,
)
from shopee_location.geocoding import GoogleGeocoder


load_dotenv()

MAX_ROWS = 5000
OUTPUT_COLUMNS = [
    "province_code_new",
    "province_new",
    "ward_code_new",
    "ward_new",
    "shopee_location_value",
    "legacy_district_guess",
    "house_number_or_street",
    "hamlet_or_area",
    "group_or_to",
    "latitude",
    "longitude",
    "confidence",
    "status",
    "reason",
]


APP_NAME = "Standardizing Vietnamese Addresses"


st.set_page_config(page_title=APP_NAME, page_icon=":material/location_on:", layout="wide")


@st.cache_resource(show_spinner=False)
def load_catalog(data_path: str) -> AdminCatalog:
    return AdminCatalog.load(path=Path(data_path))


@st.cache_resource(show_spinner=False)
def load_legacy_mapping(data_path: str, overrides_path: str) -> LegacyAdminMapping:
    return LegacyAdminMapping.load(path=Path(data_path), overrides_path=Path(overrides_path))


def read_input_file(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(uploaded_file, encoding="utf-8-sig")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding="cp1258")
    return pd.read_excel(uploaded_file)


def best_column(columns: list[str], keywords: list[str]) -> str | None:
    normalized = {column: column.lower().replace("_", " ") for column in columns}
    for keyword in keywords:
        keyword = keyword.lower()
        for column, value in normalized.items():
            if keyword in value:
                return column
    return None


def select_column(
    label: str,
    columns: list[str],
    default: str | None,
    optional: bool = True,
    key: str | None = None,
) -> str | None:
    options = [""] + columns if optional else columns
    if not options:
        return None
    index = 0
    if default in options:
        index = options.index(default)
    choice = st.selectbox(label, options, index=index, key=key)
    return choice or None


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="normalized")
    return output.getvalue()


def build_resolver(api_key: str) -> AddressResolver:
    data_path = os.getenv("ADMIN_UNITS_JSON", "data/admin_units.json")
    cache_path = os.getenv("GEOCODE_CACHE_PATH", "data/geocode_cache.sqlite")
    legacy_mapping_path = os.getenv("LEGACY_MAPPING_XLSX", "data/admin_mapping_old_to_new_10_25.xlsx")
    legacy_overrides_path = os.getenv("LEGACY_MAPPING_OVERRIDES_CSV", "data/legacy_mapping_overrides.csv")
    catalog = load_catalog(data_path)
    try:
        legacy_mapping = load_legacy_mapping(legacy_mapping_path, legacy_overrides_path)
    except Exception as exc:
        st.warning(f"Không tải được mapping cũ-mới local: {exc}")
        legacy_mapping = None
    geocoder = GoogleGeocoder(api_key=api_key, cache_path=cache_path)
    return AddressResolver(catalog=catalog, geocoder=geocoder, legacy_mapping=legacy_mapping)


st.title(APP_NAME)

with st.sidebar:
    st.header("Cấu hình")
    env_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    api_key = st.text_input("Google Geocoding API key", value=env_key, type="password")
    st.caption("Key chỉ dùng trong phiên chạy app này. Không có key thì app không gọi Google.")
    refresh_data = st.button("Tải lại danh mục hành chính")
    if refresh_data:
        data_path = Path(os.getenv("ADMIN_UNITS_JSON", "data/admin_units.json"))
        if data_path.exists():
            data_path.unlink()
        load_catalog.clear()
        st.success("Đã xóa cache danh mục. App sẽ tải lại khi xử lý.")

def render_normalize_mode(api_key: str) -> None:
    uploaded_file = st.file_uploader("Upload file CSV hoặc Excel", type=["csv", "xlsx", "xls"], key="normalize_upload")

    if not uploaded_file:
        st.info("Upload file đơn hàng để bắt đầu. Cần ít nhất một cột chứa địa chỉ cụ thể.")
        return

    try:
        source_df = read_input_file(uploaded_file)
    except Exception as exc:
        st.error(f"Không đọc được file: {exc}")
        return

    if source_df.empty:
        st.warning("File không có dòng dữ liệu.")
        return

    if len(source_df) > MAX_ROWS:
        st.error(f"Bản đầu tiên hỗ trợ tối đa {MAX_ROWS:,} dòng mỗi lần. File hiện có {len(source_df):,} dòng.")
        return

    columns = list(source_df.columns)
    address_default = best_column(columns, ["dia chi cu the", "địa chỉ cụ thể", "address", "specific"])
    location_default = best_column(columns, ["tinh/thanh", "tỉnh/thành", "quan/huyen", "quận/huyện", "location"])
    province_default = best_column(columns, ["province", "tỉnh", "thành phố", "tinh"])
    district_default = best_column(columns, ["district", "quận", "huyện", "ward", "xã", "phường"])

    st.subheader("Mapping cột")
    left, mid, right, last = st.columns(4)
    with left:
        address_column = select_column("Địa chỉ cụ thể", columns, address_default, optional=False, key="normalize_address")
    with mid:
        selected_location_column = select_column(
            "Tỉnh/Thành, Quận/Huyện/Xã khách chọn",
            columns,
            location_default,
            key="normalize_selected_location",
        )
    with right:
        selected_province_column = select_column("Tỉnh/Thành riêng", columns, province_default, key="normalize_province")
    with last:
        selected_district_column = select_column("Quận/Huyện/Xã riêng", columns, district_default, key="normalize_district")

    st.subheader("Dữ liệu đầu vào")
    st.dataframe(source_df.head(20), use_container_width=True)

    process = st.button("Xử lý địa chỉ", type="primary", disabled=not address_column)

    if process:
        resolver = build_resolver(api_key)
        progress = st.progress(0, text="Đang xử lý địa chỉ...")
        records = source_df.to_dict("records")
        output_rows = []
        for index, row in enumerate(records, start=1):
            output_rows.append(
                resolver.resolve(
                    address_text=row.get(address_column, ""),
                    selected_location=row.get(selected_location_column, "") if selected_location_column else "",
                    selected_province=row.get(selected_province_column, "") if selected_province_column else "",
                    selected_district_or_ward=row.get(selected_district_column, "") if selected_district_column else "",
                )
            )
            progress.progress(index / len(records), text=f"Đã xử lý {index}/{len(records)} dòng")
        progress.empty()
        result_df = pd.concat([source_df.reset_index(drop=True), pd.DataFrame(output_rows)], axis=1)
        st.session_state.normalized_df = result_df

    if st.session_state.normalized_df is not None:
        render_normalized_result(st.session_state.normalized_df)


def render_normalized_result(result_df: pd.DataFrame) -> None:
    st.subheader("Kết quả")
    status_options = ["all"] + sorted(result_df["status"].dropna().unique().tolist())
    status_filter = st.segmented_control("Lọc trạng thái", status_options, default="all")
    filtered_df = result_df if status_filter == "all" else result_df[result_df["status"] == status_filter]

    edited_df = st.data_editor(
        filtered_df,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "confidence": st.column_config.NumberColumn("confidence", min_value=0.0, max_value=1.0, step=0.01),
            "status": st.column_config.SelectboxColumn("status", options=["auto_ok", "needs_review", "failed"]),
        },
        disabled=[column for column in filtered_df.columns if column not in OUTPUT_COLUMNS],
    )

    if status_filter == "all":
        st.session_state.normalized_df = edited_df
        export_df = edited_df
    else:
        export_df = result_df.copy()
        export_df.loc[edited_df.index, edited_df.columns] = edited_df
        st.session_state.normalized_df = export_df

    counts = export_df["status"].value_counts(dropna=False).to_dict()
    st.write(
        f"auto_ok: {counts.get('auto_ok', 0)} | "
        f"needs_review: {counts.get('needs_review', 0)} | "
        f"failed: {counts.get('failed', 0)}"
    )

    csv_bytes = export_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    xlsx_bytes = to_excel_bytes(export_df)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Tải CSV", csv_bytes, "shopee_locations_normalized.csv", "text/csv")
    with c2:
        st.download_button(
            "Tải Excel",
            xlsx_bytes,
            "shopee_locations_normalized.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def render_scan_mode() -> None:
    _reset_selected_suggestion_when_query_changes()
    result_file = st.file_uploader(
        "Upload file kết quả đã xử lý",
        type=["csv", "xlsx", "xls"],
        key="scan_result_upload",
    )

    if not result_file:
        if st.session_state.normalized_df is None:
            st.info("Upload file kết quả đã xử lý để quét mã đơn.")
            return
        use_current = st.checkbox("Dùng kết quả vừa xử lý trong phiên này", value=True)
        if not use_current:
            return
        result_df = st.session_state.normalized_df.copy()
    else:
        try:
            result_df = read_input_file(result_file)
        except Exception as exc:
            st.error(f"Không đọc được file kết quả: {exc}")
            return

    if result_df.empty:
        st.warning("File kết quả không có dòng dữ liệu.")
        return

    columns = list(result_df.columns)
    order_default = best_column(
        columns,
        [
            "mã đơn",
            "ma don",
            "ma_don",
            "order id",
            "order_id",
            "order",
            "tracking",
            "barcode",
            "qrcode",
            "qr",
            "stt",
        ],
    )
    if order_default is None and columns:
        order_default = columns[0]

    st.subheader("Quét mã đơn")
    left, right = st.columns([1, 2])
    with left:
        order_column = select_column("Cột mã đơn", columns, order_default, optional=False, key="scan_order_column")
    with right:
        scanned_code = st.text_input(
            "Mã đơn hàng",
            key="scan_order_code",
            placeholder="Quét barcode/QR hoặc nhập 2-6 ký tự cuối mã đơn",
        )

    _focus_scan_input()

    normalized_scan = normalize_order_code(scanned_code)
    matches = result_df.iloc[0:0]
    if normalized_scan:
        matches = find_order_matches(result_df, order_column, normalized_scan)
        if matches.empty and 2 <= len(normalized_scan) <= 6:
            suggestions = find_order_suffix_matches(result_df, order_column, normalized_scan)
            if suggestions.empty:
                st.error(f"Không có mã đơn nào kết thúc bằng: {normalized_scan}")
            else:
                _render_order_suggestions(suggestions, order_column)
                selected_index = st.session_state.get("scan_selected_index")
                if selected_index in result_df.index:
                    matches = result_df.loc[[selected_index]]
        elif matches.empty:
            st.error(f"Không tìm thấy mã đơn: {normalized_scan}")
    else:
        st.info("Quét đủ mã đơn hoặc nhập 2-6 ký tự cuối để hiện gợi ý.")

    if not matches.empty:
        if len(matches) > 1:
            st.warning(f"Có {len(matches)} dòng trùng mã đơn. Đang hiển thị dòng đầu tiên.")
        _render_scan_result(matches, order_column, normalized_scan)

    with st.expander("Xem dữ liệu kết quả", expanded=False):
        st.dataframe(result_df.head(100), use_container_width=True)
        if not matches.empty:
            st.subheader("Dòng đang chọn")
            st.dataframe(matches.head(10), use_container_width=True)


def _render_scan_result(matches: pd.DataFrame, order_column: str, normalized_scan: str) -> None:
    row = matches.iloc[0]
    line_1, line_2 = build_scan_display_lines(row)
    order_code = normalize_order_code(row.get(order_column, normalized_scan))
    st.success(f"Đã chọn mã đơn: {order_code}")
    st.code(line_1)
    st.code(line_2)


def _render_order_suggestions(suggestions: pd.DataFrame, order_column: str) -> None:
    st.markdown("**Gợi ý mã đơn**")
    for index, row in suggestions.head(20).iterrows():
        left, right = st.columns([1, 8])
        with left:
            st.button("Chọn", key=f"scan_pick_{index}", on_click=_select_suggestion, args=(index,))
        with right:
            st.write(build_order_suggestion_label(row, order_column))


def _select_suggestion(index: object) -> None:
    st.session_state.scan_selected_index = index


def _reset_selected_suggestion_when_query_changes() -> None:
    current_query = normalize_order_code(st.session_state.get("scan_order_code", ""))
    previous_query = st.session_state.get("scan_previous_query")
    if previous_query != current_query:
        st.session_state.scan_selected_index = None
        st.session_state.scan_previous_query = current_query


def _focus_scan_input() -> None:
    components.html(
        """
        <script>
        const labels = Array.from(window.parent.document.querySelectorAll('label'));
        const label = labels.find((item) => item.innerText && item.innerText.includes('Mã đơn hàng'));
        const input = label ? label.parentElement.querySelector('input') : null;
        if (input) {
          setTimeout(() => input.focus(), 150);
        }
        </script>
        """,
        height=0,
    )


if "normalized_df" not in st.session_state:
    st.session_state.normalized_df = None

normalize_tab, scan_tab = st.tabs(["Chuẩn hóa file", "Quét mã đơn"])
with normalize_tab:
    render_normalize_mode(api_key)
with scan_tab:
    render_scan_mode()
