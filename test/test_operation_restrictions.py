# -*- coding: utf-8 -*-
import json
import unittest
from urllib.parse import parse_qs, urlparse

from flask import Flask

from api import persistence
from api.core import CoreDispatcher
from api.models import CityGraph, Node
from api.restrictions import OperationRestrictionError, normalize_policy_payload
from api.routes import bp
from forecast.amap_driving_route_planner import AmapDrivingRoutePlanner


def rectangle(lon1, lat1, lon2, lat2):
    return [
        {"lon": lon1, "lat": lat1},
        {"lon": lon2, "lat": lat1},
        {"lon": lon2, "lat": lat2},
        {"lon": lon1, "lat": lat2},
    ]


def policy_payload(code="p1", name=None, polygons=None, operation_area_id=1001):
    return {
        "operation_area_id": operation_area_id,
        "policy_code": code,
        "policy_name": name or code,
        "polygons": polygons or [rectangle(113.004, 22.9999, 113.006, 23.0001)],
    }


class OperationRestrictionValidationTest(unittest.TestCase):
    def test_valid_multi_polygon_policy_is_serialized_for_amap(self):
        policy = normalize_policy_payload({
            "policy_code": "campus",
            "policy_name": "Campus",
            "polygons": [
                rectangle(113.004, 22.9999, 113.006, 23.0001),
                rectangle(113.014, 23.0099, 113.016, 23.0101),
            ],
        })

        self.assertEqual(policy["polygon_count"], 2)
        self.assertEqual(policy["vertex_count"], 8)
        self.assertIn("|", policy["amap_avoidpolygons"])
        self.assertIn("policy_signature", policy)

    def test_duplicate_closing_point_is_removed(self):
        pts = rectangle(113.004, 22.9999, 113.006, 23.0001)
        policy = normalize_policy_payload(policy_payload(polygons=[pts + [pts[0]]]))
        self.assertEqual(len(policy["polygons"][0]["points"]), 4)

    def test_rejects_too_many_polygons(self):
        with self.assertRaises(OperationRestrictionError):
            normalize_policy_payload(policy_payload(polygons=[rectangle(113, 23, 113.001, 23.001)] * 33))

    def test_rejects_too_many_vertices(self):
        points = []
        for index in range(17):
            points.append({
                "lon": 113.0 + 0.001 * index,
                "lat": 23.0 + (0.001 if index % 2 else 0.0),
            })
        with self.assertRaises(OperationRestrictionError):
            normalize_policy_payload(policy_payload(polygons=[points]))

    def test_rejects_large_area(self):
        with self.assertRaises(OperationRestrictionError):
            normalize_policy_payload(policy_payload(polygons=[rectangle(113.0, 23.0, 113.1, 23.1)]))

    def test_rejects_self_intersection(self):
        with self.assertRaises(OperationRestrictionError):
            normalize_policy_payload(policy_payload(polygons=[[
                {"lon": 113.0, "lat": 23.0},
                {"lon": 113.01, "lat": 23.01},
                {"lon": 113.0, "lat": 23.01},
                {"lon": 113.01, "lat": 23.0},
            ]]))

    def test_rejects_invalid_coordinate(self):
        with self.assertRaises(OperationRestrictionError):
            normalize_policy_payload(policy_payload(polygons=[[
                {"lon": 181.0, "lat": 23.0},
                {"lon": 113.01, "lat": 23.0},
                {"lon": 113.01, "lat": 23.01},
            ]]))


