# -*- coding: utf-8 -*-
"""订单池同步匹配测试脚本。

可直接从项目根目录运行：
    python test/test_sync.py
"""

import os
import platform
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# 允许直接执行本脚本时也能导入项目根目录下的 api 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.core import CoreDispatcher
from api.models import CityGraph, Order, SPEED_MPS, Vehicle


def configure_console_encoding():
    """配置 Windows 控制台编码，避免中文输出乱码或失败。"""
    if platform.system() == "Windows":
        os.system("chcp 65001 > nul")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def make_order(city, request_id, origin_node, destination_node):
    """按当前 Order 模型创建测试订单。"""
    request_time = datetime.now().replace(microsecond=0)
    return Order(
        request_id=request_id,
        o_lon=origin_node.lon,
        o_lat=origin_node.lat,
        d_lon=destination_node.lon,
        d_lat=destination_node.lat,
        request_time=request_time,
        expected_pickup_earliest=request_time,
        expected_pickup_latest=request_time + timedelta(minutes=20),
        passenger_count=1,
        city_map=city,
        req_time=request_time.timestamp(),
    )


class _TinyNode:
    """用于订单池匹配单元测试的最小节点。"""

    def __init__(self, node_id, lon=0.0, lat=0.0):
        self.id = node_id
        self.name = node_id
        self.lon = lon
        self.lat = lat
        self.zone = 1
        self.neighbors = {}


class _TinyCity:
    """用于订单池匹配单元测试的最小路网。"""

    def __init__(self, distances):
        node_ids = sorted({node_id for pair in distances for node_id in pair})
        self.nodes_map = {
            node_id: _TinyNode(node_id, lon=float(index), lat=0.0)
            for index, node_id in enumerate(node_ids)
        }
        self.pois = list(self.nodes_map.values())
        self.path_cache = {}
        self.distances = dict(distances)
        for (start_id, end_id), distance in self.distances.items():
            self.nodes_map[start_id].neighbors[end_id] = distance

    def get_path(self, start_node, end_node, restriction_policy=None):
        if start_node.id == end_node.id:
            return 0.0, [start_node]
        distance = self.distances.get((start_node.id, end_node.id), float("inf"))
        if distance == float("inf"):
            return distance, []
        return distance, [start_node, end_node]


def _seconds_distance(seconds):
    """把行驶秒数换算成当前固定速度模型下的距离。"""
    return float(seconds) * SPEED_MPS


def _fake_order(city, request_id, origin_id, dest_id, base_ts, earliest_offset, latest_offset):
    """构造订单池匹配所需的最小订单对象。"""
    earliest_ts = base_ts + earliest_offset
    latest_ts = base_ts + latest_offset
    return SimpleNamespace(
        request_id=request_id,
        o_node=city.nodes_map[origin_id],
        d_node=city.nodes_map[dest_id],
        passenger_count=1,
        req_time=base_ts,
        expected_pickup_earliest=earliest_ts,
        expected_pickup_latest=latest_ts,
        max_pickup_time=latest_ts,
        max_arrival_time=latest_ts + 3600.0,
        actual_pick_time=None,
        status="pooled",
    )


def _fake_vehicle(vehicle_id, node_id, base_ts):
    """构造订单池匹配所需的最小车辆对象。"""
    return SimpleNamespace(
        id=vehicle_id,
        vehicle_id=vehicle_id,
        time=base_ts,
        last_node=node_id,
        next_node=node_id,
        progress=0.0,
        on_board_orders=[],
        planned_route=[],
        capacity=4,
        op_zone=None,
        is_rest_requested=False,
        is_resting=False,
        rest_status="operating",
    )


class _StopPoolLoop(Exception):
    """用于让后台订单池循环只执行一轮。"""


