import unittest

import pandas as pd

from shopee_location.legacy_mapping import LegacyAdminMapping


class LegacyMappingTests(unittest.TestCase):
    def setUp(self):
        self.mapping = LegacyAdminMapping.from_dataframe(
            pd.DataFrame(
                [
                    {
                        "city_name_old": "Thành Phố Hồ Chí Minh",
                        "district_name_old": "Quận 1",
                        "ward_name_old": "Phường Bến Nghé",
                        "city_name_new": "Thành Phố Hồ Chí Minh",
                        "ward_new_name": "Phường Sài Gòn",
                    },
                    {
                        "city_name_old": "Thành Phố Hồ Chí Minh",
                        "district_name_old": "Quận Bình Thạnh",
                        "ward_name_old": "Phường 22",
                        "city_name_new": "Thành Phố Hồ Chí Minh",
                        "ward_new_name": "Phường Thạnh Mỹ Tây",
                    },
                    {
                        "city_name_old": "Thành Phố Hà Nội",
                        "district_name_old": "Quận Ba Đình",
                        "ward_name_old": "Phường Đội Cấn",
                        "city_name_new": "Thành Phố Hà Nội",
                        "ward_new_name": "Phường Ba Đình",
                    },
                    {
                        "city_name_old": "Thành Phố Hà Nội",
                        "district_name_old": "Quận Ba Đình",
                        "ward_name_old": "Phường Đội Cấn",
                        "city_name_new": "Thành Phố Hà Nội",
                        "ward_new_name": "Phường Ngọc Hà",
                    },
                ]
            )
        )

    def test_maps_old_ward_to_unique_new_ward(self):
        result = self.mapping.match("Số 10 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM")

        self.assertTrue(result.found)
        self.assertFalse(result.ambiguous)
        self.assertEqual(result.unique_new_pair, ("Thành Phố Hồ Chí Minh", "Phường Sài Gòn"))

    def test_numeric_old_ward_requires_district_context(self):
        weak = self.mapping.match("Phường 22, TP.HCM")
        strong = self.mapping.match("Phường 22, Quận Bình Thạnh, TP.HCM")

        self.assertFalse(weak.found)
        self.assertTrue(strong.found)
        self.assertEqual(strong.unique_new_pair, ("Thành Phố Hồ Chí Minh", "Phường Thạnh Mỹ Tây"))

    def test_split_old_ward_is_ambiguous(self):
        result = self.mapping.match("Phường Đội Cấn, Quận Ba Đình, Hà Nội")

        self.assertTrue(result.found)
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.unique_new_pair)

    def test_district_name_is_not_treated_as_ward_without_city_context(self):
        mapping = LegacyAdminMapping.from_dataframe(
            pd.DataFrame(
                [
                    {
                        "city_name_old": "Tỉnh Bến Tre",
                        "district_name_old": "Huyện Châu Thành",
                        "ward_name_old": "Thị Trấn Châu Thành",
                        "city_name_new": "Tỉnh Vĩnh Long",
                        "ward_new_name": "Xã Phú Túc",
                    }
                ]
            )
        )

        result = mapping.match("Xã Tân Lý Tây, huyện Châu Thành, tỉnh Tiền Giang")

        self.assertFalse(result.found)

    def test_unique_cityless_old_ward_and_district_can_map(self):
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

        result = mapping.match("Tân Lý Tây, Châu Thành")

        self.assertTrue(result.found)
        self.assertEqual(result.unique_new_pair, ("Tỉnh Đồng Tháp", "Xã Châu Thành"))


if __name__ == "__main__":
    unittest.main()
