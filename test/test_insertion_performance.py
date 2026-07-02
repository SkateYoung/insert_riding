# -*- coding: utf-8 -*-
"""订单插入算法性能与最优性测试脚本。

该脚本不启动 Flask，也不依赖后台匹配线程，直接调用后端核心算法：

    python test_insertion_performance.py

可选参数：

    python test_insertion_performance.py --optimal-orders 4 --perf-orders 100 --vehicles 10

测试内容：
1. 小规模场景用暴力枚举所有合法 O/D 顺序，检查 _try_insert_order 是否达到全局最优。
2. 大规模随机场景统计插单耗时、可行率和路线合法性。
"""

import argparse
import itertools
import os
import platform
import random
import statistics
import sys
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

# 允许直接执行本脚本时也能导入项目根目录下的 api 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.core import CoreDispatcher
from api.models import CityGraph, Order, SPEED_MPS, Vehicle


DEFAULT_SHP_PATH = "dxc_traffic_shp/dxc_rule.shp"


def configure_console_encoding():
    """配置 Windows 控制台编码，避免中文输出乱码。"""
    if platform.system() == "Windows":
        os.system("chcp 65001 > nul")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def make_order(city, request_id, origin_idx, dest_idx, request_time, passenger_count=1):
    """根据 POI 下标创建订单。

    Args:
        city (CityGraph): 已加载的路网对象。
        request_id (str): 订单 ID。
        origin_idx (int): 起点 POI 下标。
        dest_idx (int): 终点 POI 下标。
        request_time (datetime): 请求时间。
        passenger_count (int): 乘客人数。

    Returns:
        Order: 可直接传入调度核心的订单对象。
    """
    origin = city.pois[origin_idx % len(city.pois)]
    destination = city.pois[dest_idx % len(city.pois)]
    if origin.id == destination.id:
        destination = city.pois[(dest_idx + 1) % len(city.pois)]

    return Order(
        request_id=request_id,
        o_lon=origin.lon,
        o_lat=origin.lat,
        d_lon=destination.lon,
        d_lat=destination.lat,
        request_time=request_time,
        expected_pickup_earliest=request_time + timedelta(minutes=1),
        expected_pickup_latest=request_time + timedelta(minutes=20),
        passenger_count=passenger_count,
        city_map=city,
        req_time=request_time.timestamp(),
    )


def make_vehicle(city, vehicle_id, start_idx=0, capacity=10):
    """创建测试车辆。"""
    start = city.pois[start_idx % len(city.pois)]
    vehicle = Vehicle(vehicle_id, start.id, "#10b981", zone=start.zone, capacity=capacity)
    vehicle.time = datetime.now().replace(microsecond=0).timestamp()
    return vehicle


def route_signature(route):
    """将路线转换为便于打印比较的短字符串。"""
    if not route:
        return "-"
    return " -> ".join(f"{step['type']}{step['order'].request_id}" for step in route)


def validate_route(vehicle, route):
    """校验路线是否满足容量约束和 O/D 顺序约束。

    Args:
        vehicle (Vehicle): 被校验车辆。
        route (list[dict]): planned_route 格式路线。

    Returns:
        tuple[bool, str]: (是否合法, 错误说明)。
    """
    load = sum(order.passenger_count for order in vehicle.on_board_orders)
    seen_origin = {order.request_id for order in vehicle.on_board_orders}

    for step in route or []:
        order = step["order"]
        request_id = order.request_id
        if step["type"] == "O":
            if request_id in seen_origin:
                return False, f"订单 {request_id} 重复接客"
            seen_origin.add(request_id)
            load += order.passenger_count
        elif step["type"] == "D":
            if request_id not in seen_origin:
                return False, f"订单 {request_id} 未接客就送客"
            load -= order.passenger_count
        else:
            return False, f"未知步骤类型 {step['type']}"

        if load < 0:
            return False, "载客数小于 0"
        if load > vehicle.capacity:
            return False, f"载客数 {load} 超过容量 {vehicle.capacity}"

    return True, "合法"