class PoolTimeWindowMatchingTest(unittest.TestCase):
    """验证订单池匹配会尊重期望上车时间窗。"""

    def setUp(self):
        CoreDispatcher.order_pool.clear()

    def tearDown(self):
        CoreDispatcher.order_pool.clear()

    def _run_one_pool_loop(self, fleet, city):
        with mock.patch("api.core.time.sleep", side_effect=_StopPoolLoop), \
                mock.patch.object(CoreDispatcher, "refresh_scheduled_rest_requests", return_value=None), \
                mock.patch.object(CoreDispatcher, "refresh_vehicle_route_metadata", return_value={}), \
                mock.patch("api.core.persistence.record_dispatch_assignment"):
            with self.assertRaises(_StopPoolLoop):
                CoreDispatcher.process_pool_matching(fleet, city)

    def test_future_order_stays_in_pool_before_dispatch_window(self):
        base_ts = 1_000_000.0
        city = _TinyCity({
            ("V", "O"): _seconds_distance(600),
            ("O", "D"): _seconds_distance(300),
        })
        vehicle = _fake_vehicle("V1", "V", base_ts)
        order = _fake_order(city, "FUTURE", "O", "D", base_ts, 3600, 4200)
        CoreDispatcher.order_pool.append(order)

        self._run_one_pool_loop([vehicle], city)

        self.assertEqual(CoreDispatcher.order_pool, [order])
        self.assertEqual(vehicle.planned_route, [])
        self.assertEqual(order.status, "pooled")

    def test_vehicle_that_arrives_inside_window_beats_too_early_vehicle(self):
        base_ts = 1_000_000.0
        city = _TinyCity({
            ("NEAR", "O"): _seconds_distance(60),
            ("FAR", "O"): _seconds_distance(360),
            ("O", "D"): _seconds_distance(120),
        })
        near_vehicle = _fake_vehicle("NEAR_V", "NEAR", base_ts)
        far_vehicle = _fake_vehicle("FAR_V", "FAR", base_ts)
        order = _fake_order(city, "WINDOW", "O", "D", base_ts, 600, 1200)
        CoreDispatcher.order_pool.append(order)

        self._run_one_pool_loop([near_vehicle, far_vehicle], city)

        self.assertEqual(CoreDispatcher.order_pool, [])
        self.assertEqual(near_vehicle.planned_route, [])
        self.assertEqual([step["order"].request_id for step in far_vehicle.planned_route], ["WINDOW", "WINDOW"])
        self.assertEqual(order.status, "waiting_pickup")


def main():
    """执行订单入池与池化匹配的基础联调。"""
    configure_console_encoding()
    CoreDispatcher.order_pool.clear()

    print("正在加载路网...")
    city = CityGraph("dxc_traffic_shp/dxc_rule.shp")

    start_node = city.pois[0]
    vehicle = Vehicle("测试车辆1", start_node.id, "#10b981", zone=start_node.zone)
    fleet = [vehicle]

    print("\n--- 测试场景 1：新订单进入订单池 ---")
    order1 = make_order(city, "1", city.pois[-1], city.pois[5])
    status = CoreDispatcher.pool_and_route_planning(fleet, order1, city)
    print(f"订单 1 即时指派结果：{'成功' if status else '进入订单池'}")
    print(f"当前订单池大小：{len(CoreDispatcher.order_pool)}")

    print("\n--- 测试场景 2：第二个订单继续进入订单池 ---")
    order2 = make_order(city, "2", city.pois[10], city.pois[11])
    status = CoreDispatcher.pool_and_route_planning(fleet, order2, city)
    print(f"订单 2 即时指派结果：{'成功' if status else '进入订单池'}")
    print(f"当前订单池大小：{len(CoreDispatcher.order_pool)}")

    print("\n--- 测试场景 3：执行订单池匹配 ---")
    matching_thread = threading.Thread(
        target=CoreDispatcher.process_pool_matching,
        args=(fleet, city),
        daemon=True,
    )
    matching_thread.start()

    deadline = time.time() + 10
    while CoreDispatcher.order_pool and time.time() < deadline:
        time.sleep(0.2)

    print(f"匹配后订单池大小：{len(CoreDispatcher.order_pool)}")
    print(f"车辆最终规划步骤数：{len(vehicle.planned_route)}")


if __name__ == "__main__":
    main()
