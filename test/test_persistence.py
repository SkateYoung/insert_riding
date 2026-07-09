# -*- coding: utf-8 -*-
"""Persistence serialization tests.

These tests do not connect to MySQL. They verify that runtime objects are
converted into queue tasks with the fields expected by the DDL.
"""

import os
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

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


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql = None
        self.executed_params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed_sql = sql
        self.executed_params = list(params or [])

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


class FakePyMySql:
    class cursors:
        DictCursor = object

    def __init__(self, rows):
        self.connection = FakeConnection(rows)
        self.connect_kwargs = None

    def connect(self, **kwargs):
        self.connect_kwargs = kwargs
        return self.connection


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
        passenger_phone="13900000001",
        passenger_id="passenger-1",
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

    def test_ssl_connection_kwargs_are_generated_from_config(self):
        if persistence.pymysql is None:
            self.skipTest("PyMySQL is not available")
        manager = persistence.MySqlPersistence({
            "enabled": False,
            "host": "bus-mysql",
            "port": "16336",
            "user": "zhgjuser",
            "password": "secret",
            "database": "busx_tms",
            "ssl_ca": "database/ca.pem",
            "ssl_verify_cert": "1",
            "ssl_verify_identity": "1",
        })

        kwargs = manager._connect_kwargs(autocommit=True)

        self.assertEqual(kwargs["host"], "bus-mysql")
        self.assertEqual(kwargs["port"], 16336)
        self.assertEqual(kwargs["user"], "zhgjuser")
        self.assertEqual(kwargs["database"], "busx_tms")
        self.assertTrue(kwargs["autocommit"])
        self.assertEqual(kwargs["ssl_ca"], os.path.abspath("database/ca.pem"))
        self.assertTrue(kwargs["ssl_verify_cert"])
        self.assertTrue(kwargs["ssl_verify_identity"])
        self.assertTrue(manager.status()["ssl_enabled"])

    def test_order_created_contains_order_route_fields(self):
        order = make_order(self.city)

        persistence.record_order_created(order, self.city, status="pooled")

        self.assertEqual(len(self.fake_manager.tasks), 1)
        op, payload = self.fake_manager.tasks[0]
        self.assertEqual(op, "order")
        self.assertEqual(payload["request_id"], "order-1")
        self.assertEqual(payload["passenger_phone"], "13900000001")
        self.assertEqual(payload["passenger_code"], "passenger-1")
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

    def test_vehicle_snapshot_does_not_refresh_answer_time(self):
        order = make_order(self.city)
        vehicle = Vehicle("vehicle-1", self.city.a.id, "#10b981", zone=1)
        vehicle.vehicle_id = "vehicle-code-1"
        vehicle.planned_route = [{"type": "O", "order": order}]

        persistence.record_order_snapshot(order, status="matched", vehicle=vehicle)

        order_payload = [payload for op, payload in self.fake_manager.tasks if op == "order"][-1]
        self.assertIsNone(order.answer_time)
        self.assertIsNone(order_payload["answer_time"])

    def test_dispatch_assignment_sets_answer_time_once(self):
        order = make_order(self.city)
        vehicle = Vehicle("vehicle-1", self.city.a.id, "#10b981", zone=1)
        vehicle.vehicle_id = "vehicle-code-1"
        vehicle.planned_route = [
            {"type": "O", "order": order},
            {"type": "D", "order": order},
        ]

        persistence.record_dispatch_assignment(order, vehicle, city_map=self.city, path_result={})
        first_answer_time = order.answer_time
        persistence.record_eta_result(vehicle)

        order_payloads = [payload for op, payload in self.fake_manager.tasks if op == "order"]
        self.assertIsNotNone(first_answer_time)
        self.assertEqual(order.answer_time, first_answer_time)
        self.assertTrue(order_payloads)
        self.assertTrue(all(payload["answer_time"] == first_answer_time for payload in order_payloads))

    def test_query_orders_builds_filters_and_normalizes_rows(self):
        previous_pymysql = persistence.pymysql
        row_created_at = datetime(2026, 7, 5, 12, 0, 0)
        fake_pymysql = FakePyMySql([{
            "id": 1,
            "request_id": "order-1",
            "passenger_phone": "13900000001",
            "status": "completed",
            "origin_name": "Start",
            "destination_name": "Dropoff",
            "assigned_plate_no": "粤A00001",
            "route_distance_m": Decimal("1234.50"),
            "raw_route_points": '[{"lon":113.0,"lat":23.0}]',
            "created_at": row_created_at,
            "assigned_driver_name": "张三",
            "assigned_vehicle_code": "vehicle-1",
        }])
        persistence.pymysql = fake_pymysql
        try:
            manager = persistence.MySqlPersistence({
                "enabled": True,
                "tenant_id": "test",
                "host": "127.0.0.1",
                "user": "root",
                "password": "",
                "database": "bus_dispatch_core",
            })
            orders = manager.query_orders({
                "request_id": "order-1",
                "passenger_phone": "13900000001",
                "status": "completed",
                "station_name": "Drop",
                "driver_name": "张",
                "plate_no": "粤A00001",
                "created_at": {
                    "start": "2026-07-01 00:00:00",
                    "end": "2026-07-05 23:59:59",
                },
                "limit": 10,
                "offset": 5,
            })
        finally:
            persistence.pymysql = previous_pymysql

        sql = fake_pymysql.connection.cursor_obj.executed_sql
        params = fake_pymysql.connection.cursor_obj.executed_params
        self.assertIn("o.request_id = %s", sql)
        self.assertIn("o.passenger_phone = %s", sql)
        self.assertIn("(o.origin_name LIKE %s OR o.destination_name LIKE %s)", sql)
        self.assertIn("d.driver_name LIKE %s", sql)
        self.assertIn("o.assigned_plate_no = %s", sql)
        self.assertIn("o.created_at >= %s", sql)
        self.assertIn("LIMIT %s OFFSET %s", sql)
        self.assertEqual(params[0], "test")
        self.assertIn("order-1", params)
        self.assertEqual(params[-2:], [10, 5])
        self.assertEqual(orders[0]["created_at"], "2026-07-05 12:00:00")
        self.assertEqual(orders[0]["route_distance_m"], 1234.5)
        self.assertEqual(orders[0]["raw_route_points"], [{"lon": 113.0, "lat": 23.0}])
        self.assertTrue(fake_pymysql.connection.closed)

    def test_query_orders_requires_database(self):
        manager = persistence.MySqlPersistence({"enabled": False})
        with self.assertRaises(persistence.PersistenceUnavailable):
            manager.query_orders({})


if __name__ == "__main__":
    unittest.main()
