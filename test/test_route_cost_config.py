# -*- coding: utf-8 -*-
"""调度成本参数按运营区隔离接口测试。"""

import unittest
from unittest import mock

from flask import Flask

from api.core import CoreDispatcher
from api.routes import bp


class RouteCostConfigApiTest(unittest.TestCase):
    """验证成本配置接口必须按运营区查询和更新。"""

    def setUp(self):
        CoreDispatcher.clear_route_cost_config()
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()
        self.area_lookup = mock.patch(
            "api.routes.persistence.get_operation_area_by_area_id",
            side_effect=lambda area_id: {"area_id": int(area_id)} if int(area_id) in {19, 25} else None,
        )
        self.area_lookup.start()

    def tearDown(self):
        self.area_lookup.stop()
        CoreDispatcher.clear_route_cost_config()

    def test_operation_area_id_is_required(self):
        response = self.client.get("/admin/dispatch/route-cost-config")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "operation_area_id_required")

    def test_invalid_and_unknown_operation_area_are_rejected(self):
        invalid = self.client.get(
            "/admin/dispatch/route-cost-config?operation_area_id=invalid"
        )
        missing = self.client.get(
            "/admin/dispatch/route-cost-config?operation_area_id=99"
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["error"], "operation_area_id_invalid")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.get_json()["error"], "operation_area_not_found")

    def test_updates_are_isolated_by_operation_area(self):
        response = self.client.put(
            "/admin/dispatch/route-cost-config",
            json={
                "operation_area_id": 19,
                "WAIT_COST_PER_MIN": 12,
                "PLANNED_ROUTE_INSERTION_PENALTY": 35,
            },
        )
        area_25_response = self.client.get(
            "/admin/dispatch/route-cost-config?operation_area_id=25"
        )

        self.assertEqual(response.status_code, 200)
        area_19 = response.get_json()
        area_25 = area_25_response.get_json()
        self.assertEqual(area_19["operation_area_id"], 19)
        self.assertEqual(area_19["config"]["WAIT_COST_PER_MIN"], 12.0)
        self.assertEqual(area_19["config"]["PLANNED_ROUTE_INSERTION_PENALTY"], 35.0)
        self.assertEqual(area_25["operation_area_id"], 25)
        self.assertEqual(
            area_25["config"]["WAIT_COST_PER_MIN"],
            CoreDispatcher.ROUTE_COST_CONFIG_DEFAULTS["WAIT_COST_PER_MIN"],
        )

    def test_code_defaults_are_merged_per_operation_area(self):
        with mock.patch.object(
            CoreDispatcher,
            "ROUTE_COST_CONFIG_BY_AREA_DEFAULTS",
            {
                19: {
                    "WAIT_COST_PER_MIN": 9.0,
                    "IN_CAR_COST_PER_MIN": 11.0,
                }
            },
        ):
            CoreDispatcher.clear_route_cost_config()
            area_19_response = self.client.get(
                "/admin/dispatch/route-cost-config?operation_area_id=19"
            )
            area_25_response = self.client.get(
                "/admin/dispatch/route-cost-config?operation_area_id=25"
            )

        area_19 = area_19_response.get_json()
        area_25 = area_25_response.get_json()
        self.assertEqual(area_19["config"]["WAIT_COST_PER_MIN"], 9.0)
        self.assertEqual(area_19["config"]["IN_CAR_COST_PER_MIN"], 11.0)
        self.assertEqual(
            area_19["config"]["W_PASSENGER"],
            CoreDispatcher.ROUTE_COST_CONFIG_DEFAULTS["W_PASSENGER"],
        )
        self.assertEqual(
            area_25["config"]["WAIT_COST_PER_MIN"],
            CoreDispatcher.ROUTE_COST_CONFIG_DEFAULTS["WAIT_COST_PER_MIN"],
        )


if __name__ == "__main__":
    unittest.main()
