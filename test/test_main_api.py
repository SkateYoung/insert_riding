# -*- coding: utf-8 -*-
"""main.py HTTP 接口冒烟测试脚本。

用法：
    python main.py
    python test_main_api.py

可选：
    python test_main_api.py --base-url http://127.0.0.1:5000
"""

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timedelta
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_BASE_URL = "http://127.0.0.1:5000"
TEMP_EXPORT_FILE = "__tmp_main_api_export_test.js"


def configure_console_encoding():
    """尽量让 Windows 控制台按 UTF-8 显示中文，避免输出乱码。"""
    if platform.system() == "Windows":
        os.system("chcp 65001 > nul")

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


class ApiTestError(Exception):
    """接口测试失败时抛出的异常。"""


def request_json(base_url, method, path, body=None, expected_status=200):
    """发送 HTTP 请求，并把响应解析成 JSON。"""
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise ApiTestError(f"无法连接到 {base_url}：{exc.reason}") from exc

    if status != expected_status:
        raise ApiTestError(f"{method} {path} 返回 {status}，预期 {expected_status}：{raw[:300]}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiTestError(f"{method} {path} 没有返回合法 JSON：{raw[:300]}") from exc


def assert_true(condition, message):
    """断言条件成立；失败时抛出统一的测试异常。"""
    if not condition:
        raise ApiTestError(message)


def run_tests(base_url):
    """按顺序测试 main.py 暴露的主要 HTTP 接口。"""
    results = []

    def check(name, func):
        """执行单个测试项并输出耗时。"""
        started = time.perf_counter()
        data = func()
        elapsed_ms = (time.perf_counter() - started) * 1000
        results.append((name, elapsed_ms))
        print(f"[通过] {name}（{elapsed_ms:.0f} 毫秒）")
        return data

    health = check("健康检查 GET /health", lambda: request_json(base_url, "GET", "/health"))
    assert_true(health.get("status") == "ok", "/health 的 status 应为 ok")

    time_info = check("系统时间 GET /time", lambda: request_json(base_url, "GET", "/time"))
    assert_true("timestamp" in time_info and "time_text" in time_info, "/time 应返回 timestamp 和 time_text")
    assert_true(time_info.get("timezone") == "Asia/Shanghai", "/time 应返回 Asia/Shanghai 时区")

    if not health.get("initialized"):
        init = check("初始化系统 POST /init", lambda: request_json(base_url, "POST", "/init", {}))
        assert_true(init.get("status") in {"initialized", "already_initialized"}, "/init 返回了非预期状态")
        assert_true(init.get("nodes", 0) > 0, "/init 应加载到路网节点")
    else:
        print("[跳过] 初始化系统 POST /init（系统已初始化）")

    status = check("系统状态 GET /status", lambda: request_json(base_url, "GET", "/status"))
    assert_true(status.get("initialized") is True, "/status 应返回 initialized=true")
    assert_true(status.get("nodes_count", 0) > 0, "/status 的 nodes_count 应大于 0")
    assert_true(len(status.get("fleet", [])) > 0, "/status 的 fleet 不应为空")

    pois = check("POI 列表 GET /pois", lambda: request_json(base_url, "GET", "/pois"))
    poi_list = pois.get("pois", [])
    assert_true(len(poi_list) >= 2, "/pois 至少应返回 2 个 POI")

    fleet = check("车队列表 GET /fleet", lambda: request_json(base_url, "GET", "/fleet"))
    fleet_list = fleet.get("fleet", [])
    assert_true(len(fleet_list) > 0, "/fleet 应返回车辆列表")

    first_vehicle_id = fleet_list[0]["id"]
    vehicle = check(
        f"单车状态 GET /fleet/{first_vehicle_id}",
        lambda: request_json(base_url, "GET", "/fleet/" + urllib.parse.quote(first_vehicle_id, safe="")),
    )
    assert_true(vehicle.get("id") == first_vehicle_id, "/fleet/<vehicle_id> 返回了错误车辆")

    missing_vehicle = check(
        "不存在车辆 GET /fleet/__missing__ 应返回 404",
        lambda: request_json(base_url, "GET", "/fleet/__missing__", expected_status=404),
    )
    assert_true("error" in missing_vehicle, "不存在车辆的响应应包含 error 字段")

    p0, p1 = poi_list[0], poi_list[1]
    path_body = {"lon": p0["lon"], "lat": p0["lat"]}
    path = check(
        f"更新车辆路径 POST /fleet/{first_vehicle_id}/path",
        lambda: request_json(
            base_url,
            "POST",
            "/fleet/" + urllib.parse.quote(first_vehicle_id, safe="") + "/path",
            path_body,
        ),
    )
    assert_true(path.get("vehicle", {}).get("id") == first_vehicle_id, "更新路径接口应返回对应车辆 id")
    assert_true(isinstance(path.get("gps"), dict), "更新路径接口应返回 gps")
    assert_true(isinstance(path.get("snap"), dict), "更新路径接口应返回 snap")
    assert_true(isinstance(path.get("snap", {}).get("point"), dict), "更新路径接口应返回 snap.point")
    assert_true(isinstance(path.get("route"), dict), "更新路径接口应返回 route")
    assert_true(isinstance(path.get("route", {}).get("points"), list), "更新路径接口应返回 route.points")
    assert_true(isinstance(path.get("route", {}).get("segments"), list), "更新路径接口应返回 route.segments")
    assert_true(isinstance(path.get("events"), list), "更新路径接口应返回 events")
    assert_true(isinstance(path.get("orders"), dict), "更新路径接口应返回 orders")
    assert_true(path.get("path") == path.get("route", {}).get("points"), "兼容字段 path 应等于 route.points")
    assert_true(isinstance(path.get("snapped_point"), dict), "兼容字段 snapped_point 应存在")
    assert_true("planned_route_point" not in path, "更新路径接口不应再返回 planned_route_point")
    assert_true("snapped_node" not in path, "更新路径接口不应再返回 snapped_node")
    assert_true("segments" not in path, "更新路径接口不应再返回顶层 segments")

    now = datetime.now().replace(microsecond=0)
    order_body = {
        "request_id": f"REQ-TEST-{int(time.time() * 1000)}",
        "origin": {"lon": p0["lon"], "lat": p0["lat"]},
        "destination": {"lon": p1["lon"], "lat": p1["lat"]},
        "expected_pickup_time": {
            "earliest": (now + timedelta(minutes=5)).isoformat(sep=" "),
            "latest": (now + timedelta(minutes=20)).isoformat(sep=" "),
        },
        "passenger_count": 1,
        "passenger_phone": "13900000001",
        "passenger_id": "test-passenger-1",
    }
    order = check("创建订单 POST /order", lambda: request_json(base_url, "POST", "/order", order_body))
    assert_true(order.get("status") == "pooled", "/order 应返回 status=pooled")
    assert_true("request_id" in order, "/order 应返回 request_id")
    assert_true("request_time" in order, "/order 应返回后端生成的 request_time")

    cancel_path = "/orders/" + urllib.parse.quote(order_body["request_id"], safe="") + "/cancel"
    cancel = check("取消未上车订单 POST /orders/<request_id>/cancel", lambda: request_json(base_url, "POST", cancel_path))
    assert_true(cancel.get("status") == "cancelled", "取消未上车订单应成功")

    pool = check("订单池 GET /orders/pool", lambda: request_json(base_url, "GET", "/orders/pool"))
    assert_true("pool_size" in pool and "orders" in pool, "/orders/pool 应返回订单池字段")

    rest = check(
        f"司机请求立即休息 POST /fleet/{first_vehicle_id}/rest",
        lambda: request_json(
            base_url,
            "POST",
            "/fleet/" + urllib.parse.quote(first_vehicle_id, safe="") + "/rest",
            {},
        ),
    )
    assert_true(rest.get("decision") == "close_now", "立即休息请求应返回 close_now 决策")
    assert_true(rest.get("rest_status") in {"closing", "resting"}, "车辆应进入收车中或休息中")

    tick = check("刷新真实时间状态 POST /tick", lambda: request_json(base_url, "POST", "/tick", {"dt": 0.1}))
    assert_true("system_time" in tick and "dt" in tick, "/tick 应返回系统时间和真实 elapsed dt")
    assert_true(len(tick.get("fleet", [])) > 0, "/tick 应返回车队状态")

    try:
        export = check(
            "导出地图 POST /export",
            lambda: request_json(base_url, "POST", "/export", {"file_path": TEMP_EXPORT_FILE}),
        )
        assert_true(export.get("status") == "ok", "/export 应返回 status=ok")
        assert_true(os.path.exists(TEMP_EXPORT_FILE), "/export 应创建临时导出文件")
    finally:
        if os.path.exists(TEMP_EXPORT_FILE):
            os.remove(TEMP_EXPORT_FILE)

    print(f"\n全部 {len(results)} 项接口检查通过。")


def main():
    """解析命令行参数并执行接口测试。"""
    configure_console_encoding()

    parser = argparse.ArgumentParser(description="测试 main.py 暴露的 HTTP 接口。")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MAIN_API_BASE_URL", DEFAULT_BASE_URL),
        help="后端服务地址",
    )
    args = parser.parse_args()

    try:
        run_tests(args.base_url)
    except ApiTestError as exc:
        print(f"[失败] {exc}", file=sys.stderr)
        print("请先启动后端服务：python main.py", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
