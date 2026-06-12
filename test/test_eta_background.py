# -*- coding: utf-8 -*-
"""后台订单 ETA 刷新与乘客端查询接口测试。"""

import unittest
import os
import asyncio
import time
from datetime import datetime, timedelta

from flask import Flask

from api import state
from api.core import CoreDispatcher
from api.models import Node, Order, Vehicle
from api.routes import bp as api_routes
from forecast.amap_eta_correct import DEFAULT_AMAP_KEY, AmapEtaCorrectClient, build_eta_pipeline_from_astar, run_blocking_io


class FakeCity:
    """最小路网桩：只提供 Order 和 ETA 适配层需要的接口。"""

    def __init__(self):
        self.a = Node("A", 113.0, 23.0)
        self.b = Node("B", 113.001, 23.001)
        self.c = Node("C", 113.002, 23.002)
        self.a.name = "起点"
        self.b.name = "上车点"
        self.c.name = "目的地"
        self.pois = [self.a, self.b, self.c]
        self.nodes_map = {node.id: node for node in self.pois}

    def get_path(self, start_node, end_node):
        if start_node.id == end_node.id:
            return 0.0, [start_node]
        return 100.0, [start_node, end_node]


class FakeEtaService:
    """高德 ETA 服务桩，避免测试访问网络。"""

    def __init__(self):
        self.payloads = []

    def build_eta_pipeline_from_astar(self, payload, now=None):
        self.payloads.append(payload)
        by_order_id = {}
        for segment in payload.get("segments", []):
            end_step = segment.get("endStep", {})
            if end_step.get("type") == "IDLE":
                continue
            order_id = str(end_step.get("orderId"))
            step_type = end_step.get("type")
            order_eta = by_order_id.setdefault(order_id, {
                "orderId": order_id,
                "pickupEtaSec": None,
                "dropoffEtaSec": None,
            })
            if step_type == "O":
                order_eta["pickupEtaSec"] = 60
            elif step_type == "D":
                order_eta["dropoffEtaSec"] = 300 if order_eta["pickupEtaSec"] is not None else 200

        return {
            "ok": True,
            "pipelineKind": "amap_eta_correct",
            "amapEnabled": True,
            "vehicleId": payload["vehicleId"],
            "routeVersion": payload["routeVersion"],
            "builtAtEpoch": now,
            "passengerEtas": list(by_order_id.values()),
            "idleEtaSec": 180 if any(
                segment.get("endStep", {}).get("type") == "IDLE"
                for segment in payload.get("segments", [])
            ) else None,
            "idleEtaDistanceM": 800 if any(
                segment.get("endStep", {}).get("type") == "IDLE"
                for segment in payload.get("segments", [])
            ) else None,
        }


class FakeAmapCorrectClient:
    """模拟 ETA pipeline 只调用驾车 ETA，不再调用轨迹纠偏。"""

    enabled = True

    def __init__(self):
        self.driving_calls = []
        self.grasp_called = False

    async def grasp_driving(self, points, speed_mps=16.6667):
        self.grasp_called = True
        raise AssertionError("ETA pipeline should not call grasp_driving")

    async def driving_eta(self, points):
        self.driving_calls.append(points)
        return {
            "ok": True,
            "duration_sec": 120,
            "distance_m": 600,
            "polyline": points,
            "traffic_status": "畅通",
            "waypoint_count": max(0, len(points) - 2),
        }


class FakeRouteGraspService:
    """路线纠偏服务桩，成功时给每个点轻微偏移以便断言写回。"""

    enabled = True

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def grasp_driving_sync(self, points, speed_mps=16.6667):
        self.calls.append(points)
        if self.fail:
            return {"ok": False, "reason": "grasp_failed", "request_points": len(points)}
        return {
            "ok": True,
            "points": [
                {**point, "lon": float(point["lon"]) + 0.0001}
                for point in points
            ],
            "distance_m": 123,
            "request_points": len(points),
        }

    def driving_eta_sync(self, points):
        return {"ok": False, "reason": "not_used"}


