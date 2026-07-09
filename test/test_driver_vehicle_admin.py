# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timedelta

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
        self.previous_state = {
            "city": state.city,
            "fleet": state.fleet,
            "system_initialized": state.system_initialized,
        }
        persistence._manager = persistence.MySqlPersistence({"enabled": False, "tenant_id": "test"})
        self.city = FakeCity()
        state.city = self.city
        state.fleet = []
        state.system_initialized = True
        CoreDispatcher.order_pool.clear()
        CoreDispatcher.completed_orders_pool.clear()
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def tearDown(self):
        persistence._manager = self.previous_manager
        state.city = self.previous_state["city"]
        state.fleet = self.previous_state["fleet"]
        state.system_initialized = self.previous_state["system_initialized"]
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
        }
        if driver:
            payload["current_driver_code"] = driver
        return self.client.post("/admin/vehicles", json=payload)

    def activate_vehicle(self, code="vehicle-1", status="operating", lon=113.00002, lat=23.00001):
        return self.client.post(f"/admin/vehicles/{code}/status", json={
            "operation_status": status,
            "initial_position": {"lon": lon, "lat": lat},
        })

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
            "passenger_count": 1,
            "passenger_phone": "13900000001",
            "passenger_id": "passenger-business-1",
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["passenger_phone"], "13900000001")
        self.assertEqual(data["passenger_id"], "passenger-business-1")

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

        unbound_activation = self.activate_vehicle()
        self.assertEqual(unbound_activation.status_code, 409)
        self.assertEqual(unbound_activation.get_json()["error"], "driver_required")

        self.create_driver()
        bound = self.client.post("/admin/vehicles/vehicle-1/bind-driver", json={"driver_code": "driver-1"})
        self.assertEqual(bound.status_code, 200)

        activated = self.activate_vehicle()
        self.assertEqual(activated.status_code, 200)
        active_data = activated.get_json()
        self.assertEqual(active_data["snap"]["node"]["id"], "A")
        self.assertGreaterEqual(active_data["snap"]["snap_distance_m"], 0.0)
        self.assertEqual(len(state.fleet), 1)
        self.assertEqual(state.fleet[0].vehicle_id, "vehicle-1")
        self.assertTrue(CoreDispatcher._vehicle_can_accept_order(state.fleet[0]))

        duplicated_plate = self.create_vehicle(code="vehicle-2", plate="粤A00001")
        self.assertEqual(duplicated_plate.status_code, 409)
        self.assertEqual(duplicated_plate.get_json()["error"], "plate_no_exists")

        invalid_create_status = self.create_vehicle(code="vehicle-3", plate="粤A00003", status="operating")
        self.assertEqual(invalid_create_status.status_code, 400)

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
            "initial_position": {"lon": 181, "lat": 23},
        })
        self.assertEqual(invalid_position.status_code, 400)

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
        self.assertEqual(unbind_operating.status_code, 409)
        self.assertEqual(unbind_operating.get_json()["error"], "driver_required")


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

    def test_load_fleet_assigns_random_poi_when_runtime_position_is_missing(self):
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

        self.assertEqual(len(fleet), 1)
        self.assertEqual(fleet[0].vehicle_id, "db-bus-random")
        self.assertIn(fleet[0].last_node, {poi.id for poi in self.city.pois})
        self.assertIsNotNone(fleet[0].gps["lon"])
        self.assertIsNotNone(fleet[0].gps["lat"])


if __name__ == "__main__":
    unittest.main()
