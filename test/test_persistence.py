# -*- coding: utf-8 -*-
"""Persistence serialization tests.

These tests do not connect to MySQL. They verify that runtime objects are
converted into queue tasks with the fields expected by the DDL.
"""

import unittest
from datetime import datetime, timedelta

from api import persistence
from api.core import CoreDispatcher
from api.models import Node, Order, Vehicle


class FakeCity:
    def __init__(self):
        self.a = Node("A", 113.0, 23.0)
        self.b = Node("B", 113.001, 23.001)
        self.c = Node("C", 113.002, 23.002)
        self.a.name = "Start"
        self.b.name = "Pickup"
        self.c.name = "Dropoff"
        self.pois = [self.a, self.b, self.c]
        self.nodes_map = {"A": self.a, "B": self.b, "C": self.c}
        self.edges = []

    def get_path(self, start_node, end_node):
        if start_node.id == end_node.id:
            return 0.0, [start_node]
        if start_node.id == "A" and end_node.id == "B":
            return 100.0, [self.a, self.b]
        if start_node.id == "B" and end_node.id == "C":
            return 200.0, [self.b, self.c]
        return 300.0, [start_node, end_node]


class FakeManager:
    tenant_id = "000000"

    def __init__(self):
        self.tasks = []

    def enqueue(self, op, payload):
        self.tasks.append((op, payload))
        return True

    def status(self):
        return {"enabled": True, "queue_size": len(self.tasks), "last_error": None}


def make_order(city, request_id="order-1"):
    now = datetime.now().replace(microsecond=0)
    return Order(
        request_id=request_id,
        o_lon=city.b.lon,
        o_lat=city.b.lat,
        d_lon=city.c.lon,
        d_lat=city.c.lat,
        request_time=now,
        expected_pickup_earliest=now,
        expected_pickup_latest=now + timedelta(minutes=20),
        passenger_count=1,
        city_map=city,
        req_time=now.timestamp(),
    )


class PersistenceSerializationTest(unittest.TestCase):
    def setUp(self):
        self.previous_manager = persistence._manager
        self.fake_manager = FakeManager()
        persistence._manager = self.fake_manager
        self.city = FakeCity()

    def tearDown(self):
        persistence._manager = self.previous_manager

    def test_disabled_manager_noops(self):
        disabled = persistence.MySqlPersistence({"enabled": False})
        self.assertFalse(disabled.enqueue("tenant", {"tenant_name": "x"}))
        self.assertFalse(disabled.status()["enabled"])

    def test_order_created_contains_order_route_fields(self):
        order = make_order(self.city)

        persistence.record_order_created(order, self.city, status="pooled")

        self.assertEqual(len(self.fake_manager.tasks), 1)
        op, payload = self.fake_manager.tasks[0]
        self.assertEqual(op, "order")
        self.assertEqual(payload["request_id"], "order-1")
        self.assertEqual(payload["status"], "pooled")
        self.assertEqual(payload["route_status"], "ready")
        self.assertEqual(payload["route_distance_m"], 200.0)
        self.assertTrue(payload["raw_route_points"])
        self.assertTrue(payload["route_segments"])

    def test_vehicle_route_writes_snapshot_steps_segments_and_order_route(self):
        order = make_order(self.city)
        vehicle = Vehicle("vehicle-1", self.city.a.id, "#10b981", zone=1)
        vehicle.vehicle_id = "vehicle-code-1"
        vehicle.plate_no = "粤A00001"
        vehicle.driver_id = "driver-code-1"
        vehicle.driver_no = "D001"
        vehicle.planned_route = [
            {"type": "O", "order": order},
            {"type": "D", "order": order},
        ]
        result = CoreDispatcher.rebuild_vehicle_path_from_node(vehicle, self.city, self.city.a)
        raw_segments = CoreDispatcher._route_result_to_grasp_raw_segments(result)
        vehicle.planned_route_point = result["path"]
        vehicle.planned_route_segment_raw_point = raw_segments
        vehicle.planned_route_segment_grasped_point = raw_segments
        vehicle.planned_route_grasped_point = CoreDispatcher._combine_grasped_segments(raw_segments)
        vehicle.planned_route_grasp_route_version = "route-v1"
        vehicle.planned_route_grasp_status = "ready"

        persistence.record_vehicle_route(vehicle, path_result=result)

        ops = [op for op, _ in self.fake_manager.tasks]
        self.assertIn("route_snapshot", ops)
        self.assertEqual(ops.count("route_step"), 2)
        self.assertEqual(ops.count("route_segment"), 2)
        self.assertIn("order", ops)

        order_payload = [payload for op, payload in self.fake_manager.tasks if op == "order"][-1]
        self.assertEqual(order_payload["request_id"], "order-1")
        self.assertEqual(order_payload["route_version"], "route-v1")
        self.assertTrue(order_payload["route_segments"])
        self.assertTrue(order_payload["raw_route_points"])


if __name__ == "__main__":
    unittest.main()