class RecordingGraspClient(AmapEtaCorrectClient):
    """记录高德纠偏 payload 的客户端，避免单测访问真实网络。"""

    def __init__(self):
        super().__init__(api_key="fake-key")
        self.payload_points = []

    def _build_grasp_payload(self, points, speed_mps):
        self.payload_points = [dict(point) for point in points]
        return super()._build_grasp_payload(points, speed_mps)

    def _urlopen_json(self, req):
        return {
            "errcode": "0",
            "data": {
                "points": [
                    {"x": point["lon"], "y": point["lat"]}
                    for point in self.payload_points
                ],
                "distance": 100,
            },
        }


def make_order(city, request_id="order-1"):
    request_time = datetime.now().replace(microsecond=0)
    return Order(
        request_id=request_id,
        o_lon=city.b.lon,
        o_lat=city.b.lat,
        d_lon=city.c.lon,
        d_lat=city.c.lat,
        request_time=request_time,
        expected_pickup_earliest=request_time,
        expected_pickup_latest=request_time + timedelta(minutes=20),
        passenger_count=1,
        city_map=city,
        req_time=request_time.timestamp(),
    )


def mark_vehicle_grasp_ready(vehicle, city):
    start_node = city.nodes_map[vehicle.next_node]
    result = CoreDispatcher.rebuild_vehicle_path_from_node(vehicle, city, start_node)
    raw_segments = CoreDispatcher._route_result_to_grasp_raw_segments(result)
    vehicle.planned_route_segment_raw_point = raw_segments
    vehicle.planned_route_segment_grasped_point = raw_segments
    vehicle.planned_route_grasped_point = CoreDispatcher._combine_grasped_segments(raw_segments)
    vehicle.planned_route_grasp_route_version = CoreDispatcher._vehicle_grasp_route_version(vehicle)
    vehicle.planned_route_grasp_status = "ready"
    vehicle.planned_route_grasp_error = None


