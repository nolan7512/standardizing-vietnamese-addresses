# Goal

Build a small local Streamlit project that normalizes Shopee customer addresses in Vietnam after administrative mergers. The app should infer new province/ward labels, preserve legacy district guesses for review, extract hamlet/group details, geocode with Google, cache API calls, and export corrected CSV/XLSX files.

# Assumptions / Open Questions

- Use Python 3.11 and a local Streamlit app.
- Use Google Geocoding API through `.env` or a password field in the UI.
- Use the post-merger Vietnamese administrative dataset from `thanglequoc/vietnamese-provinces-database`.
- Keep questionable rows as `needs_review` instead of forcing an automatic correction.

# Implementation Checklist

- [x] Scaffold project files, package modules, README, dependencies, and environment sample.
- [x] Implement text normalization, hamlet/group extraction, and legacy district extraction.
- [x] Implement administrative catalog loading/downloading and fuzzy matching.
- [x] Implement Google Geocoding client with SQLite cache.
- [x] Remove AddressKit and rely on local matching plus optional Google geocoding.
- [x] Integrate local VietMap old-to-new administrative mapping.
- [x] Add local override CSV for intermediate legacy cases missing from the main mapping.
- [x] Add `house_number_or_street` extraction for house/street details before hamlet/ward/district/province.
- [x] Add scan/lookup mode for processed result files by order code.
- [x] Show compact address lines after scanning an order QR/barcode.
- [x] Add suffix suggestions when typing 2-6 ending characters of an order code.
- [x] Move scan result above the long preview table.
- [x] Implement resolver confidence scoring and batch processing.
- [x] Implement Streamlit upload/mapping/preview/edit/export UI.
- [x] Add unit and integration tests.

# Verification Checklist

- [x] Run normalization and resolver tests.
- [x] Run geocoder cache test with a mocked Google response.
- [x] Run a manual sample based on the provided screenshot address.
- [x] Start the Streamlit app locally and confirm the server boots.
- [x] Test `F:\testcase.xlsx` with local mapping.
- [x] Test order-code lookup helper and Streamlit boot after adding scan mode.

# Review

- Implemented Streamlit app, local catalog matching, optional Google geocoding cache, export flow, and tests.
- `.\.venv\Scripts\python -m unittest discover -s tests -v` passed: 17 tests.
- `.\.venv\Scripts\python -m compileall app.py shopee_location tests` passed.
- Manual sample returned `Tỉnh Đồng Tháp`, `Xã Châu Thành`, `ấp Tân Thanh`, `tổ 22`, and `needs_review` without Google key.
- Manual sample `Châu Thành, Đồng Tháp` now returns `Tỉnh Đồng Tháp` and `Xã Châu Thành` without requiring `xã/tỉnh` prefixes.
- Output now includes stable current administrative codes: `province_code_new` and `ward_code_new` from the `thanglequoc/vietnamese-provinces-database` catalog.
- Streamlit boot verified at `http://localhost:8501` with HTTP 200.
- In-app browser reload verified the sidebar no longer shows AddressKit controls.
- Manual mapping checks: `Phường Bến Nghé, Quận 1, TP.HCM` maps to `Phường Sài Gòn`; `Phường 22, Quận Bình Thạnh, TP.HCM` maps to `Phường Thạnh Mỹ Tây`; ambiguous old mappings remain `needs_review`.
- `F:\testcase.xlsx` has 9 rows and 2 columns (`STT`, `Địa chỉ cụ thể`). After adding the `Tân Lý Tây` override, all 9 rows map to `Tỉnh Đồng Tháp`, `Xã Châu Thành`, codes `82` / `28519`, with `needs_review` because Google was not called in the CLI privacy test.
- The same testcase now also extracts `house_number_or_street = 876/3` for `876/3 Ấp Tân Thạnh...` while keeping `hamlet_or_area = Ấp Tân Thạnh`.
- Added `Quét mã đơn` tab. It uploads a processed result file, maps the order-code column, accepts scanner/keyboard input, and shows compact address lines from `shopee_location_value`, `province_new`, `ward_new`, `hamlet_or_area`, and `house_number_or_street`.
- Scan mode now suggests matching rows when the user types 2-6 ending characters and keeps the selected result above the preview table to avoid scrolling.
