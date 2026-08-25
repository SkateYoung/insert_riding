# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from flask import Flask

from api import persistence, state
from api.core import CoreDispatcher
from api.models import Node, Order, Vehicle
from api.routes import bp


class FakeCity:
    def __init__(self):
        self.a = Node("A", 113.0000, 23.0000)
        self.b = Node("B", 113.0010, 23.0000)
        self.c = Node("C", 113.0020, 23.0000)
        self.a.name = "起点"
        self.b.name = "中点"
        self.c.name = "终点"
        self.a.poi_code = "poi-a"
        self.b.poi_code = "poi-b"
        self.c.poi_code = "poi-c"
        self.a.zone = self.b.zone = self.c.zone = 1
        self.a.neighbors = {"B": 100.0}
        self.b.neighbors = {"A": 100.0, "C": 100.0}
        self.c.neighbors = {"B": 100.0}
        self.nodes_map = {"A": self.a, "B": self.b, "C": self.c}
        self.pois = [self.a, self.b, self.c]
        self.edges = []
        self.path_cache = {}

    def get_path(self, start_node, end_node, restriction_policy=None):
        if start_node.id == end_node.id:
            return 0.0, [start_node]
        return 100.0, [start_node, end_node]


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


class DriverVehicleAdminApiTest(unittest.TestCase):
    def setUp(self):
        self.previous_manager = persistence._manager
        self.previous_get_station_by_coordinate = persistence.get_station_by_coordinate
        self.previous_state = {
            "city": state.city,
            "fleet": state.fleet,
            "system_initialized": state.system_initialized,
            "city_maps": state.city_maps,
            "operation_area_records": state.operation_area_records,
            "default_operation_area_id": state.default_operation_area_id,
            "default_operation_area_code": state.default_operation_area_code,
            "fleet_by_area": state.fleet_by_area,
        }
        persistence._manager = persistence.MySqlPersistence({"enabled": False, "tenant_id": "test"})
        persistence.save_operation_area({
            "area_id": 10001,
            "code": "test-area",
            "name": "测试运营区",
            "status": "enabled",
            "audit_status": "approved",
            "load_on_startup": 1,
            "shp_path": "fake.shp",
        }, create=True)
        self.city = FakeCity()
        state.city = self.city
        state.fleet = []
        state.city_maps = {10001: self.city}
        state.operation_area_records = {10001: {"area_id": 10001, "code": "test-area", "name": "测试运营区"}}
        state.default_operation_area_id = None
        state.default_operation_area_code = None
        state.fleet_by_area = {10001: []}
        state.system_initialized = True
        station_records = {
            (round(node.lon, 8), round(node.lat, 8)): {
                "id": index,
                "operation_area_id": 10001,
                "poi_code": node.poi_code,
                "poi_name": node.name,
                "longitude": node.lon,
                "latitude": node.lat,
            }
            for index, node in enumerate(self.city.pois, start=1)
        }
        persistence.get_station_by_coordinate = lambda operation_area_id, lon, lat: (
            station_records.get((round(float(lon), 8), round(float(lat), 8)))
            if int(operation_area_id) == 10001
            else None
        )
        CoreDispatcher.order_pool.clear()
        CoreDispatcher.completed_orders_pool.clear()
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def tearDown(self):
        persistence._manager = self.previous_manager
        persistence.get_station_by_coordinate = self.previous_get_station_by_coordinate
        state.city = self.previous_state["city"]
        state.fleet = self.previous_state["fleet"]
        state.system_initialized = self.previous_state["system_initialized"]
        state.city_maps = self.previous_state["city_maps"]
        state.operation_area_records = self.previous_state["operation_area_records"]
        state.default_operation_area_id = self.previous_state["default_operation_area_id"]
        state.default_operation_area_code = self.previous_state["default_operation_area_code"]
        state.fleet_by_area = self.previous_state["fleet_by_area"]
        CoreDispatcher.order_pool.clear()
        CoreDispatcher.completed_orders_pool.clear()

    def create_driver(self, code="driver-1", no="D001", name="张三"):
        return self.client.post("/admin/drivers", json={
            "driver_code": code,
            "driver_no": no,
            "driver_name": name,
            "phone": "13800000000",
            "employment_status": "active",
            "work_status": "off_duty",
        })

    def create_vehicle(self, code="vehicle-1", plate="粤A00001", status="offline", driver=None, seat_count=10, max_load_count=10):
        payload = {
            "vehicle_code": code,
            "plate_no": plate,
            "vehicle_type": "bus",
            "seat_count": seat_count,
            "max_load_count": max_load_count,
            "operation_status": status,
            "operation_area_id": 10001,
        }
        if driver:
            payload["current_driver_code"] = driver
        return self.client.post("/admin/vehicles", json=payload)

    def activate_vehicle(self, code="vehicle-1", status="operating", lon=113.00002, lat=23.00001):
        return self.client.post(f"/admin/vehicles/{code}/status", json={
            "operation_status": status,
            "operation_area_id": 10001,
            "initial_position": {"lon": lon, "lat": lat},
        })

    def test_operation_area_admin_path_uses_area_id(self):
        response = self.client.get("/admin/operation-areas/10001")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["area"]["area_id"], 10001)
        self.assertEqual(data["area"]["code"], "test-area")

        by_code = self.client.get("/admin/operation-areas/test-area")
        self.assertEqual(by_code.status_code, 400)
        self.assertEqual(by_code.get_json()["error"], "operation_area_id_invalid")

    def test_create_operation_area_runtime_failure_does_not_persist(self):
        payload = {
            "area_id": 10002,
            "org_id": 20002,
            "dept_id": 30002,
            "org_code": "org-2",
            "org_name": "测试机构",
            "name": "失败运营区",
            "code": "failed-area",
            "status": "enabled",
            "audit_status": "approved",
            "city_code": "440100",
            "city_name": "广州",
            "country_code": "440113",
            "country_name": "番禺",
            "shp_path": "missing.shp",
            "load_on_startup": 1,
        }
        with patch("api.routes.CityGraph", side_effect=RuntimeError("load failed")):
            response = self.client.post("/admin/operation-areas", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "operation_area_runtime_load_failed")
        self.assertEqual(response.get_json()["message"], "load failed")
        self.assertIsNone(persistence.get_operation_area_by_area_id(10002))

    def test_vehicle_tick_does_not_force_rest_by_driving_time(self):
        vehicle = Vehicle("vehicle-1", self.city.a.id, "#10b981", zone=1)
        vehicle.max_continuous_driving_seconds = 1
        vehicle.planned_route = [{"type": "O", "order": make_order(self.city)}]

        vehicle.tick(10)

        self.assertGreater(vehicle.driving_time, vehicle.max_continuous_driving_seconds)
        self.assertEqual(vehicle.rest_status, "operating")
        self.assertFalse(vehicle.is_rest_requested)
        self.assertFalse(vehicle.is_resting)

    def test_vehicle_acceptance_uses_operation_status_only(self):
        vehicle = Vehicle("vehicle-1", self.city.a.id, "#10b981", zone=1)
        vehicle.operation_status = "operating"
        vehicle.rest_status = "resting"
        vehicle.is_rest_requested = True
        vehicle.is_resting = True

        self.assertTrue(CoreDispatcher._vehicle_can_accept_order(vehicle))

    def test_vehicle_closing_status_blocks_order_even_if_rest_fields_stale(self):
        vehicle = Vehicle("vehicle-1", self.city.a.id, "#10b981", zone=1)
        vehicle.operation_status = "closing"
        vehicle.rest_status = "operating"
        vehicle.is_rest_requested = False
        vehicle.is_resting = False

        self.assertFalse(CoreDispatcher._vehicle_can_accept_order(vehicle))

    def test_rest_endpoint_accepts_platform_source(self):
        self.create_driver()
        self.create_vehicle(driver="driver-1")
        self.activate_vehicle()

        response = self.client.post("/fleet/vehicle-1/rest", json={
            "source": "platform",
            "rest_duration_minutes": 20,
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["source"], "platform")
        self.assertIn(data["rest_status"], {"closing", "resting"})
        self.assertFalse(CoreDispatcher._vehicle_can_accept_order(state.fleet[0]))

    def test_delete_operation_area_blocks_pooled_order(self):
        order = make_order(self.city, request_id="pooled-order")
        order.operation_area_id = 10001
        order.status = "pooled"
        CoreDispatcher.order_pool.append(order)

        response = self.client.delete("/admin/operation-areas/10001")

        self.assertEqual(response.status_code, 409)
        data = response.get_json()
        self.assertEqual(data["error"], "operation_area_has_unfinished_orders")
        self.assertEqual(data["blockers"]["pooled_orders"][0]["request_id"], "pooled-order")
        self.assertIsNotNone(persistence.get_operation_area_by_area_id(10001))

    def test_delete_operation_area_blocks_runtime_vehicle_task(self):
        self.create_vehicle()
        self.activate_vehicle()
        state.fleet[0].planned_route = [{"type": "O", "order": make_order(self.city, request_id="assigned-order")}]

        response = self.client.delete("/admin/operation-areas/10001")

        self.assertEqual(response.status_code, 409)
        data = response.get_json()
        self.assertEqual(data["error"], "operation_area_has_unfinished_orders")
        self.assertEqual(data["blockers"]["vehicles"][0]["vehicle_id"], "vehicle-1")
        self.assertIsNotNone(persistence.get_operation_area_by_area_id(10001))

    def test_delete_operation_area_resets_area_vehicles_when_idle(self):
        self.create_vehicle()

        response = self.client.delete("/admin/operation-areas/10001")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "deleted")
        self.assertEqual(data["reset_vehicle_codes"], ["vehicle-1"])
        self.assertIsNone(persistence.get_operation_area_by_area_id(10001))
        vehicle = persistence.get_vehicle("vehicle-1")
        self.assertEqual(vehicle["operation_status"], "offline")
        self.assertIsNone(vehicle["operation_area_id"])
        self.assertNotIn(10001, state.city_maps)
        self.assertNotIn(10001, state.fleet_by_area)

    def test_options_returns_form_enums_and_current_records(self):
        self.create_driver()
        self.create_vehicle(status="offline")

        response = self.client.get("/admin/driver-vehicle/options")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("operating", data["vehicle_operation_statuses"])
        self.assertIn("off_duty", data["driver_work_statuses"])
        self.assertEqual(len(data["drivers"]), 1)
        self.assertEqual(len(data["vehicles"]), 1)

    def test_order_query_returns_503_when_database_disabled(self):
        response = self.client.post("/admin/orders/query", json={})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "database_unavailable")

    def test_create_order_requires_passenger_phone(self):
        now = datetime.now().replace(microsecond=0)
        response = self.client.post("/order", json={
            "request_id": "order-without-phone",
            "origin": {"lon": self.city.b.lon, "lat": self.city.b.lat},
            "destination": {"lon": self.city.c.lon, "lat": self.city.c.lat},
            "expected_pickup_time": {
                "earliest": now.isoformat(sep=" "),
                "latest": (now + timedelta(minutes=20)).isoformat(sep=" "),
            },
            "operation_area_id": 10001,
            "passenger_count": 1,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("passenger_phone", response.get_json()["error"])

    def test_create_order_returns_passenger_identity_fields(self):
        now = datetime.now().replace(microsecond=0)
        response = self.client.post("/order", json={
            "request_id": "order-with-phone",
            "origin": {"lon": self.city.b.lon, "lat": self.city.b.lat},
            "destination": {"lon": self.city.c.lon, "lat": self.city.c.lat},
            "expected_pickup_time": {
                "earliest": now.isoformat(sep=" "),
                "latest": (now + timedelta(minutes=20)).isoformat(sep=" "),
            },
            "operation_area_id": 10001,
            "passenger_count": 1,
            "passenger_phone": "13900000001",
            "passenger_id": "passenger-business-1",
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["passenger_phone"], "13900000001")
        self.assertEqual(data["passenger_id"], "passenger-business-1")

    def test_create_order_rejects_coordinate_not_in_station_table(self):
        now = datetime.now().replace(microsecond=0)
        response = self.client.post("/order", json={
            "request_id": "order-invalid-origin",
            "origin": {"lon": 113.0015, "lat": 23.0015},
            "destination": {"lon": self.city.c.lon, "lat": self.city.c.lat},
            "expected_pickup_time": {
                "earliest": now.isoformat(sep=" "),
                "latest": (now + timedelta(minutes=20)).isoformat(sep=" "),
            },
            "operation_area_id": 10001,
            "passenger_count": 1,
            "passenger_phone": "13900000001",
        })

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["code"], "origin_station_not_found_by_coordinate")

    def test_create_order_rejects_same_origin_and_destination(self):
        now = datetime.now().replace(microsecond=0)
        response = self.client.post("/order", json={
            "request_id": "order-same-station",
            "origin": {"lon": self.city.b.lon, "lat": self.city.b.lat},
            "destination": {"lon": self.city.b.lon, "lat": self.city.b.lat},
            "expected_pickup_time": {
                "earliest": now.isoformat(sep=" "),
                "latest": (now + timedelta(minutes=20)).isoformat(sep=" "),
            },
            "operation_area_id": 10001,
            "passenger_count": 1,
            "passenger_phone": "13900000001",
        })

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "same_origin_destination")

    def test_batch_create_order_allows_partial_success(self):
        now = datetime.now().replace(microsecond=0)
        response = self.client.post("/order", json={
            "orders": [
                {
                    "request_id": "batch-order-ok",
                    "origin": {"lon": self.city.b.lon, "lat": self.city.b.lat},
                    "destination": {"lon": self.city.c.lon, "lat": self.city.c.lat},
                    "expected_pickup_time": {
                        "earliest": now.isoformat(sep=" "),
                        "latest": (now + timedelta(minutes=20)).isoformat(sep=" "),
                    },
                    "operation_area_id": 10001,
                    "passenger_count": 1,
                    "passenger_phone": "13900000001",
                },
                {
                    "request_id": "batch-order-bad",
                    "origin": {"lon": self.city.b.lon, "lat": self.city.b.lat},
                    "destination": {"lon": self.city.b.lon, "lat": self.city.b.lat},
                    "expected_pickup_time": {
                        "earliest": now.isoformat(sep=" "),
                        "latest": (now + timedelta(minutes=20)).isoformat(sep=" "),
                    },
                    "operation_area_id": 10001,
                    "passenger_count": 1,
                    "passenger_phone": "13900000002",
                },
            ],
        })

        self.assertEqual(response.status_code, 207)
        data = response.get_json()
        self.assertEqual(data["success_count"], 1)
        self.assertEqual(data["failure_count"], 1)
        self.assertEqual(data["pool_size"], 1)
        self.assertEqual(CoreDispatcher.order_pool[0].request_id, "batch-order-ok")
        self.assertEqual(data["results"][1]["code"], "same_origin_destination")

    def test_batch_cancel_vehicle_orders_refreshes_route_once(self):
        vehicle = Vehicle("vehicle-1", self.city.a.id, "#10b981", zone=1)
        vehicle.vehicle_id = "vehicle-1"
        vehicle.operation_area_id = 10001
        order_a = make_order(self.city, request_id="cancel-a")
        order_b = make_order(self.city, request_id="cancel-b")
        vehicle.planned_route = [
            {"type": "O", "order": order_a},
            {"type": "O", "order": order_b},
            {"type": "D", "order": order_a},
            {"type": "D", "order": order_b},
        ]
        state.fleet.append(vehicle)
        state.fleet_by_area[10001].append(vehicle)

        with patch("api.core.CoreDispatcher.refresh_vehicle_route_metadata", return_value={"path": [], "segments": []}) as refreshed:
            response = self.client.post("/orders/batch/cancel", json={
                "request_ids": ["cancel-a", "cancel-b"],
            })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["success_count"], 2)
        self.assertEqual(len(data["affected_vehicles"]), 1)
        self.assertEqual(refreshed.call_count, 1)
        self.assertEqual(vehicle.planned_route, [])

    def test_driver_crud_duplicate_no_and_bound_delete_conflict(self):
        created = self.create_driver()
        self.assertEqual(created.status_code, 201)

        duplicated_no = self.create_driver(code="driver-2", no="D001")
        self.assertEqual(duplicated_no.status_code, 409)
        self.assertEqual(duplicated_no.get_json()["error"], "driver_no_exists")

        updated = self.client.put("/admin/drivers/driver-1", json={
            "driver_code": "ignored",
            "driver_no": "D009",
            "driver_name": "李四",
            "employment_status": "active",
            "work_status": "serving",
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["driver"]["driver_no"], "D009")

        vehicle = self.create_vehicle(driver="driver-1")
        self.assertEqual(vehicle.status_code, 201)

        deleted = self.client.delete("/admin/drivers/driver-1")
        self.assertEqual(deleted.status_code, 409)
        self.assertEqual(deleted.get_json()["error"], "driver_bound")

    def test_vehicle_create_offline_then_activate_with_position_snap(self):
        created = self.create_vehicle()

        self.assertEqual(created.status_code, 201)
        data = created.get_json()
        self.assertEqual(data["vehicle"]["operation_status"], "offline")
        self.assertIsNone(data["snap"])
        self.assertEqual(len(state.fleet), 0)

        activated = self.activate_vehicle()
        self.assertEqual(activated.status_code, 200)
        active_data = activated.get_json()
        self.assertEqual(active_data["snap"]["node"]["id"], "A")
        self.assertGreaterEqual(active_data["snap"]["snap_distance_m"], 0.0)
        self.assertEqual(len(state.fleet), 1)
        self.assertEqual(state.fleet[0].driver_id, "")
        self.assertEqual(state.fleet[0].vehicle_id, "vehicle-1")
        self.assertTrue(CoreDispatcher._vehicle_can_accept_order(state.fleet[0]))

        duplicated_plate = self.create_vehicle(code="vehicle-2", plate="粤A00001")
        self.assertEqual(duplicated_plate.status_code, 409)
        self.assertEqual(duplicated_plate.get_json()["error"], "plate_no_exists")

        invalid_create_status = self.create_vehicle(code="vehicle-3", plate="粤A00003", status="operating")
        self.assertEqual(invalid_create_status.status_code, 400)

        deprecated_area_code = self.client.post("/admin/vehicles", json={
            "vehicle_code": "vehicle-area-code",
            "plate_no": "粤A00007",
            "vehicle_type": "bus",
            "seat_count": 10,
            "max_load_count": 10,
            "operation_status": "offline",
            "operation_area_code": "test-area",
        })
        self.assertEqual(deprecated_area_code.status_code, 400)
        self.assertIn("operation_area_id", deprecated_area_code.get_json()["error"])

        missing_seat_count = self.client.post("/admin/vehicles", json={
            "vehicle_code": "vehicle-4",
            "plate_no": "粤A00004",
            "operation_status": "offline",
            "max_load_count": 10,
        })
        self.assertEqual(missing_seat_count.status_code, 400)

        position_on_create = self.client.post("/admin/vehicles", json={
            "vehicle_code": "vehicle-5",
            "plate_no": "粤A00005",
            "operation_status": "offline",
            "seat_count": 10,
            "max_load_count": 10,
            "initial_position": {"lon": 113.00002, "lat": 23.00001},
        })
        self.assertEqual(position_on_create.status_code, 400)

        self.create_vehicle(code="vehicle-6", plate="粤A00006")
        invalid_position = self.client.post("/admin/vehicles/vehicle-6/status", json={
            "operation_status": "operating",
            "operation_area_id": 10001,
            "initial_position": {"lon": 181, "lat": 23},
        })
        self.assertEqual(invalid_position.status_code, 400)

    def test_vehicle_update_reuses_commute_assignment_when_mode_is_commute(self):
        self.create_vehicle()
        persistence.save_commute_line({
            "line_code": "line-admin-1",
            "line_name": "管理接口快线",
            "operation_area_id": 10001,
            "status": "enabled",
        }, create=True)

        missing_line = self.client.put("/admin/vehicles/vehicle-1", json={
            "plate_no": "粤A00001",
            "vehicle_type": "bus",
            "seat_count": 10,
            "max_load_count": 10,
            "operation_status": "offline",
            "operation_mode": "commute_fixed_waiting",
            "operation_area_id": 10001,
        })
        self.assertEqual(missing_line.status_code, 400)
        self.assertIn("line_code", missing_line.get_json()["error"])

        bound = self.client.put("/admin/vehicles/vehicle-1", json={
            "plate_no": "粤A00001",
            "vehicle_type": "bus",
            "seat_count": 10,
            "max_load_count": 10,
            "operation_status": "offline",
            "operation_mode": "commute_fixed_waiting",
            "line_code": "line-admin-1",
            "operation_area_id": 99999,
        })
        self.assertEqual(bound.status_code, 200)
        bound_data = bound.get_json()
        self.assertEqual(bound_data["vehicle"]["operation_mode"], "commute_fixed_waiting")
        self.assertEqual(bound_data["vehicle"]["operation_area_id"], 10001)
        self.assertEqual(bound_data["commute_assignment"]["line_code"], "line-admin-1")
        self.assertEqual(bound_data["commute_assignment"]["task_mode"], "commute_fixed_waiting")
        self.assertEqual(persistence.get_commute_vehicle_assignment("vehicle-1")["status"], "active")

        dynamic = self.client.put("/admin/vehicles/vehicle-1", json={
            "plate_no": "粤A00001",
            "vehicle_type": "bus",
            "seat_count": 10,
            "max_load_count": 10,
            "operation_status": "offline",
            "operation_mode": "dynamic_bus",
            "operation_area_id": 10001,
        })
        self.assertEqual(dynamic.status_code, 200)
        self.assertEqual(dynamic.get_json()["vehicle"]["operation_mode"], "dynamic_bus")
        self.assertEqual(persistence.get_commute_vehicle_assignment("vehicle-1")["status"], "disabled")

    def test_fleet_detail_query_uses_vehicle_id_not_internal_id(self):
        vehicle = Vehicle("internal-display-id", self.city.a.id, "#10b981", zone=1)
        vehicle.vehicle_id = "vehicle-business-id"
        vehicle.plate_no = "粤A00999"
        state.fleet = [vehicle]

        by_vehicle_id = self.client.get("/fleet/vehicle-business-id")
        by_internal_id = self.client.get("/fleet/internal-display-id")

        self.assertEqual(by_vehicle_id.status_code, 200)
        self.assertEqual(by_vehicle_id.get_json()["vehicle_id"], "vehicle-business-id")
        self.assertEqual(by_internal_id.status_code, 404)

    def test_vehicle_status_controls_runtime_acceptance_and_removal(self):
        self.create_driver()
        self.create_vehicle(driver="driver-1")
        self.activate_vehicle()

        resting = self.client.post("/admin/vehicles/vehicle-1/status", json={"operation_status": "resting"})
        self.assertEqual(resting.status_code, 200)
        vehicle = state.fleet[0]
        self.assertEqual(vehicle.rest_status, "resting")
        self.assertFalse(CoreDispatcher._vehicle_can_accept_order(vehicle))

        closing = self.client.post("/admin/vehicles/vehicle-1/status", json={"operation_status": "closing"})
        self.assertEqual(closing.status_code, 200)
        self.assertEqual(vehicle.rest_status, "closing")
        self.assertFalse(CoreDispatcher._vehicle_can_accept_order(vehicle))

        offline = self.client.post("/admin/vehicles/vehicle-1/status", json={"operation_status": "offline"})
        self.assertEqual(offline.status_code, 200)
        self.assertEqual(state.fleet, [])

    def test_vehicle_offline_and_delete_conflict_when_vehicle_has_tasks(self):
        self.create_driver()
        self.create_vehicle(driver="driver-1")
        self.activate_vehicle()
        vehicle = state.fleet[0]
        vehicle.planned_route = [{"type": "O", "order": make_order(self.city)}]

        offline = self.client.post("/admin/vehicles/vehicle-1/status", json={"operation_status": "offline"})
        self.assertEqual(offline.status_code, 409)
        self.assertEqual(offline.get_json()["error"], "vehicle_has_tasks")

        deleted = self.client.delete("/admin/vehicles/vehicle-1")
        self.assertEqual(deleted.status_code, 409)
        self.assertEqual(deleted.get_json()["error"], "vehicle_has_tasks")

    def test_bind_driver_and_missing_driver(self):
        self.create_driver()
        self.create_vehicle(status="offline")
        self.create_vehicle(code="vehicle-2", plate="粤A00002", status="offline")

        missing = self.client.post("/admin/vehicles/vehicle-1/bind-driver", json={"driver_code": "missing"})
        self.assertEqual(missing.status_code, 404)

        bound = self.client.post("/admin/vehicles/vehicle-1/bind-driver", json={"driver_code": "driver-1"})
        self.assertEqual(bound.status_code, 200)
        self.assertEqual(bound.get_json()["vehicle"]["current_driver_code"], "driver-1")

        duplicate_bound = self.client.post("/admin/vehicles/vehicle-2/bind-driver", json={"driver_code": "driver-1"})
        self.assertEqual(duplicate_bound.status_code, 409)
        self.assertEqual(duplicate_bound.get_json()["error"], "driver_already_bound")

        activated = self.activate_vehicle()
        self.assertEqual(activated.status_code, 200)

        unbind_operating = self.client.post("/admin/vehicles/vehicle-1/bind-driver", json={"driver_code": None})
        self.assertEqual(unbind_operating.status_code, 200)
        self.assertIsNone(unbind_operating.get_json()["vehicle"]["current_driver_code"])


class DriverVehicleStateLoadTest(unittest.TestCase):
    def setUp(self):
        self.previous_manager = persistence._manager
        persistence._manager = persistence.MySqlPersistence({"enabled": False, "tenant_id": "test"})
        self.city = FakeCity()

    def tearDown(self):
        persistence._manager = self.previous_manager

    def test_load_fleet_from_persistence_uses_operating_database_vehicles(self):
        persistence.save_driver({
            "driver_code": "driver-db-1",
            "driver_no": "DB001",
            "driver_name": "数据库司机1",
        }, create=True)
        persistence.save_vehicle({
            "vehicle_code": "db-bus-1",
            "plate_no": "粤B00001",
            "operation_status": "operating",
            "current_driver_code": "driver-db-1",
            "current_lon": 113.00001,
            "current_lat": 23.00001,
            "last_node_code": "A",
            "next_node_code": "A",
            "edge_progress": 0.0,
        }, create=True)
        persistence.save_vehicle({
            "vehicle_code": "db-bus-2",
            "plate_no": "粤B00002",
            "operation_status": "maintenance",
            "current_lon": 113.001,
            "current_lat": 23.000,
        }, create=True)

        fleet = state.load_fleet_from_persistence(self.city, datetime.now().timestamp())

        self.assertEqual([vehicle.vehicle_id for vehicle in fleet], ["db-bus-1"])

    def test_load_fleet_skips_vehicle_when_runtime_position_is_missing(self):
        persistence.save_driver({
            "driver_code": "driver-db-random",
            "driver_no": "DB099",
            "driver_name": "随机司机",
        }, create=True)
        persistence.save_vehicle({
            "vehicle_code": "db-bus-random",
            "plate_no": "粤B00999",
            "operation_status": "operating",
            "current_driver_code": "driver-db-random",
        }, create=True)

        fleet = state.load_fleet_from_persistence(self.city, datetime.now().timestamp())

        self.assertEqual(fleet, [])


if __name__ == "__main__":
    unittest.main()
