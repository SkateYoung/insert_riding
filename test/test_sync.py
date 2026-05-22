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
from datetime import datetime, timedelta
from pathlib import Path

# 允许直接执行本脚本时也能导入项目根目录下的 api 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.core import CoreDispatcher
from api.models import CityGraph, Order, Vehicle


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