def is_valid_od_sequence(route, on_board_ids):
    """判断 O/D 排列是否满足先接后送。"""
    seen_origin = set(on_board_ids)
    for step in route:
        request_id = step["order"].request_id
        if step["type"] == "O":
            if request_id in seen_origin:
                return False
            seen_origin.add(request_id)
        elif request_id not in seen_origin:
            return False
    return True


class _TinyNode:
    """用于单元测试的最小路网节点。"""

    def __init__(self, node_id, lon=0.0, lat=0.0):
        self.id = node_id
        self.name = node_id
        self.lon = lon
        self.lat = lat
        self.zone = 1
        self.neighbors = {}


class _TinyCity:
    """用于单元测试的最小路网。"""

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
    """构造只包含核心算法所需字段的订单对象。"""
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
    )


class TimeWindowRouteEvaluationTest(unittest.TestCase):
    """验证插单评分会按乘客期望上车时间窗推演 pickup_times。"""

    def _evaluate(self, first_leg_seconds, earliest_offset, latest_offset, second_leg_seconds=300):
        base_ts = 1_000_000.0
        city = _TinyCity({
            ("A", "O"): _seconds_distance(first_leg_seconds),
            ("O", "D"): _seconds_distance(second_leg_seconds),
        })
        order = _fake_order(city, "TW1", "O", "D", base_ts, earliest_offset, latest_offset)
        vehicle_state = {"time": base_ts, "last_node": "A", "next_node": "A", "progress": 0.0}
        return CoreDispatcher.evaluate_route(
            [{"type": "O", "order": order}, {"type": "D", "order": order}],
            vehicle_state,
            [],
            city,
            capacity=4,
            return_details=True,
        )

    def test_pickup_inside_expected_window_has_no_time_window_cost(self):
        is_feasible, cost, _, details = self._evaluate(600, 540, 720)
        self.assertTrue(is_feasible)
        self.assertLess(cost, float("inf"))
        self.assertAlmostEqual(details["metrics"]["pickup_times"]["TW1"], 1_000_600.0)
        self.assertEqual(details["time_window_cost"], 0.0)

    def test_early_pickup_waits_until_earliest_and_shifts_dropoff(self):
        is_feasible, _, arrivals, details = self._evaluate(420, 600, 1200, second_leg_seconds=300)
        self.assertTrue(is_feasible)
        self.assertAlmostEqual(details["metrics"]["pickup_arrival_times"]["TW1"], 1_000_420.0)
        self.assertAlmostEqual(details["metrics"]["pickup_times"]["TW1"], 1_000_600.0)
        self.assertAlmostEqual(details["metrics"]["early_pickup_wait_seconds"]["TW1"], 180.0)
        self.assertAlmostEqual(arrivals["TW1"], 1_000_900.0)

    def test_early_pickup_over_limit_is_infeasible(self):
        is_feasible, cost, _, details = self._evaluate(240, 600, 1200)
        self.assertFalse(is_feasible)
        self.assertEqual(cost, float("inf"))
        self.assertEqual(details["infeasible_reason"], "pickup_too_early")
        self.assertAlmostEqual(details["early_wait_seconds"], 360.0)

    def test_late_pickup_keeps_finite_penalty(self):
        is_feasible, cost, _, details = self._evaluate(900, 60, 600)
        self.assertTrue(is_feasible)
        self.assertLess(cost, float("inf"))
        self.assertGreater(details["late_pickup_cost"], 0.0)
        self.assertEqual(details["early_pickup_wait_cost"], 0.0)

    def test_reserved_order_wait_cost_starts_from_earliest(self):
        is_feasible, _, _, details = self._evaluate(3420, 3600, 4200)
        self.assertTrue(is_feasible)
        self.assertAlmostEqual(details["metrics"]["pickup_times"]["TW1"], 1_003_600.0)
        self.assertEqual(details["wait_cost"], 0.0)
        self.assertGreater(details["early_pickup_wait_cost"], 0.0)


