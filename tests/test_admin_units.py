import unittest

from shopee_location.admin_units import AdminCatalog


SAMPLE_PAYLOAD = [
    {
        "Code": "87",
        "Name": "Đồng Tháp",
        "FullName": "Tỉnh Đồng Tháp",
        "Wards": [
            {"Code": "29245", "Name": "Châu Thành", "FullName": "Xã Châu Thành", "ProvinceCode": "87"},
            {"Code": "29248", "Name": "Tân Thanh", "FullName": "Xã Tân Thanh", "ProvinceCode": "87"},
        ],
    },
    {
        "Code": "79",
        "Name": "Hồ Chí Minh",
        "FullName": "Thành phố Hồ Chí Minh",
        "Wards": [
            {"Code": "26734", "Name": "Bến Nghé", "FullName": "Phường Bến Nghé", "ProvinceCode": "79"},
        ],
    },
]


class AdminCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = AdminCatalog.from_payload(SAMPLE_PAYLOAD)

    def test_match_province_without_accents(self):
        match = self.catalog.match_province("Tinh Dong Thap")
        self.assertTrue(match.found)
        self.assertEqual(match.item.full_name, "Tỉnh Đồng Tháp")

    def test_match_ward_with_province_scope(self):
        province = self.catalog.match_province("Đồng Tháp").item
        match = self.catalog.match_ward("Xa Chau Thanh", province_code=province.code)
        self.assertTrue(match.found)
        self.assertEqual(match.item.full_name, "Xã Châu Thành")


if __name__ == "__main__":
    unittest.main()
