# Local Geocoding Options

## Short Answer

Google Geocoding does not provide a downloadable offline dataset for local geocoding. To get Google-quality coordinates, use Google Geocoding API with an API key and cache only within the allowed policy. For fully local geocoding, use open map/address data and accept lower coverage for Vietnamese house-level addresses.

## Practical Options

1. Keep current app behavior:
   - Local administrative matching from `data/admin_units.json`.
   - Google Geocoding API only when `GOOGLE_MAPS_API_KEY` is configured.
   - Rows without exact coordinates remain `needs_review`.

2. Add ward/province centroid fallback:
   - Download or build centroids for province/ward polygons.
   - The `thanglequoc/vietnamese-provinces-database` GIS add-on has WGS84 ward/province polygons that can be joined by `province_code` and `ward_code`.
   - Return approximate latitude/longitude when exact geocoding is unavailable.
   - Add a precision column such as `coordinate_precision = ward_centroid`.

3. Self-host OpenStreetMap geocoding:
   - Download Vietnam OSM extract from Geofabrik.
   - Import into Nominatim, Pelias, or Photon.
   - Works offline/local, but house-number coverage in Vietnam can be incomplete.

4. Use Overture Maps data:
   - Query/download address and places GeoParquet for Vietnam.
   - Useful for POIs/places and some address points, but still needs a matching engine.

## Recommended Path For This Project

- Phase 1: Keep local admin correction, VietMap old-to-new mapping, and optional Google.
- Phase 2: Add ward centroid fallback so every matched ward has an approximate coordinate.
- Phase 2.5: Use ward polygons to reverse-check Google/OSM coordinates with point-in-polygon before marking a row `auto_ok`.
- Phase 3: Add a `geocoder_provider` abstraction and support local Nominatim when a local server URL is configured.
- Phase 4: Use local Nominatim/Pelias/Photon for OSM exact geocoding if a local server is imported from the Vietnam extract.

## Source Links

- Google Geocoding policies: https://developers.google.com/maps/documentation/geocoding/policies
- VietMap administrative old-to-new mapping: https://github.com/vietmap-company/vietnam_administrative_address/tree/main/admin_mapping
- Vietnamese provinces database JSON/GIS: https://github.com/thanglequoc/vietnamese-provinces-database
- Vietnamese provinces database GIS docs: https://github.com/thanglequoc/vietnamese-provinces-database/blob/master/docs/gis/gis_readme_vi.md
- Geofabrik Vietnam OSM extract: https://download.geofabrik.de/asia/vietnam.html
- Nominatim installation: https://nominatim.org/release-docs/latest/admin/Installation/
- Overture addresses docs: https://docs.overturemaps.org/guides/addresses/
- Overture data access: https://docs.overturemaps.org/getting-data/cloud-sources/
