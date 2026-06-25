# Standardizing Vietnamese Addresses

Web app nhỏ để chuẩn hóa địa chỉ giao hàng Việt Nam sau sáp nhập đơn vị hành chính. App đọc CSV/Excel, dùng phần `địa chỉ cụ thể` làm tín hiệu chính, đối chiếu danh mục tỉnh/xã mới, gọi Google Geocoding để lấy tọa độ, rồi xuất file có trạng thái `auto_ok`, `needs_review`, hoặc `failed`.

## Chức năng

- Upload CSV/XLSX đơn hàng Shopee.
- Chọn cột địa chỉ cụ thể và các cột gợi ý như tỉnh/thành, quận/huyện/xã nếu có.
- Trích `ấp/thôn/khu phố`, `tổ/nhóm`, và quận/huyện cũ nếu xuất hiện.
- Trích phần số nhà/đường còn lại vào `house_number_or_street`, ví dụ `876/3` hoặc `876/3 đường Ngô Văn Hai`.
- Chuyển địa chỉ cũ 3 cấp sang địa chỉ mới bằng bảng mapping local VietMap nếu địa chỉ có đủ xã/phường cũ + quận/huyện + tỉnh.
- Match mềm tỉnh/thành và xã/phường/đặc khu theo danh mục hành chính mới.
- Xuất cả tên và mã đơn vị mới (`province_code_new`, `ward_code_new`) từ catalog `thanglequoc/vietnamese-provinces-database`.
- Gọi Google Geocoding API với cache SQLite để giảm phí.
- Preview, lọc theo trạng thái, chỉnh tay vài dòng, tải kết quả CSV/XLSX.
- Tab `Quét mã đơn` cho phép upload file kết quả, quét/nhập mã đơn từ barcode/QR scanner dạng bàn phím, rồi hiển thị nhanh 2 dòng địa chỉ đã chuẩn hóa.

## Cài đặt

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env` và điền:

```text
GOOGLE_MAPS_API_KEY=...
LEGACY_MAPPING_XLSX=data/admin_mapping_old_to_new_10_25.xlsx
LEGACY_MAPPING_OVERRIDES_CSV=data/legacy_mapping_overrides.csv
```

Nếu chưa có key, app vẫn chạy được nhưng không có latitude/longitude và đa số dòng sẽ cần duyệt.
Nếu chưa có file mapping, app tự tải từ VietMap về `data/admin_mapping_old_to_new_10_25.xlsx`.
File override CSV dùng để vá các trường hợp trung gian không có trong mapping chính, ví dụ `Xã Tân Lý Tây, Huyện Châu Thành, Tỉnh Tiền Giang`.

## Chạy app

```powershell
.\.venv\Scripts\python -m streamlit run app.py
```

Người dùng không rành kỹ thuật có thể double-click `run.bat`. File này sẽ tạo môi trường `.venv`, cài thư viện, tạo `.env` nếu chưa có, mở browser và chạy app tại `http://localhost:8501`.

Mặc định app tải danh mục từ:

```text
https://raw.githubusercontent.com/thanglequoc/vietnamese-provinces-database/master/json/vn_only_simplified_json_generated_data_vn_units_minified.json
```

File được cache tại `data/admin_units.json`.

## Chạy test

```powershell
python -m unittest discover -s tests -v
```

## Quét mã đơn

Sau khi đã xuất file kết quả, mở tab `Quét mã đơn`, upload file CSV/XLSX kết quả, chọn cột mã đơn rồi quét hoặc nhập mã đơn hàng. Có thể nhập 2-6 ký tự cuối mã đơn để hiện danh sách gợi ý, sau đó chọn dòng đúng. Khi tìm thấy mã, app hiển thị kết quả ngay dưới ô nhập, trước bảng dữ liệu dài:

```text
shopee_location_value | hamlet_or_area | house_number_or_street
province_new | ward_new | hamlet_or_area | house_number_or_street
```

## Ghi chú dữ liệu

- Danh mục hành chính mới dùng mô hình tỉnh/thành và xã/phường/đặc khu.
- Danh mục `thanglequoc/vietnamese-provinces-database` đang phù hợp cho catalog hiện hành 34 tỉnh/thành và 3.321 xã/phường/đặc khu; phần GIS của repo có thể dùng ở bước sau để kiểm tra point-in-polygon hoặc lấy centroid xã/phường khi không có tọa độ chính xác.
- `legacy_district_guess` là thông tin đối soát khi địa chỉ hoặc Google còn trả tên quận/huyện cũ.
- App không gọi AddressKit. Địa chỉ cũ 3 cấp được chuyển bằng bảng mapping local; nếu một xã/phường cũ tách sang nhiều đơn vị mới thì app đánh dấu `needs_review`.
- Nếu Google và dữ liệu khách chọn mâu thuẫn, app hạ confidence và đánh dấu `needs_review`.

## Nguồn dữ liệu mapping

- Danh mục/mapping cũ-mới VietMap: https://github.com/vietmap-company/vietnam_administrative_address
- Mapping XLSX: https://github.com/vietmap-company/vietnam_administrative_address/tree/main/admin_mapping
- Danh mục hành chính mới/GIS: https://github.com/thanglequoc/vietnamese-provinces-database
