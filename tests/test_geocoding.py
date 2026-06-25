import tempfile
import unittest
from pathlib import Path

from shopee_location.geocoding import GoogleGeocoder


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Xã Châu Thành, Tỉnh Đồng Tháp, Việt Nam",
                    "place_id": "abc",
                    "geometry": {
                        "location": {"lat": 10.1, "lng": 105.2},
                        "location_type": "ROOFTOP",
                    },
                    "address_components": [
                        {"long_name": "Xã Châu Thành", "short_name": "Châu Thành", "types": ["administrative_area_level_3"]},
                        {"long_name": "Huyện Châu Thành", "short_name": "Châu Thành", "types": ["administrative_area_level_2"]},
                        {"long_name": "Tỉnh Đồng Tháp", "short_name": "Đồng Tháp", "types": ["administrative_area_level_1"]},
                    ],
                }
            ],
        }


class FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return FakeResponse()


class GeocodingTests(unittest.TestCase):
    def test_google_geocoder_uses_sqlite_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = FakeSession()
            cache_path = Path(tmp) / "cache.sqlite"
            geocoder = GoogleGeocoder("fake-key", cache_path=cache_path, session=session)
            first = geocoder.geocode("876/3 Đường Ngô Văn Hải, Xã Châu Thành, Đồng Tháp")
            second = geocoder.geocode("876/3 Đường Ngô Văn Hải, Xã Châu Thành, Đồng Tháp")

            self.assertTrue(first.ok)
            self.assertTrue(second.ok)
            self.assertTrue(second.from_cache)
            self.assertEqual(session.calls, 1)


if __name__ == "__main__":
    unittest.main()
