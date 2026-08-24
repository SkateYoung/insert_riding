# -*- coding: utf-8 -*-
"""通勤快线独立业务模块单元测试。"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.commute_express import COMMUTE_CRUISING, COMMUTE_FIXED_WAITING, CommuteExpressService
from api.core import CoreDispatcher


def _stops():
    """生成固定循环线路站点快照。"""
    return [
        {"poi_id": 1, "poi_code": "p1", "station_name": "站点1", "lon": 113.0000, "lat": 23.0000, "node_code": "n1"},
        {"poi_id": 2, "poi_code": "p2", "station_name": "站点2", "lon": 113.0010, "lat": 23.0000, "node_code": "n2"},
        {"poi_id": 3, "poi_code": "p3", "station_name": "站点3", "lon": 113.0020, "lat": 23.0000, "node_code": "n3"},
        {"poi_id": 4, "poi_code": "p4", "station_name": "站点4", "lon": 113.0030, "lat": 23.0000, "node_code": "n4"},
    ]


def _vehicle(vehicle_id="V1", *, lon=113.0000, lat=23.0000, mode=COMMUTE_FIXED_WAITING, capacity=4):
    """生成测试用通勤快线车辆。"""
    return SimpleNamespace(
        id=vehicle_id,
        vehicle_id=vehicle_id,
        plate_no="粤A00001",
        operation_mode=mode,
        operation_area_id=10001,
        rest_status="operating",
        capacity=capacity,
        gps={"lon": lon, "lat": lat} if lon is not None and lat is not None else {},
        last_node="n1",
        next_node="n1",
        progress=0.0,
        planned_route=[],
        on_board_orders=[],
        idle_target=None,
        idle_forecast=None,
    )


class CommuteExpressServiceTest(unittest.TestCase):
    """验证通勤快线站序、派单和动态巴士隔离逻辑。"""

    def setUp(self):
        self.stops = _stops()
        self.line = {
            "line_code": "line_001",
            "line_name": "测试快线",
            "operation_area_id": 10001,
            "status": "enabled",
            "stops": self.stops,
        }
        self.assignment = {
            "vehicle_code": "V1",
            "line_code": "line_001",
            "operation_area_id": 10001,
            "task_mode": COMMUTE_FIXED_WAITING,
            "status": "active",
        }
        self.orders = {}

    def _patch_persistence(self):
        def save_order(order, create=False):
            self.orders[order["request_id"]] = dict(order)
            return dict(self.orders[order["request_id"]])

        return mock.patch.multiple(
            "api.commute_express.persistence",
            get_commute_line=mock.Mock(return_value=self.line),
            list_commute_vehicle_assignments=mock.Mock(return_value=[self.assignment]),
            save_commute_order=mock.Mock(side_effect=save_order),
            get_commute_order=mock.Mock(side_effect=lambda request_id: self.orders.get(request_id)),
            record_vehicle_runtime=mock.Mock(),
        )

    def test_loop_sequence_wraps_by_fixed_direction(self):
        sequence = CommuteExpressService._line_sequence_between(self.stops, 3, 1)
        self.assertEqual([stop["poi_id"] for stop in sequence], [3, 4, 1])

    def test_dynamic_pool_skips_commute_vehicle(self):
        self.assertFalse(CoreDispatcher._vehicle_can_accept_order(_vehicle()))

    def test_order_from_one_to_three_passes_station_two_without_service_stop(self):
        vehicle = _vehicle()
        payload = {
            "request_id": "commute_order_001",
            "line_code": "line_001",
            "origin_lon": 113.0000,
            "origin_lat": 23.0000,
            "destination_lon": 113.0020,
            "destination_lat": 23.0000,
            "passenger_phone": "13800000000",
            "passenger_count": 1,
        }

        with self._patch_persistence(), mock.patch("api.commute_express.fleet_push.submit_vehicle_navigation", return_value=True):
            result = CommuteExpressService.create_order(payload, [vehicle])

        self.assertEqual(result["status"], "waiting_pickup")
        self.assertEqual([step["type"] for step in vehicle.planned_route], ["O", "D"])
        self.assertEqual(vehicle.planned_route_segment_raw_point, [])
        self.assertEqual(vehicle.planned_route_segment_grasped_point, [])
        self.assertEqual(self.orders["commute_order_001"]["route_poi_sequence"], [1, 2, 3])
        self.assertEqual(self.orders["commute_order_001"]["order_source"], "commute_express")

    def test_matching_uses_gps_distance_for_both_commute_modes(self):
        vehicle_1 = _vehicle("V1", lon=113.0000, lat=23.0000, mode=COMMUTE_FIXED_WAITING)
        vehicle_2 = _vehicle("V2", lon=113.0010, lat=23.0000, mode=COMMUTE_CRUISING)
        assignments = [
            self.assignment,
            {
                "vehicle_code": "V2",
                "line_code": "line_001",
                "operation_area_id": 10001,
                "task_mode": COMMUTE_CRUISING,
                "status": "active",
            },
        ]
        payload = {
            "request_id": "commute_order_near",
            "line_code": "line_001",
            "origin_lon": 113.0010,
            "origin_lat": 23.0000,
            "destination_lon": 113.0020,
            "destination_lat": 23.0000,
            "passenger_phone": "13800000000",
            "passenger_count": 1,
        }
        with self._patch_persistence(), mock.patch(
            "api.commute_express.persistence.list_commute_vehicle_assignments",
            return_value=assignments,
        ), mock.patch("api.commute_express.fleet_push.submit_vehicle_navigation", return_value=True):
            result = CommuteExpressService.create_order(payload, [vehicle_1, vehicle_2])

        self.assertEqual(result["candidate"]["vehicle_id"], "V2")
        self.assertEqual(result["candidate"]["vehicle_code"], "V2")
        self.assertEqual([step["type"] for step in vehicle_2.planned_route], ["O", "D"])

    def test_vehicle_without_gps_is_not_candidate(self):
        vehicle = _vehicle(lon=None, lat=None)
        payload = {
            "request_id": "commute_order_no_gps",
            "line_code": "line_001",
            "origin_lon": 113.0000,
            "origin_lat": 23.0000,
            "destination_lon": 113.0020,
            "destination_lat": 23.0000,
            "passenger_phone": "13800000000",
            "passenger_count": 1,
        }
        with self._patch_persistence(), mock.patch("api.commute_express.fleet_push.submit_vehicle_navigation", return_value=True):
            result = CommuteExpressService.create_order(payload, [vehicle])

        self.assertEqual(result["status"], "pooled")
        self.assertEqual(vehicle.planned_route, [])

    def test_local_insertion_keeps_existing_step_order(self):
        vehicle = _vehicle()
        old_order = SimpleNamespace(
            request_id="old_order",
            passenger_count=1,
            status="waiting_pickup",
            order_source="commute_express",
            line_code="line_001",
            commute_origin_poi_id=4,
            commute_destination_poi_id=1,
            o_node=CommuteExpressService._node_like_from_stop(self.stops[3]),
            d_node=CommuteExpressService._node_like_from_stop(self.stops[0]),
        )
        vehicle.planned_route = [
            {"type": "O", "order": old_order},
            {"type": "D", "order": old_order},
        ]
        payload = {
            "request_id": "new_order",
            "line_code": "line_001",
            "origin_lon": 113.0010,
            "origin_lat": 23.0000,
            "destination_lon": 113.0020,
            "destination_lat": 23.0000,
            "passenger_phone": "13800000000",
            "passenger_count": 1,
        }
        with self._patch_persistence(), \
                mock.patch.object(CommuteExpressService, "_route_head_locked", return_value=False), \
                mock.patch("api.commute_express.fleet_push.submit_vehicle_navigation", return_value=True):
            result = CommuteExpressService.create_order(payload, [vehicle])

        self.assertEqual(result["status"], "waiting_pickup")
        route_ids = [step["order"].request_id for step in vehicle.planned_route]
        self.assertLess(route_ids.index("new_order"), route_ids.index("old_order"))
        self.assertEqual(
            [step["type"] for step in vehicle.planned_route if step["order"].request_id == "old_order"],
            ["O", "D"],
        )

    def test_local_insertion_keeps_locked_head_first(self):
        vehicle = _vehicle(lon=113.0030, lat=23.0000)
        old_order = SimpleNamespace(
            request_id="old_order",
            passenger_count=1,
            status="waiting_pickup",
            order_source="commute_express",
            line_code="line_001",
            commute_origin_poi_id=4,
            commute_destination_poi_id=1,
            o_node=CommuteExpressService._node_like_from_stop(self.stops[3]),
            d_node=CommuteExpressService._node_like_from_stop(self.stops[0]),
        )
        vehicle.planned_route = [
            {"type": "O", "order": old_order},
            {"type": "D", "order": old_order},
        ]
        payload = {
            "request_id": "new_order",
            "line_code": "line_001",
            "origin_lon": 113.0010,
            "origin_lat": 23.0000,
            "destination_lon": 113.0020,
            "destination_lat": 23.0000,
            "passenger_phone": "13800000000",
            "passenger_count": 1,
        }
        with self._patch_persistence(), mock.patch("api.commute_express.fleet_push.submit_vehicle_navigation", return_value=True):
            result = CommuteExpressService.create_order(payload, [vehicle])

        self.assertEqual(result["status"], "waiting_pickup")
        self.assertEqual(vehicle.planned_route[0]["order"].request_id, "old_order")
        self.assertEqual(vehicle.planned_route[0]["type"], "O")


if __name__ == "__main__":
    unittest.main()