def brute_force_best_route(vehicle, orders, city):
    """暴力枚举小规模订单的所有合法 O/D 顺序，求全局最优路线。

    Args:
        vehicle (Vehicle): 测试车辆。
        orders (list[Order]): 待服务订单。
        city (CityGraph): 路网对象。

    Returns:
        tuple[list|None, float, int]: 最优路线、最优成本、枚举的合法路线数量。
    """
    steps = []
    for order in orders:
        steps.append({"type": "O", "order": order})
        steps.append({"type": "D", "order": order})

    vehicle_state = {
        "time": vehicle.time,
        "last_node": vehicle.last_node,
        "next_node": vehicle.next_node,
        "progress": vehicle.progress,
    }
    on_board_ids = {order.request_id for order in vehicle.on_board_orders}

    best_route = None
    best_cost = float("inf")
    valid_count = 0
    for permutation in itertools.permutations(steps):
        route = list(permutation)
        if not is_valid_od_sequence(route, on_board_ids):
            continue
        valid_count += 1
        is_feasible, cost, _ = CoreDispatcher.evaluate_route(
            route,
            vehicle_state,
            vehicle.on_board_orders,
            city,
            vehicle.capacity,
            v_zone=vehicle.op_zone,
        )
        if is_feasible and cost < best_cost:
            best_route = route
            best_cost = cost

    return best_route, best_cost, valid_count


def run_optimality_test(city, order_count, seed):
    """运行小规模最优性对照测试。"""
    random.seed(seed)
    now = datetime.now().replace(microsecond=0)
    vehicle = make_vehicle(city, "最优性测试车", start_idx=0, capacity=10)
    orders = []
    used_pairs = set()
    for i in range(order_count):
        while True:
            origin_idx = random.randrange(0,len(city.pois))
            dest_idx = random.randrange(0,len(city.pois))
            print(origin_idx,dest_idx)
            if origin_idx != dest_idx and (origin_idx, dest_idx) not in used_pairs:
                used_pairs.add((origin_idx, dest_idx))
                break
        orders.append(make_order(city, f"O{i + 1}", origin_idx, dest_idx, now))

    # _try_insert_order 每次插一单；这里模拟逐单插入后的最终路线。
    algorithm_route = []
    algorithm_cost = 0.0

    for order in orders:
        print("origin:{0},{1},destination:{2},{3}".format(order.o_lon, order.o_lat,order.d_lon,order.d_lat))
        vehicle.planned_route = algorithm_route
        route, cost = CoreDispatcher._try_insert_order(vehicle, order, city)
        if route is None:
            algorithm_route = None
            algorithm_cost = float("inf")
            break
        algorithm_route = route
        algorithm_cost = cost

    brute_route, brute_cost, valid_count = brute_force_best_route(vehicle, orders, city)
    is_valid, valid_message = validate_route(vehicle, algorithm_route)
    if brute_cost == float("inf") and algorithm_cost == float("inf"):
        gap = 0.0
    elif brute_cost == 0:
        gap = 0.0 if algorithm_cost == 0 else float("inf")
    else:
        gap = max(0.0, (algorithm_cost - brute_cost) / brute_cost)

    print("\n========== 小规模最优性测试 ==========")
    print(f"订单数量：{order_count}")
    print(f"合法暴力枚举路线数：{valid_count}")
    print(f"算法路线合法性：{valid_message}")
    print(f"算法成本：{algorithm_cost:.4f}")
    print(f"暴力最优成本：{brute_cost:.4f}")
    print(f"最优性差距：{gap * 100:.2f}%")
    print(f"算法路线：{route_signature(algorithm_route)}")
    print(f"最优路线：{route_signature(brute_route)}")

    return {
        "is_valid": is_valid,
        "gap": gap,
        "algorithm_cost": algorithm_cost,
        "brute_cost": brute_cost,
    }


