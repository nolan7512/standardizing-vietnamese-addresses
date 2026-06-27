from __future__ import annotations

from html import escape
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


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --sva-ink: #1f2933;
            --sva-muted: #6b7280;
            --sva-line: #d7dde5;
            --sva-panel: #ffffff;
            --sva-panel-soft: #f7f9fb;
            --sva-teal: #0f766e;
            --sva-teal-dark: #115e59;
            --sva-coral: #e4573d;
            --sva-amber: #b7791f;
            --sva-shadow: 0 16px 42px rgba(31, 41, 51, 0.10);
            --sva-shadow-soft: 0 8px 24px rgba(31, 41, 51, 0.08);
        }

        .stApp {
            color: var(--sva-ink);
            background:
                linear-gradient(180deg, #f3f7f6 0%, #f7f9fb 34%, #ffffff 100%);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .block-container {
            max-width: 1360px;
            padding-top: 1.35rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3, label, .stMarkdown, .stText, .stCaption {
            letter-spacing: 0;
        }

        h2, h3 {
            color: var(--sva-ink);
            font-weight: 730;
        }

        [data-testid="stSidebar"] {
            background: #f8faf9;
            border-right: 1px solid var(--sva-line);
        }

        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.75rem;
        }

        .sva-masthead {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 24px;
            padding: 24px 26px;
            margin: 0 0 22px;
            background:
                linear-gradient(135deg, rgba(15, 118, 110, 0.11), rgba(228, 87, 61, 0.07)),
                var(--sva-panel);
            border: 1px solid rgba(15, 118, 110, 0.18);
            border-radius: 8px;
            box-shadow: var(--sva-shadow);
        }

        .sva-brand {
            display: flex;
            align-items: center;
            gap: 14px;
            min-width: 0;
        }

        .sva-mark {
            display: grid;
            place-items: center;
            width: 44px;
            height: 44px;
            color: white;
            font-weight: 780;
            background: #0f766e;
            border: 1px solid rgba(17, 94, 89, 0.35);
            border-radius: 8px;
            box-shadow: inset 0 -10px 18px rgba(0, 0, 0, 0.10), 0 10px 24px rgba(15, 118, 110, 0.22);
        }

        .sva-eyebrow {
            color: var(--sva-teal-dark);
            font-size: 0.72rem;
            font-weight: 760;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 3px;
        }

        .sva-title {
            font-size: clamp(1.65rem, 3vw, 2.4rem);
            line-height: 1.05;
            font-weight: 790;
            color: var(--sva-ink);
            margin: 0;
        }

        .sva-status-row {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            gap: 8px;
        }

        .sva-pill {
            padding: 7px 10px;
            font-size: 0.78rem;
            font-weight: 690;
            color: #344054;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(31, 41, 51, 0.10);
            border-radius: 999px;
            box-shadow: 0 4px 12px rgba(31, 41, 51, 0.07);
        }

        .sva-pill strong {
            color: var(--sva-teal-dark);
        }

        div[data-testid="stTabs"] [role="tablist"] {
            gap: 8px;
            padding: 7px;
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid var(--sva-line);
            border-radius: 8px;
            box-shadow: var(--sva-shadow-soft);
        }

        div[data-testid="stTabs"] [role="tab"] {
            min-height: 42px;
            padding: 8px 18px;
            border-radius: 6px;
            color: var(--sva-muted);
            font-weight: 690;
        }

        div[data-testid="stTabs"] [aria-selected="true"] {
            color: white;
            background: var(--sva-teal);
            box-shadow: 0 8px 18px rgba(15, 118, 110, 0.20);
        }

        div[data-testid="stFileUploader"] section {
            background: rgba(255, 255, 255, 0.82);
            border: 1px dashed rgba(15, 118, 110, 0.42);
            border-radius: 8px;
            box-shadow: var(--sva-shadow-soft);
        }

        div[data-testid="stFileUploader"] button {
            color: var(--sva-ink) !important;
            background: #ffffff !important;
            border: 1px solid #cdd6df !important;
            border-radius: 6px !important;
            box-shadow: 0 6px 16px rgba(31, 41, 51, 0.08) !important;
        }

        div[data-testid="stFileUploader"] button:hover {
            color: var(--sva-teal-dark) !important;
            background: #f7faf9 !important;
            border-color: rgba(15, 118, 110, 0.45) !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            min-height: 40px;
            border-radius: 6px;
            font-weight: 720;
            border: 1px solid rgba(15, 118, 110, 0.25);
            box-shadow: 0 8px 18px rgba(31, 41, 51, 0.08);
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            transform: translateY(-1px);
            border-color: rgba(15, 118, 110, 0.55);
            box-shadow: 0 12px 26px rgba(31, 41, 51, 0.12);
        }

        .stButton > button[kind="primary"] {
            background: var(--sva-teal);
            border-color: var(--sva-teal-dark);
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        textarea {
            border-radius: 6px !important;
            border-color: #cdd6df !important;
            box-shadow: 0 1px 0 rgba(31, 41, 51, 0.04);
        }

        div[data-baseweb="input"]:focus-within > div,
        div[data-baseweb="select"]:focus-within > div {
            border-color: var(--sva-teal) !important;
            box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"] {
            border: 1px solid var(--sva-line);
            border-radius: 8px;
            box-shadow: var(--sva-shadow-soft);
            overflow: hidden;
        }

        div[data-testid="stMetric"] {
            background: var(--sva-panel);
            border: 1px solid var(--sva-line);
            border-radius: 8px;
            padding: 12px 14px;
            box-shadow: var(--sva-shadow-soft);
        }

        div[data-testid="stAlert"] {
            border-radius: 8px;
            border: 1px solid rgba(31, 41, 51, 0.10);
            box-shadow: 0 8px 20px rgba(31, 41, 51, 0.07);
        }

        .sva-scan-result {
            margin-top: 12px;
            padding: 18px;
            background: #ffffff;
            border: 1px solid rgba(15, 118, 110, 0.28);
            border-left: 5px solid var(--sva-teal);
            border-radius: 8px;
            box-shadow: var(--sva-shadow);
        }

        .sva-scan-result-label {
            color: var(--sva-muted);
            font-size: 0.78rem;
            font-weight: 750;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .sva-scan-line {
            padding: 11px 12px;
            margin-top: 8px;
            color: #172026;
            background: #f7faf9;
            border: 1px solid #dbe7e4;
            border-radius: 6px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
            font-size: 0.95rem;
            line-height: 1.45;
            word-break: break-word;
        }

        .sva-suggestion-row {
            padding: 9px 0;
            border-bottom: 1px solid rgba(215, 221, 229, 0.72);
        }

        .sva-suggestion-label {
            padding: 9px 11px;
            min-height: 40px;
            color: #24313a;
            background: rgba(255, 255, 255, 0.80);
            border: 1px solid rgba(215, 221, 229, 0.72);
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(31, 41, 51, 0.05);
        }

        @media (max-width: 760px) {
            .sva-masthead {
                align-items: flex-start;
                flex-direction: column;
                padding: 18px;
            }

            .sva-status-row {
                justify-content: flex-start;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        f"""
        <div class="sva-masthead">
          <div class="sva-brand">
            <div class="sva-mark">SVA</div>
            <div>
              <div class="sva-eyebrow">Address Operations</div>
              <h1 class="sva-title">{escape(APP_NAME)}</h1>
            </div>
          </div>
          <div class="sva-status-row">
            <span class="sva-pill"><strong>34</strong> provinces</span>
            <span class="sva-pill"><strong>3,321</strong> wards</span>
            <span class="sva-pill">Local first</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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


inject_theme()
render_header()

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

    meta_left, meta_mid, meta_right = st.columns(3)
    meta_left.metric("Dòng", f"{len(source_df):,}")
    meta_mid.metric("Cột", f"{len(source_df.columns):,}")
    meta_right.metric("Giới hạn/lần", f"{MAX_ROWS:,}")

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
    count_left, count_mid, count_right = st.columns(3)
    count_left.metric("auto_ok", f"{counts.get('auto_ok', 0):,}")
    count_mid.metric("needs_review", f"{counts.get('needs_review', 0):,}")
    count_right.metric("failed", f"{counts.get('failed', 0):,}")

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

    scan_meta_left, scan_meta_right = st.columns(2)
    scan_meta_left.metric("Dòng kết quả", f"{len(result_df):,}")
    scan_meta_right.metric("Cột dữ liệu", f"{len(result_df.columns):,}")

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
    st.markdown(
        f"""
        <div class="sva-scan-result">
          <div class="sva-scan-result-label">Đã chọn mã đơn: {escape(order_code)}</div>
          <div class="sva-scan-line">{escape(line_1)}</div>
          <div class="sva-scan-line">{escape(line_2)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_order_suggestions(suggestions: pd.DataFrame, order_column: str) -> None:
    st.markdown("**Gợi ý mã đơn**")
    for index, row in suggestions.head(20).iterrows():
        st.markdown('<div class="sva-suggestion-row">', unsafe_allow_html=True)
        left, right = st.columns([1, 8])
        with left:
            st.button("Chọn", key=f"scan_pick_{index}", on_click=_select_suggestion, args=(index,))
        with right:
            label = escape(build_order_suggestion_label(row, order_column))
            st.markdown(f'<div class="sva-suggestion-label">{label}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


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