class EtaBackgroundTest(unittest.TestCase):
    def setUp(self):
        self.previous = {
            "city": state.city,
            "fleet": state.fleet,
            "system_initialized": state.system_initialized,
            "eta_last_refresh_timestamp": CoreDispatcher.eta_last_refresh_timestamp,
            "route_grasp_last_refresh_timestamp": CoreDispatcher.route_grasp_last_refresh_timestamp,
            "order_pool": list(CoreDispatcher.order_pool),
            "completed_orders_pool": list(CoreDispatcher.completed_orders_pool),
        }
        CoreDispatcher.order_pool.clear()
        CoreDispatcher.completed_orders_pool.clear()

        self.city = FakeCity()
        self.vehicle = Vehicle("测试车", self.city.a.id, "#10b981", zone=0)
        self.vehicle.next_node = self.city.a.id
        self.vehicle.last_node = self.city.a.id
        self.vehicle.gps = {"lon": self.city.a.lon, "lat": self.city.a.lat}
        state.city = self.city
        state.fleet = [self.vehicle]
        state.system_initialized = True
        CoreDispatcher.eta_last_refresh_timestamp = None
        CoreDispatcher.route_grasp_last_refresh_timestamp = None

    def tearDown(self):
        state.city = self.previous["city"]
        state.fleet = self.previous["fleet"]
        state.system_initialized = self.previous["system_initialized"]
        CoreDispatcher.eta_last_refresh_timestamp = self.previous["eta_last_refresh_timestamp"]
        CoreDispatcher.route_grasp_last_refresh_timestamp = self.previous["route_grasp_last_refresh_timestamp"]
        CoreDispatcher.order_pool[:] = self.previous["order_pool"]
        CoreDispatcher.completed_orders_pool[:] = self.previous["completed_orders_pool"]

    def test_waiting_order_eta_is_written_and_payload_keeps_od_types(self):
        order = make_order(self.city)
        self.vehicle.planned_route = [
            {"type": "O", "order": order},
            {"type": "D", "order": order},
        ]
        mark_vehicle_grasp_ready(self.vehicle, self.city)
        fake_service = FakeEtaService()

        changed = state.refresh_order_etas_if_due(
            current_timestamp=1000.0,
            force=True,
            service=fake_service,
        )

        self.assertEqual(changed, 1)
        self.assertEqual(
            [segment["endStep"]["type"] for segment in fake_service.payloads[0]["segments"]],
            ["O", "D"],
        )
        self.assertEqual(order.eta_status, "ready")
        self.assertEqual(order.estimated_arrival_time, 1060.0)
        self.assertEqual(order.estimated_dropoff_time, 1300.0)
        self.assertEqual(order.estimated_arrival_eta_seconds, 60.0)
        self.assertEqual(order.estimated_dropoff_eta_seconds, 300.0)

    def test_riding_order_eta_uses_actual_pickup_and_live_dropoff(self):
        order = make_order(self.city)
        order.actual_pick_time = 900.0
        self.vehicle.on_board_orders = [order]
        self.vehicle.planned_route = [{"type": "D", "order": order}]
        mark_vehicle_grasp_ready(self.vehicle, self.city)

        changed = state.refresh_order_etas_if_due(
            current_timestamp=1000.0,
            force=True,
            service=FakeEtaService(),
        )

        self.assertEqual(changed, 1)
        self.assertEqual(order.estimated_arrival_time, 900.0)
        self.assertEqual(order.estimated_arrival_eta_seconds, 0)
        self.assertEqual(order.estimated_dropoff_time, 1200.0)
        self.assertEqual(order.estimated_dropoff_eta_seconds, 200.0)

    def test_passenger_eta_endpoint_returns_order_eta_snapshot(self):
        order = make_order(self.city)
        order.eta_status = "ready"
        order.eta_updated_at = 1000.0
        order.estimated_arrival_time = 1060.0
        order.estimated_arrival_eta_seconds = 60.0
        order.estimated_dropoff_time = 1360.0
        order.estimated_dropoff_eta_seconds = 360.0
        self.vehicle.planned_route = [
            {"type": "O", "order": order},
            {"type": "D", "order": order},
        ]

        app = Flask(__name__)
        app.register_blueprint(api_routes)
        response = app.test_client().get(f"/orders/{order.request_id}/eta")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["request_id"], str(order.request_id))
        self.assertEqual(data["status"], "waiting")
        self.assertEqual(data["vehicle"]["id"], self.vehicle.id)
        self.assertEqual(data["eta"]["status"], "ready")
        self.assertEqual(data["eta"]["estimated_arrival_time"], 1060.0)
        self.assertEqual(data["eta"]["estimated_dropoff_time"], 1360.0)

    def test_amap_eta_correct_accepts_string_route_version(self):
        previous = os.environ.get("AMAP_DISABLE")
        os.environ["AMAP_DISABLE"] = "1"
        try:
            payload = {
                "vehicleId": "bus-001",
                "routeVersion": "bus-001|A|O:order-1|D:order-1",
                "vehiclePosition": {"lon": 113.0, "lat": 23.0},
                "segments": [
                    {
                        "index": 0,
                        "endStep": {"type": "O", "orderId": "order-1"},
                        "points": [
                            {"lon": 113.0, "lat": 23.0},
                            {"lon": 113.001, "lat": 23.001},
                        ],
                    },
                    {
                        "index": 1,
                        "endStep": {"type": "D", "orderId": "order-1"},
                        "points": [
                            {"lon": 113.001, "lat": 23.001},
                            {"lon": 113.002, "lat": 23.002},
                        ],
                    },
                ],
            }

            result = build_eta_pipeline_from_astar(payload)
        finally:
            if previous is None:
                os.environ.pop("AMAP_DISABLE", None)
            else:
                os.environ["AMAP_DISABLE"] = previous

        self.assertEqual(result["routeVersion"], payload["routeVersion"])
        self.assertEqual(
            [segment["endStep"]["type"] for segment in result["segments"]],
            ["O", "D"],
        )

    def test_amap_grasp_payload_matches_frontend_time_shape(self):
        client = AmapEtaCorrectClient(api_key="test-key")
        payload = client._build_grasp_payload(
            [
                {"lon": 113.0, "lat": 23.0},
                {"lon": 113.001, "lat": 23.001},
                {"lon": 113.002, "lat": 23.002},
            ],
            16.6667,
        )
        timestamps = [point["tm"] for point in payload]

        self.assertGreater(timestamps[0], 1_000_000_000)
        self.assertEqual(timestamps[1:], [5, 10])
        self.assertEqual(payload[0]["sp"], 20.0)
        self.assertTrue(all(5.0 <= point["sp"] <= 80.0 for point in payload[1:]))

    def test_blocking_io_helper_works_without_asyncio_to_thread(self):
        sentinel = getattr(asyncio, "to_thread", None)
        if sentinel is not None:
            delattr(asyncio, "to_thread")
        try:
            result = asyncio.run(run_blocking_io(lambda value: value + 1, 41))
        finally:
            if sentinel is not None:
                setattr(asyncio, "to_thread", sentinel)

        self.assertEqual(result, 42)

    def test_amap_eta_correct_does_not_call_grasp(self):
        fake_amap = FakeAmapCorrectClient()
        result = build_eta_pipeline_from_astar(
            {
                "vehicleId": "bus-001",
                "routeVersion": "debug",
                "vehiclePosition": {"lon": 113.0, "lat": 23.0},
                "segments": [
                    {
                        "index": 0,
                        "endStep": {"type": "O", "orderId": "order-1"},
                        "points": [
                            {"lon": 113.0, "lat": 23.0},
                            {"lon": 113.001, "lat": 23.001},
                        ],
                    },
                    {
                        "index": 1,
                        "endStep": {"type": "D", "orderId": "order-1"},
                        "points": [
                            {"lon": 113.001, "lat": 23.001},
                            {"lon": 113.002, "lat": 23.002},
                        ],
                    },
                ],
            },
            amap=fake_amap,
        )

        self.assertFalse(fake_amap.grasp_called)
        self.assertEqual(result["passengerEtas"][0]["pickupEtaSec"], 120.0)
        self.assertEqual(result["passengerEtas"][0]["dropoffEtaSec"], 240.0)
        self.assertEqual(
            [segment["chosenSource"] for segment in result["segments"]],
            ["amap", "amap"],
        )

    def test_grasp_driving_uses_original_points_without_sampling(self):
        client = RecordingGraspClient()
        points = [
            {"lon": 113.0 + i * 0.0001, "lat": 23.0 + i * 0.00005}
            for i in range(120)
        ]

        result = asyncio.run(client.grasp_driving(points))

        self.assertTrue(result["ok"])
        self.assertEqual(result["request_points"], len(points))
        self.assertEqual(len(client.payload_points), len(points))

    def test_vehicle_default_grasp_fields(self):
        vehicle = Vehicle("默认车", self.city.a.id, "#fff", zone=0)

        self.assertEqual(vehicle.planned_route_grasped_point, [])
        self.assertEqual(vehicle.planned_route_segment_grasped_point, [])
        self.assertEqual(vehicle.planned_route_segment_raw_point, [])
        self.assertIsNone(vehicle.planned_route_grasp_status)

    def test_core_uses_eta_module_default_amap_key(self):
        self.assertEqual(CoreDispatcher.DEFAULT_AMAP_API_KEY, DEFAULT_AMAP_KEY)

    def test_route_update_marks_order_segments_pending(self):
        order = make_order(self.city)
        self.vehicle.planned_route = [
            {"type": "O", "order": order},
            {"type": "D", "order": order},
        ]

        CoreDispatcher.refresh_vehicle_route_metadata(self.vehicle, self.city)

        self.assertEqual(self.vehicle.planned_route_grasp_status, "pending")
        self.assertEqual(
            [segment["type"] for segment in self.vehicle.planned_route_segment_raw_point],
            ["O", "D"],
        )

    def test_route_update_marks_idle_segment_pending(self):
        self.vehicle.idle_target = {"node_id": self.city.c.id, "generated_at": 1000.0}
        self.vehicle.idle_forecast = {"pred_count": 3}

        CoreDispatcher.refresh_vehicle_route_metadata(self.vehicle, self.city)

        self.assertEqual(self.vehicle.planned_route_grasp_status, "pending")
        self.assertEqual(self.vehicle.planned_route_segment_raw_point[0]["type"], "IDLE")

    def test_route_grasp_success_writes_segment_and_combined_points(self):
        order = make_order(self.city)
        self.vehicle.planned_route = [{"type": "O", "order": order}]
        CoreDispatcher.refresh_vehicle_route_metadata(self.vehicle, self.city)

        changed = state.refresh_route_grasps_if_due(
            current_timestamp=1000.0,
            force=True,
            service=FakeRouteGraspService(),
        )

        self.assertEqual(changed, 1)
        self.assertEqual(self.vehicle.planned_route_grasp_status, "ready")
        self.assertEqual(len(self.vehicle.planned_route_segment_grasped_point), 1)
        self.assertGreater(self.vehicle.planned_route_grasped_point[0]["lon"], self.city.a.lon)

    def test_route_update_auto_submits_async_grasp_when_enabled(self):
        order = make_order(self.city)
        self.vehicle.planned_route = [{"type": "O", "order": order}]
        fake_service = FakeRouteGraspService()
        previous_service = CoreDispatcher.eta_service
        previous_service_key = CoreDispatcher.eta_service_api_key
        previous_lock = CoreDispatcher.route_grasp_apply_lock
        previous_enabled = CoreDispatcher.route_grasp_auto_submit_enabled
        api_key = os.getenv("AMAP_API_KEY") or CoreDispatcher.DEFAULT_AMAP_API_KEY

        CoreDispatcher.disable_route_grasp_async(wait=True)
        CoreDispatcher.eta_service = fake_service
        CoreDispatcher.eta_service_api_key = api_key
        CoreDispatcher.configure_route_grasp_async(
            state_lock=state.state_lock,
            enabled=True,
            max_workers=1,
        )
        try:
            CoreDispatcher.refresh_vehicle_route_metadata(self.vehicle, self.city)
            deadline = time.time() + 2.0
            while self.vehicle.planned_route_grasp_status != "ready" and time.time() < deadline:
                time.sleep(0.01)

            self.assertEqual(self.vehicle.planned_route_grasp_status, "ready")
            self.assertEqual(len(fake_service.calls), 1)
            self.assertGreater(self.vehicle.planned_route_grasped_point[0]["lon"], self.city.a.lon)
        finally:
            CoreDispatcher.disable_route_grasp_async(wait=True)
            CoreDispatcher.eta_service = previous_service
            CoreDispatcher.eta_service_api_key = previous_service_key
            CoreDispatcher.route_grasp_apply_lock = previous_lock
            CoreDispatcher.route_grasp_auto_submit_enabled = previous_enabled

    def test_route_grasp_discards_stale_result(self):
        order = make_order(self.city)
        self.vehicle.planned_route = [{"type": "O", "order": order}]
        CoreDispatcher.refresh_vehicle_route_metadata(self.vehicle, self.city)
        job = CoreDispatcher._collect_route_grasp_jobs([self.vehicle])[0]
        result = CoreDispatcher._run_route_grasp_job(FakeRouteGraspService(), job)
        self.vehicle.progress = 0.5

        changed = CoreDispatcher._apply_route_grasp_result(job, result, [self.vehicle])

        self.assertEqual(changed, 0)
        self.assertEqual(self.vehicle.planned_route_grasp_status, "pending")
        self.assertEqual(self.vehicle.planned_route_segment_grasped_point, [])

    def test_route_grasp_failure_keeps_previous_grasped_points(self):
        order = make_order(self.city)
        self.vehicle.planned_route = [{"type": "O", "order": order}]
        CoreDispatcher.refresh_vehicle_route_metadata(self.vehicle, self.city)
        state.refresh_route_grasps_if_due(
            current_timestamp=1000.0,
            force=True,
            service=FakeRouteGraspService(),
        )
        previous_points = list(self.vehicle.planned_route_grasped_point)
        CoreDispatcher.refresh_vehicle_route_metadata(self.vehicle, self.city)

        changed = state.refresh_route_grasps_if_due(
            current_timestamp=1005.0,
            force=True,
            service=FakeRouteGraspService(fail=True),
        )

        self.assertEqual(changed, 1)
        self.assertEqual(self.vehicle.planned_route_grasp_status, "error")
        self.assertEqual(self.vehicle.planned_route_grasped_point, previous_points)

    def test_idle_eta_is_written_to_vehicle(self):
        self.vehicle.idle_target = {"node_id": self.city.c.id, "generated_at": 1000.0}
        self.vehicle.idle_forecast = {"pred_count": 3}
        CoreDispatcher.refresh_vehicle_route_metadata(self.vehicle, self.city)
        state.refresh_route_grasps_if_due(
            current_timestamp=1000.0,
            force=True,
            service=FakeRouteGraspService(),
        )

        changed = state.refresh_order_etas_if_due(
            current_timestamp=1010.0,
            force=True,
            service=FakeEtaService(),
        )

        self.assertEqual(changed, 1)
        self.assertEqual(self.vehicle.idle_target_eta_status, "ready")
        self.assertEqual(self.vehicle.idle_target_eta_seconds, 180.0)
        self.assertEqual(self.vehicle.idle_target_eta_time, 1190.0)


if __name__ == "__main__":
    unittest.main()
