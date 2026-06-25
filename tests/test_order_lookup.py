import unittest

import pandas as pd

from shopee_location.order_lookup import (
    build_order_suggestion_label,
    build_scan_display_lines,
    find_order_matches,
    find_order_suffix_matches,
    normalize_order_code,
)


class OrderLookupTests(unittest.TestCase):
    def test_normalize_order_code_removes_excel_float_suffix(self):
        self.assertEqual(normalize_order_code(12345.0), "12345")
        self.assertEqual(normalize_order_code(" SPX123\n"), "SPX123")

    def test_find_order_matches_exact_normalized_code(self):
        dataframe = pd.DataFrame(
            [
                {"Mã đơn": "A001", "province_new": "Tỉnh Đồng Tháp"},
                {"Mã đơn": "A002", "province_new": "Tỉnh Tây Ninh"},
            ]
        )

        result = find_order_matches(dataframe, "Mã đơn", "A002")

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["province_new"], "Tỉnh Tây Ninh")

    def test_find_order_suffix_matches_last_two_to_six_chars(self):
        dataframe = pd.DataFrame(
            [
                {"Mã đơn": "SPXVN001234", "province_new": "Tỉnh Đồng Tháp"},
                {"Mã đơn": "SPXVN991234", "province_new": "Tỉnh Tây Ninh"},
                {"Mã đơn": "SPXVN000777", "province_new": "Tỉnh An Giang"},
            ]
        )

        short = find_order_suffix_matches(dataframe, "Mã đơn", "4")
        matches = find_order_suffix_matches(dataframe, "Mã đơn", "1234")

        self.assertTrue(short.empty)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches["Mã đơn"].tolist(), ["SPXVN001234", "SPXVN991234"])

    def test_build_scan_display_lines(self):
        row = pd.Series(
            {
                "shopee_location_value": "Tỉnh Đồng Tháp, Xã Châu Thành",
                "province_new": "Tỉnh Đồng Tháp",
                "ward_new": "Xã Châu Thành",
                "hamlet_or_area": "Ấp Tân Thạnh",
                "house_number_or_street": "876/3",
            }
        )

        line_1, line_2 = build_scan_display_lines(row)

        self.assertEqual(line_1, "Tỉnh Đồng Tháp, Xã Châu Thành | Ấp Tân Thạnh | 876/3")
        self.assertEqual(line_2, "Tỉnh Đồng Tháp | Xã Châu Thành | Ấp Tân Thạnh | 876/3")

    def test_build_order_suggestion_label(self):
        row = pd.Series(
            {
                "Mã đơn": "SPXVN001234",
                "shopee_location_value": "Tỉnh Đồng Tháp, Xã Châu Thành",
                "hamlet_or_area": "Ấp Tân Thạnh",
                "house_number_or_street": "876/3",
            }
        )

        label = build_order_suggestion_label(row, "Mã đơn")

        self.assertEqual(label, "SPXVN001234 | Tỉnh Đồng Tháp, Xã Châu Thành | Ấp Tân Thạnh | 876/3")


if __name__ == "__main__":
    unittest.main()
