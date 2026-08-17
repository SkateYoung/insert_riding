# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from api import reflect_mapping, state
from api.models import Node


class ReflectMappingTest(unittest.TestCase):
    def test_load_reflect_station_index_uses_direction_key(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as handle:
            path = handle.name
            handle.write("STIONNAME,name,Calc_Dir,gd_lng,gd_lat\n")
            handle.write("站点A,道路A,东-西,113.1,23.1\n")
            handle.write("站点A,道路A,西-东,113.2,23.2\n")
        try:
            index = reflect_mapping.load_reflect_station_index(path)
            item = reflect_mapping.find_reflect_station(index, " 站点A ", "道路A", "西-东")
            self.assertIsNotNone(item)
            self.assertEqual(item["gd_lng"], 113.2)
            self.assertEqual(item["gd_lat"], 23.2)
            self.assertEqual(item["direction"], "西-东")
            self.assertIsNone(reflect_mapping.find_reflect_station(index, "站点A", "道路A", "南-北"))
        finally:
            os.remove(path)

    def test_load_reflect_station_index_keeps_first_duplicate_key(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as handle:
            path = handle.name
            handle.write("STIONNAME,name,Calc_Dir,gd_lng,gd_lat,dist\n")
            handle.write("站点A,道路A,东-西,113.1,23.1,99\n")
            handle.write("站点A,道路A,东-西,113.2,23.2,1\n")
        try:
            index = reflect_mapping.load_reflect_station_index(path)
            item = reflect_mapping.find_reflect_station(index, "站点A", "道路A", "东-西")
            self.assertIsNotNone(item)
            self.assertEqual(item["gd_lng"], 113.1)
            self.assertEqual(item["gd_lat"], 23.1)
            self.assertNotIn("dist", item)
            self.assertNotIn("_sort_dist", item)
        finally:
            os.remove(path)


class ReflectPoiRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.previous_list_pois = state.persistence.list_pois
        self.previous_load_index = state.reflect_mapping.load_reflect_station_index

    def tearDown(self):
        state.persistence.list_pois = self.previous_list_pois
        state.reflect_mapping.load_reflect_station_index = self.previous_load_index

    def _fake_city_map(self):
        class FakeCityMap:
            pass

        city_map = FakeCityMap()
        city_map.nodes_map = {
            "113.000000_23.000000": Node("113.000000_23.000000", 113.0, 23.0),
            "113.200000_23.200000": Node("113.200000_23.200000", 113.2, 23.2),
        }
        city_map.pois = []
        return city_map

    def test_apply_database_pois_uses_reflect_node_first(self):
        city_map = self._fake_city_map()
        state.persistence.list_pois = lambda operation_area_id=None, operation_area_ids=None: [
            {
                "longitude": 113.0,
                "latitude": 23.0,
                "poi_name": "站点A",
                "areas": "道路A",
                "station_direction": "东-西",
                "poi_code": "poi_a",
                "station_id": "station_a",
                "operation_area_id": 10001,
            }
        ]
        state.reflect_mapping.load_reflect_station_index = lambda: {
            ("站点A", "道路A", "东-西"): {
                "station_name": "站点A",
                "road_name": "道路A",
                "direction": "东-西",
                "gd_lng": 113.2,
                "gd_lat": 23.2,
            }
        }

        count = state._apply_database_pois(city_map, {"area_id": 10001, "code": "area_1"})

        self.assertEqual(count, 1)
        self.assertEqual(city_map.pois[0].id, "113.200000_23.200000")
        self.assertEqual(city_map.pois[0].poi_snap_source, "reflect_csv")
        self.assertEqual(city_map.pois[0].reflect_road_name, "道路A")
        self.assertEqual(city_map.pois[0].reflect_direction, "东-西")

    def test_apply_database_pois_falls_back_to_nearest_node(self):
        city_map = self._fake_city_map()
        state.persistence.list_pois = lambda operation_area_id=None, operation_area_ids=None: [
            {
                "longitude": 113.0,
                "latitude": 23.0,
                "poi_name": "站点A",
                "areas": "道路A",
                "station_direction": "东-西",
                "poi_code": "poi_a",
                "station_id": "station_a",
                "operation_area_id": 10001,
            }
        ]
        state.reflect_mapping.load_reflect_station_index = lambda: {}

        count = state._apply_database_pois(city_map, {"area_id": 10001, "code": "area_1"})

        self.assertEqual(count, 1)
        self.assertEqual(city_map.pois[0].id, "113.000000_23.000000")
        self.assertEqual(city_map.pois[0].poi_snap_source, "nearest_node")

    def test_apply_database_pois_snaps_from_reflect_coordinate_when_node_missing(self):
        city_map = self._fake_city_map()
        state.persistence.list_pois = lambda operation_area_id=None, operation_area_ids=None: [
            {
                "longitude": 113.0,
                "latitude": 23.0,
                "poi_name": "站点A",
                "areas": "道路A",
                "station_direction": "东-西",
                "poi_code": "poi_a",
                "station_id": "station_a",
                "operation_area_id": 10001,
            }
        ]
        state.reflect_mapping.load_reflect_station_index = lambda: {
            ("站点A", "道路A", "东-西"): {
                "station_name": "站点A",
                "road_name": "道路A",
                "direction": "东-西",
                "gd_lng": 113.19,
                "gd_lat": 23.19,
            }
        }

        count = state._apply_database_pois(city_map, {"area_id": 10001, "code": "area_1"})

        self.assertEqual(count, 1)
        self.assertEqual(city_map.pois[0].id, "113.200000_23.200000")
        self.assertEqual(city_map.pois[0].poi_snap_source, "reflect_csv_nearest_node")
        self.assertEqual(city_map.pois[0].reflect_snap_mode, "nearest_node")


if __name__ == "__main__":
    unittest.main()
