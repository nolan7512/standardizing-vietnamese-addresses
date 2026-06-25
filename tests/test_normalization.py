import unittest

from shopee_location.normalization import (
    extract_group_or_to,
    extract_hamlet_or_area,
    extract_house_number_or_street,
    extract_explicit_ward,
    extract_legacy_district,
    normalize_admin_name,
    normalize_text,
    strip_accents,
)


class NormalizationTests(unittest.TestCase):
    def test_strip_accents_handles_vietnamese_d(self):
        self.assertEqual(strip_accents("Đường Ngô Văn Hải"), "Duong Ngo Van Hai")

    def test_normalize_admin_name_removes_prefix(self):
        self.assertEqual(normalize_admin_name("TP. Hồ Chí Minh"), "ho chi minh")
        self.assertEqual(normalize_admin_name("Tỉnh Đồng Tháp"), "dong thap")

    def test_extract_hamlet_and_group(self):
        address = "876/3 Đường Ngô Văn Hải, tổ 22, ấp Tân Thanh"
        self.assertEqual(extract_group_or_to(address), "tổ 22")
        self.assertEqual(extract_hamlet_or_area(address), "ấp Tân Thanh")

    def test_extract_house_number_or_street(self):
        self.assertEqual(
            extract_house_number_or_street("876/3 Ấp Tân Thạnh, Tân Lý Tây, Châu Thành, Tiền Giang"),
            "876/3",
        )
        self.assertEqual(
            extract_house_number_or_street("876/3 đường Ngô Văn Hai, tổ 22, ấp Tân Thanh"),
            "876/3 đường Ngô Văn Hai",
        )
        self.assertEqual(
            extract_house_number_or_street("Số 10 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM"),
            "Số 10 Nguyễn Huệ",
        )
        self.assertEqual(extract_house_number_or_street("Tân Lý Tây, Châu Thành, Tiền Giang"), "")
        self.assertEqual(extract_house_number_or_street("xã Tân Lý Tây, Châu Thành, Tiền Giang"), "")

    def test_extract_legacy_district(self):
        self.assertEqual(extract_legacy_district("Phường 1, Quận 3, TP.HCM"), "Quận 3")

    def test_extract_explicit_ward_ignores_hamlet(self):
        self.assertEqual(extract_explicit_ward("tổ 22, ấp Tân Thanh"), "")
        self.assertEqual(extract_explicit_ward("P. Bến Nghé, Quận 1"), "P. Bến Nghé")

    def test_normalize_text_expands_common_abbreviation(self):
        self.assertIn("phuong", normalize_text("P. Bến Nghé"))


if __name__ == "__main__":
    unittest.main()