class OperationRestrictionAStarTest(unittest.TestCase):
    def make_graph(self):
        graph = CityGraph.__new__(CityGraph)
        graph.path_cache = {}
        graph.edges = []
        graph.pois = []
        a = Node("A", 113.000, 23.000)
        b = Node("B", 113.010, 23.000)
        c = Node("C", 113.000, 23.010)
        d = Node("D", 113.010, 23.010)
        a.neighbors = {"B": 1.0, "C": 1.0}
        c.neighbors = {"D": 1.0}
        d.neighbors = {"B": 1.0}
        b.neighbors = {}
        graph.nodes_map = {"A": a, "B": b, "C": c, "D": d}
        return graph, a, b, c, d

    def test_restriction_blocks_direct_edge_and_cache_is_policy_scoped(self):
        graph, a, b, _, _ = self.make_graph()
        direct_dist, direct_path = graph.get_path(a, b)
        self.assertEqual(direct_dist, 1.0)
        self.assertEqual([node.id for node in direct_path], ["A", "B"])

        policy = normalize_policy_payload(policy_payload())
        restricted_dist, restricted_path = graph.get_path(a, b, restriction_policy=policy)

        self.assertEqual(restricted_dist, 3.0)
        self.assertEqual([node.id for node in restricted_path], ["A", "C", "D", "B"])

    def test_restriction_can_make_route_unreachable(self):
        graph, a, b, _, _ = self.make_graph()
        policy = normalize_policy_payload(policy_payload(polygons=[
            rectangle(112.9999, 22.9999, 113.0001, 23.0001),
        ]))
        dist, path = graph.get_path(a, b, restriction_policy=policy)
        self.assertEqual(dist, float("inf"))
        self.assertEqual(path, [])

    def test_largest_component_prunes_stale_neighbor_references(self):
        graph = CityGraph.__new__(CityGraph)
        orphan = Node("orphan", 113.300000, 23.100000)
        a = Node("A", 113.000000, 23.000000)
        b = Node("B", 113.001000, 23.000000)
        c = Node("C", 113.002000, 23.000000)

        orphan.neighbors = {}
        a.neighbors = {"B": 1.0, "orphan": 1.0}
        b.neighbors = {"A": 1.0, "C": 1.0}
        c.neighbors = {"B": 1.0}
        graph.nodes_map = {
            "orphan": orphan,
            "A": a,
            "B": b,
            "C": c,
        }
        graph.edges = [
            {"u": "A", "v": "B", "dist": 1.0},
            {"u": "B", "v": "A", "dist": 1.0},
            {"u": "B", "v": "C", "dist": 1.0},
            {"u": "C", "v": "B", "dist": 1.0},
            {"u": "A", "v": "orphan", "dist": 1.0},
        ]

        graph._keep_largest_connected_component()

        self.assertNotIn("orphan", graph.nodes_map)
        self.assertNotIn("orphan", graph.nodes_map["A"].neighbors)
        self.assertTrue(all(edge["u"] != "orphan" and edge["v"] != "orphan" for edge in graph.edges))


class FakePlanner(AmapDrivingRoutePlanner):
    def __init__(self):
        super().__init__(
            api_key="test-key",
            timeout_sec=1,
            request_interval_ms=0,
            qps_retry_delays_ms=[],
        )
        self.requests = []

    def _urlopen_json(self, req):
        self.requests.append(req)
        return {
            "status": "1",
            "route": {
                "paths": [{
                    "distance": "100",
                    "cost": {"duration": "10"},
                    "steps": [{"polyline": "113,23;113.01,23.01", "tmcs": []}],
                }]
            },
        }


class AmapDrivingRestrictionTest(unittest.TestCase):
    def points(self):
        return [{"lon": 113.0, "lat": 23.0}, {"lon": 113.01, "lat": 23.01}]

    def test_avoidpolygons_enters_request_params_and_cache_key(self):
        planner = FakePlanner()
        policy = normalize_policy_payload(policy_payload())

        first = planner.plan_segment_sync(self.points(), restriction_policy=policy)
        second = planner.plan_segment_sync(self.points(), restriction_policy=policy)

        self.assertTrue(first["ok"])
        self.assertTrue(second["cached"])
        self.assertEqual(len(planner.requests), 1)
        query = parse_qs(urlparse(planner.requests[0].full_url).query)
        self.assertEqual(query["avoidpolygons"][0], policy["amap_avoidpolygons"])

        other = normalize_policy_payload(policy_payload(code="p2", polygons=[
            rectangle(113.02, 23.02, 113.021, 23.021),
        ]))
        planner.plan_segment_sync(self.points(), restriction_policy=other)
        self.assertEqual(len(planner.requests), 2)

    def test_long_avoidpolygons_uses_post(self):
        planner = FakePlanner()
        huge_policy = {
            "policy_code": "huge",
            "amap_avoidpolygons": ";".join(["113,23"] * 500),
            "policy_signature": "huge:test",
        }
        planner.plan_segment_sync(self.points(), restriction_policy=huge_policy)
        req = planner.requests[0]
        self.assertIsNotNone(req.data)
        body = parse_qs(req.data.decode("utf-8"))
        self.assertIn("avoidpolygons", body)