def run_performance_test(city, vehicle_count, order_count, seed):
    """运行随机压力测试，统计插单耗时与可行性。"""
    random.seed(seed)
    now = datetime.now().replace(microsecond=0)
    vehicles = [
        make_vehicle(city, f"性能测试车-{i + 1}", start_idx=i, capacity=10)
        for i in range(vehicle_count)
    ]
    orders = [
        make_order(
            city,
            f"P{i + 1}",
            random.randrange(len(city.pois)),
            random.randrange(len(city.pois)),
            now + timedelta(seconds=i),
            passenger_count=random.choice([1, 1, 1, 2]),
        )
        for i in range(order_count)
    ]

    durations_ms = []
    feasible_count = 0
    invalid_count = 0
    assigned_count = 0

    started = time.perf_counter()
    for order in orders:
        best_vehicle = None
        best_route = None
        best_cost = float("inf")

        for vehicle in vehicles:
            step_started = time.perf_counter()
            route, cost = CoreDispatcher._try_insert_order(vehicle, order, city)
            durations_ms.append((time.perf_counter() - step_started) * 1000)
            if route is not None and cost < best_cost:
                best_vehicle = vehicle
                best_route = route
                best_cost = cost

        if best_route is not None:
            feasible_count += 1
            is_valid, _ = validate_route(best_vehicle, best_route)
            if not is_valid:
                invalid_count += 1
            best_vehicle.planned_route = best_route
            assigned_count += 1

    total_ms = (time.perf_counter() - started) * 1000
    avg_ms = statistics.mean(durations_ms) if durations_ms else 0.0
    p95_ms = statistics.quantiles(durations_ms, n=20)[18] if len(durations_ms) >= 20 else max(durations_ms, default=0.0)
    max_ms = max(durations_ms, default=0.0)

    print("\n========== 随机性能压力测试 ==========")
    print(f"车辆数：{vehicle_count}")
    print(f"订单数：{order_count}")
    print(f"尝试插单次数：{len(durations_ms)}")
    print(f"成功匹配订单数：{assigned_count}")
    print(f"无可行路线订单数：{order_count - feasible_count}")
    print(f"非法路线数量：{invalid_count}")
    print(f"总耗时：{total_ms:.2f} ms")
    print(f"平均单次插单耗时：{avg_ms:.2f} ms")
    print(f"P95 单次插单耗时：{p95_ms:.2f} ms")
    print(f"最大单次插单耗时：{max_ms:.2f} ms")
    print(f"路径缓存数量：{len(city.path_cache)}")

    return {
        "assigned_count": assigned_count,
        "invalid_count": invalid_count,
        "total_ms": total_ms,
        "avg_ms": avg_ms,
        "p95_ms": p95_ms,
        "max_ms": max_ms,
    }


def main():
    """解析参数并执行测试。"""
    configure_console_encoding()

    parser = argparse.ArgumentParser(description="测试订单插入算法的最优性和性能。")
    parser.add_argument("--shp-path", default=DEFAULT_SHP_PATH, help="路网 SHP 文件路径")
    parser.add_argument("--seed", type=int, default=6, help="随机种子")
    parser.add_argument("--optimal-orders", type=int, default=4, help="暴力最优性测试订单数，建议 1-4")
    parser.add_argument("--vehicles", type=int, default=5, help="性能测试车辆数")
    parser.add_argument("--perf-orders", type=int, default=50, help="性能测试订单数")
    args = parser.parse_args()

    if args.optimal_orders < 1 or args.optimal_orders > 4:
        print("optimal-orders 建议控制在 1 到 4，避免暴力枚举耗时过长。", file=sys.stderr)
        return 2

    city = CityGraph(args.shp_path)
    optimal_result = run_optimality_test(city, args.optimal_orders, args.seed)
    perf_result = run_performance_test(city, args.vehicles, args.perf_orders, args.seed)

    if not optimal_result["is_valid"] or perf_result["invalid_count"] > 0:
        print("\n[失败] 插入算法产生了非法路线。")
        return 1

    print("\n[完成] 测试结束。请重点查看最优性差距和 P95/最大插单耗时。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
