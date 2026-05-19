"""Flask 运行期共享状态。

该模块集中保存路网、车队、后台匹配线程等进程内单例对象。
接口层只读取这些状态，初始化和模拟数据注入统一由 init_system 完成。
"""

import threading
import time

from .models import CityGraph, Order, Vehicle
from .core import CoreDispatcher


city = None
fleet = None
matching_thread = None
system_initialized = False


def _seed_completed_orders(city_map, count=30):
    """生成用于预测测试的历史完成订单。

    Args:
        city_map (CityGraph): 已完成 POI 映射的城市路网对象。
        count (int): 需要生成的模拟订单数量。

    Returns:
        None。

    Side Effects:
        清空并重建 CoreDispatcher.completed_orders_pool。
    """
    CoreDispatcher.completed_orders_pool = []
    if len(city_map.pois) < 2:
        return

    # 热点 OD 故意重复出现，让预测模块能稳定识别高需求上车区域。
    hot_pairs = [
        (3, 8), (3, 8), (3, 8), (3, 9), (3, 10),
        (5, 8), (5, 8), (5, 9),
        (1, 12), (2, 14),
    ]
    now = time.time()
    for i in range(count):
        p_idx, d_idx = hot_pairs[i % len(hot_pairs)]
        p = city_map.pois[p_idx % len(city_map.pois)]
        d = city_map.pois[d_idx % len(city_map.pois)]
        req_time = now - (count - i) * 300
        order = Order(f"mock-completed-{i + 1:02d}", p.lon, p.lat, d.lon, d.lat, req_time, city_map)
        order.status = "completed"
        order.actual_pick_time = req_time + 180
        order.completion_time = req_time + 900
        CoreDispatcher.completed_orders_pool.append(order)


def init_system(shp_path="dxc_traffic_shp/dxc_rule.shp"):
    """加载路网、创建车队、注入测试历史订单并启动后台匹配引擎。

    Args:
        shp_path (str): 路网 SHP 文件路径。

    Returns:
        None。

    Side Effects:
        更新模块级 city、fleet、matching_thread、system_initialized。
        启动一个 daemon 后台线程持续处理订单池匹配和空车停靠预测。
    """
    global city, fleet, matching_thread, system_initialized

    city = CityGraph(shp_path)

    # 测试车队固定从三个 POI 出发，便于前端和接口测试复现路径。
    fleet = [
        Vehicle("巴士-绿色01", city.pois[0].id, "#10b981", zone=city.pois[0].zone),
        Vehicle("巴士-蓝色02", city.pois[12].id, "#3b82f6", zone=city.pois[12].zone),
        Vehicle("巴士-橙色03", city.pois[24].id, "#f59e0b", zone=city.pois[24].zone),
    ]

    fleet[0].driver_id, fleet[0].driver_no = "700045866645051565", "6800A145"
    fleet[0].vehicle_id, fleet[0].plate_no = "72057594546143661", "粤A00001"

    fleet[1].driver_id, fleet[1].driver_no = "700045866645052222", "6800B222"
    fleet[1].vehicle_id, fleet[1].plate_no = "72057594546144444", "粤A00002"

    fleet[2].driver_id, fleet[2].driver_no = "700045866645053333", "6800C333"
    fleet[2].vehicle_id, fleet[2].plate_no = "72057594546145555", "粤A00003"

    for v in fleet:
        CoreDispatcher.refresh_vehicle_route_metadata(v, city)

    # 预测模块依赖历史订单样本；这里注入模拟完成订单，不进入实时订单池。
    _seed_completed_orders(city, count=30)

    matching_thread = threading.Thread(
        target=CoreDispatcher.process_pool_matching,
        args=(fleet, city),
        daemon=True,
        name="OrderMatchingEngine",
    )
    matching_thread.start()

    system_initialized = True
