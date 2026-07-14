# -*- coding: utf-8 -*-
import unittest

from flask import Flask

from api import persistence, state
from api.routes import bp


class StationAdminApiTest(unittest.TestCase):
    def setUp(self):
        self.previous = {
            "create_station": persistence.create_station,
            "delete_station_by_coordinate": persistence.delete_station_by_coordinate,
            "list_operation_areas": persistence.list_operation_areas,
            "city_maps": state.city_maps,
            "apply_database_pois": state._apply_database_pois,
        }
        persistence.list_operation_areas = lambda include_deleted=False: [
            {"area_id": 10001, "code": "test-area", "name": "测试运营区"}
        ]
        state.city_maps = {10001: object()}
        state._apply_database_pois = lambda city_map, area: 2
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def tearDown(self):
        persistence.create_station = self.previous["create_station"]
        persistence.delete_station_by_coordinate = self.previous["delete_station_by_coordinate"]
        persistence.list_operation_areas = self.previous["list_operation_areas"]
        state.city_maps = self.previous["city_maps"]
        state._apply_database_pois = self.previous["apply_database_pois"]

    def test_create_stations_supports_partial_success(self):
        def fake_create_station(payload):
            if payload["station_name"] == "重复站点":
                raise persistence.PersistenceConflict(
                    "同一运营区已有相同经纬度站点",
                    code="station_coordinate_exists",
                    field="lon,lat",
                )
            return {
                "id": 1,
                "operation_area_id": payload["operation_area_id"],
                "station_name": payload["station_name"],
                "lon": payload["lon"],
                "lat": payload["lat"],
            }

        persistence.create_station = fake_create_station
        response = self.client.post("/admin/stations", json={
            "stations": [
                {
                    "operation_area_id": 10001,
                    "station_name": "大学城北门",
                    "lon": 113.12345678,
                    "lat": 23.12345678,
                },
                {
                    "operation_area_id": 10001,
                    "station_name": "重复站点",
                    "lon": 113.12345678,
                    "lat": 23.12345678,
                },
            ]
        })

        data = response.get_json()
        self.assertEqual(response.status_code, 207)
        self.assertEqual(data["success_count"], 1)
        self.assertEqual(data["failure_count"], 1)
        self.assertEqual(data["results"][1]["code"], "station_coordinate_exists")
        self.assertTrue(data["runtime_refresh"]["refreshed"])

    def test_create_station_requires_station_name(self):
        response = self.client.post("/admin/stations", json={
            "operation_area_id": 10001,
            "lon": 113.12345678,
            "lat": 23.12345678,
        })

        data = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(data["failure_count"], 1)
        self.assertEqual(data["results"][0]["code"], "station_name_required")

    def test_delete_station_by_coordinate_not_found(self):
        persistence.delete_station_by_coordinate = lambda lon, lat, operation_area_id=None: None

        response = self.client.delete("/admin/stations", json={
            "lon": 113.12345678,
            "lat": 23.12345678,
        })

        data = response.get_json()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(data["failure_count"], 1)
        self.assertEqual(data["results"][0]["code"], "station_not_found_by_coordinate")


if __name__ == "__main__":
    unittest.main()
