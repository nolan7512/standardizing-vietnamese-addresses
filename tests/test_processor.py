import unittest

from shopee_location.admin_units import AdminCatalog
from shopee_location.geocoding import GeocodeResult, GoogleGeocoder
from shopee_location.legacy_mapping import LegacyAdminMapping
from shopee_location.processor import AddressResolver
import pandas as pd


SAMPLE_PAYLOAD = [
    {
        "Code": "79",
        "Name": "Hồ Chí Minh",
        "FullName": "Thành phố Hồ Chí Minh",
        "Wards": [
            {"Code": "26734", "Name": "Sài Gòn", "FullName": "Phường Sài Gòn", "ProvinceCode": "79"},
            {"Code": "26737", "Name": "Thạnh Mỹ Tây", "FullName": "Phường Thạnh Mỹ Tây", "ProvinceCode": "79"},
        ],
    },
    {
        "Code": "87",
        "Name": "Đồng Tháp",
        "FullName": "Tỉnh Đồng Tháp",
        "Wards": [
            {"Code": "29245", "Name": "Châu Thành", "FullName": "Xã Châu Thành", "ProvinceCode": "87"},
            {"Code": "29248", "Name": "Tân Thanh", "FullName": "Xã Tân Thanh", "ProvinceCode": "87"},
        ],
    }
]


class FakeGeocoder:
    def geocode(self, query):
        return GeocodeResult(
            latitude=10.234,
            longitude=105.678,
            formatted_address="876/3 Đường Ngô Văn Hải, Xã Châu Thành, Tỉnh Đồng Tháp, Việt Nam",
            place_id="place",
            location_type="ROOFTOP",
            raw_status="OK",
            components=(
                {"long_name": "Xã Châu Thành", "short_name": "Châu Thành", "types": ["administrative_area_level_3"]},
                {"long_name": "Huyện Châu Thành", "short_name": "Châu Thành", "types": ["administrative_area_level_2"]},
                {"long_name": "Tỉnh Đồng Tháp", "short_name": "Đồng Tháp", "types": ["administrative_area_level_1"]},
            ),
        )


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        catalog = AdminCatalog.from_payload(SAMPLE_PAYLOAD)
        self.resolver = AddressResolver(catalog, geocoder=FakeGeocoder())

    def test_resolve_manual_sample_auto_ok(self):
        result = self.resolver.resolve(
            "876/3 (CLB Tuấn Nguyễn) Đường Ngô Văn Hải, tổ 22, ấp Tân Thanh",
            selected_location="Tỉnh Đồng Tháp, Xã Châu Thành",
        )

        self.assertEqual(result["province_new"], "Tỉnh Đồng Tháp")
        self.assertEqual(result["province_code_new"], "87")
        self.assertEqual(result["ward_new"], "Xã Châu Thành")
        self.assertEqual(result["ward_code_new"], "29245")
        self.assertEqual(result["group_or_to"], "tổ 22")
        self.assertEqual(result["hamlet_or_area"], "ấp Tân Thanh")
        self.assertEqual(result["house_number_or_street"], "876/3 (CLB Tuấn Nguyễn) Đường Ngô Văn Hải")
        self.assertEqual(result["latitude"], 10.234)
        self.assertEqual(result["status"], "auto_ok")

    def test_unprefixed_ward_and_province_are_matched_locally(self):
        resolver = AddressResolver(
            AdminCatalog.from_payload(SAMPLE_PAYLOAD),
            geocoder=GoogleGeocoder(api_key=""),
        )

        result = resolver.resolve("Châu Thành, Đồng Tháp")

        self.assertEqual(result["province_new"], "Tỉnh Đồng Tháp")
        self.assertEqual(result["ward_new"], "Xã Châu Thành")
        self.assertEqual(result["status"], "needs_review")

    def test_hamlet_does_not_become_unprefixed_ward(self):
        resolver = AddressResolver(
            AdminCatalog.from_payload(SAMPLE_PAYLOAD),
            geocoder=GoogleGeocoder(api_key=""),
        )

        result = resolver.resolve("ấp Tân Thanh, Tỉnh Đồng Tháp")

        self.assertEqual(result["province_new"], "Tỉnh Đồng Tháp")
        self.assertEqual(result["ward_new"], "")
        self.assertEqual(result["hamlet_or_area"], "ấp Tân Thanh")

    def test_legacy_mapping_converts_old_two_column_address(self):
        mapping = LegacyAdminMapping.from_dataframe(
            pd.DataFrame(
                [
                    {
                        "city_name_old": "Thành Phố Hồ Chí Minh",
                        "district_name_old": "Quận 1",
                        "ward_name_old": "Phường Bến Nghé",
                        "city_name_new": "Thành Phố Hồ Chí Minh",
                        "ward_new_name": "Phường Sài Gòn",
                    }
                ]
            )
        )
        resolver = AddressResolver(
            AdminCatalog.from_payload(SAMPLE_PAYLOAD),
            geocoder=GoogleGeocoder(api_key=""),
            legacy_mapping=mapping,
        )

        result = resolver.resolve("Số 10 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM")

        self.assertEqual(result["province_new"], "Thành phố Hồ Chí Minh")
        self.assertEqual(result["province_code_new"], "79")
        self.assertEqual(result["ward_new"], "Phường Sài Gòn")
        self.assertEqual(result["ward_code_new"], "26734")
        self.assertEqual(result["legacy_district_guess"], "Quận 1")

    def test_legacy_override_converts_intermediate_old_address(self):
        mapping = LegacyAdminMapping.from_dataframe(
            pd.DataFrame(
                [
                    {
                        "city_name_old": "Tỉnh Tiền Giang",
                        "district_name_old": "Huyện Châu Thành",
                        "ward_name_old": "Xã Tân Lý Tây",
                        "city_name_new": "Tỉnh Đồng Tháp",
                        "ward_new_name": "Xã Châu Thành",
                    }
                ]
            )
        )
        resolver = AddressResolver(
            AdminCatalog.from_payload(SAMPLE_PAYLOAD),
            geocoder=GoogleGeocoder(api_key=""),
            legacy_mapping=mapping,
        )

        result = resolver.resolve("876/3 Ấp Tân Thạnh, Tân Lý Tây, Châu Thành, Tiền Giang")

        self.assertEqual(result["province_new"], "Tỉnh Đồng Tháp")
        self.assertEqual(result["ward_new"], "Xã Châu Thành")
        self.assertEqual(result["house_number_or_street"], "876/3")

    def test_old_ward_name_is_not_fuzzy_matched_to_current_ward(self):
        resolver = AddressResolver(
            AdminCatalog.from_payload(
                [
                    {
                        "Code": "79",
                        "Name": "Hồ Chí Minh",
                        "FullName": "Thành phố Hồ Chí Minh",
                        "Wards": [
                            {"Code": "1", "Name": "Tân Thành", "FullName": "Phường Tân Thành", "ProvinceCode": "79"},
                        ],
                    }
                ]
            ),
            geocoder=GoogleGeocoder(api_key=""),
        )

        result = resolver.resolve("Xã Tân Thạnh Tây, Huyện Củ Chi, Thành phố Hồ Chí Minh")

        self.assertEqual(result["province_new"], "Thành phố Hồ Chí Minh")
        self.assertEqual(result["ward_new"], "")


if __name__ == "__main__":
    unittest.main()