class OperationRestrictionApiTest(unittest.TestCase):
    def setUp(self):
        self.previous_manager = persistence._manager
        persistence._manager = persistence.MySqlPersistence({"enabled": False, "tenant_id": "test"})
        CoreDispatcher.set_operation_restriction_policy(None)
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def tearDown(self):
        persistence._manager = self.previous_manager
        CoreDispatcher.set_operation_restriction_policy(None)

    def test_crud_and_active_policy(self):
        payload = policy_payload(code="api-policy")
        created = self.client.post("/operation-restrictions/policies", json=payload)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["policy"]["policy_code"], "api-policy")

        listed = self.client.get("/operation-restrictions/policies")
        self.assertEqual(len(listed.get_json()["policies"]), 1)

        active = self.client.post("/operation-restrictions/active", json={
            "operation_area_id": 1001,
            "policy_code": "api-policy",
        })
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.get_json()["policy"]["policy_code"], "api-policy")
        self.assertEqual(
            CoreDispatcher.current_operation_restriction_policy(1001)["policy_code"],
            "api-policy",
        )

        deleted = self.client.delete("/operation-restrictions/policies/api-policy")
        self.assertEqual(deleted.status_code, 200)
        self.assertIsNone(CoreDispatcher.current_operation_restriction_policy(1001))

    def test_duplicate_code_is_allowed_but_duplicate_name_is_rejected(self):
        first = self.client.post(
            "/operation-restrictions/policies",
            json=policy_payload(code="same-code", name="策略一"),
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/operation-restrictions/policies",
            json=policy_payload(code="same-code", name="策略二"),
        )
        self.assertEqual(second.status_code, 201)

        duplicated_name = self.client.post(
            "/operation-restrictions/policies",
            json=policy_payload(code="another-code", name="策略一"),
        )
        self.assertEqual(duplicated_name.status_code, 400)
        self.assertEqual(duplicated_name.get_json()["error"], "policy_name_exists")

        listed = self.client.get("/operation-restrictions/policies")
        self.assertEqual(len(listed.get_json()["policies"]), 2)

    def test_active_policy_is_isolated_by_operation_area(self):
        first = self.client.post(
            "/operation-restrictions/policies",
            json=policy_payload(code="area-a", name="区域A禁区", operation_area_id=1001),
        )
        second = self.client.post(
            "/operation-restrictions/policies",
            json=policy_payload(code="area-b", name="区域B禁区", operation_area_id=2002),
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        active_a = self.client.post("/operation-restrictions/active", json={
            "operation_area_id": 1001,
            "policy_name": "区域A禁区",
        })
        active_b = self.client.post("/operation-restrictions/active", json={
            "operation_area_id": 2002,
            "policy_name": "区域B禁区",
        })

        self.assertEqual(active_a.status_code, 200)
        self.assertEqual(active_b.status_code, 200)
        self.assertEqual(CoreDispatcher.current_operation_restriction_policy(1001)["policy_code"], "area-a")
        self.assertEqual(CoreDispatcher.current_operation_restriction_policy(2002)["policy_code"], "area-b")

    def test_invalid_policy_returns_400(self):
        response = self.client.post("/operation-restrictions/policies", json={
            "policy_code": "invalid",
            "policy_name": "Invalid",
            "polygons": [],
        })
        self.assertEqual(response.status_code, 400)

    def test_create_policy_requires_operation_area_id(self):
        payload = policy_payload(code="missing-area")
        payload.pop("operation_area_id", None)
        response = self.client.post("/operation-restrictions/policies", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "operation_area_id_required")


if __name__ == "__main__":
    unittest.main()
