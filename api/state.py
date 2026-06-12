"""Flask 运行期共享状态。

该模块集中保存路网、车队、后台匹配线程等进程内单例对象。
接口层只读取这些状态，初始化和模拟数据注入统一由 init_system 完成。
"""

import threading
import time
from datetime import datetime, timedelta, timezone

from .models import CityGraph, Order, Vehicle
from .core import CoreDispatcher


# ============================================================
# 功能一：Flask 进程内共享运行状态与统一业务时间
# 相关变量：city、fleet、matching_thread、clock_thread、eta_thread、route_grasp_thread、system_initialized
# ============================================================

city = None
fleet = None
matching_thread = None
clock_thread = None
eta_thread = None
system_initialized = False
state_lock = threading.RLock()

TIMEZONE_NAME = "Asia/Shanghai"
BUSINESS_TIMEZONE = timezone(timedelta(hours=8), TIMEZONE_NAME)
TIME_MODE = "real_time"
CLOCK_INTERVAL_SECONDS = 1.0
ETA_REFRESH_INTERVAL_SECONDS = CoreDispatcher.ETA_REFRESH_INTERVAL_SECONDS
clock_last_timestamp = None
clock_last_dt = 0.0
clock_tick_count = 0


def _business_now():
    """读取 Asia/Shanghai 业务时间。"""
    return datetime.now(BUSINESS_TIMEZONE).replace(microsecond=0)


def format_timestamp(timestamp_value):
    """将 Unix 时间戳格式化为业务可读时间。"""
    return datetime.fromtimestamp(float(timestamp_value), BUSINESS_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def now_timestamp():
    """返回当前统一业务时间戳。"""
    return _business_now().timestamp()


def now_datetime():
    """返回当前统一业务 datetime，保持无时区格式以兼容现有订单模型输出。"""
    return _business_now().replace(tzinfo=None)


def datetime_to_timestamp(value):
    """按 Asia/Shanghai 语义把 datetime 转成 Unix 时间戳。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=BUSINESS_TIMEZONE)
    return value.timestamp()


def parse_business_datetime(value):
    """解析接口传入的业务时间字符串。"""
    parsed = datetime.fromisoformat(str(value).replace("/", "-"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(BUSINESS_TIMEZONE).replace(tzinfo=None)
    return parsed


def current_time():
    """返回接口统一使用的系统时间快照。"""
    now = _business_now()
    return {
        "mode": TIME_MODE,
        "timezone": TIMEZONE_NAME,
        "timestamp": now.timestamp(),
        "time_text": now.strftime("%Y-%m-%d %H:%M:%S"),
        "clock_interval_seconds": CLOCK_INTERVAL_SECONDS,
        "clock_running": clock_thread is not None and clock_thread.is_alive(),
        "clock_last_dt": clock_last_dt,
        "clock_tick_count": clock_tick_count,
        "eta_refresh_interval_seconds": ETA_REFRESH_INTERVAL_SECONDS,
        "eta_thread_running": eta_thread is not None and eta_thread.is_alive(),
        "eta_last_refresh_timestamp": CoreDispatcher.eta_last_refresh_timestamp,
        "eta_last_refresh_time_text": (
            format_timestamp(CoreDispatcher.eta_last_refresh_timestamp)
            if CoreDispatcher.eta_last_refresh_timestamp is not None
            else None
        ),
        "route_grasp_mode": "on_route_update_async",
        "route_grasp_async_enabled": CoreDispatcher.route_grasp_auto_submit_enabled,
        "route_grasp_inflight_count": CoreDispatcher.route_grasp_inflight_count(),
        "route_grasp_thread_running": False,
        "route_grasp_last_refresh_timestamp": CoreDispatcher.route_grasp_last_refresh_timestamp,
        "route_grasp_last_refresh_time_text": (
            format_timestamp(CoreDispatcher.route_grasp_last_refresh_timestamp)
            if CoreDispatcher.route_grasp_last_refresh_timestamp is not None
            else None
        ),
    }


def refresh_runtime_state(current_timestamp=None):
    """按真实 elapsed seconds 推进车辆状态并刷新休息控制。"""
    global clock_last_timestamp, clock_last_dt, clock_tick_count

    with state_lock:
        if not system_initialized or city is None or fleet is None:
            return 0.0

        current_timestamp = float(current_timestamp if current_timestamp is not None else now_timestamp())
        previous_timestamp = clock_last_timestamp or current_timestamp
        dt = max(0.0, current_timestamp - previous_timestamp)
        clock_last_timestamp = current_timestamp
        clock_last_dt = dt
        clock_tick_count += 1

        for vehicle in fleet:
            vehicle.tick(dt, current_time=current_timestamp)
        CoreDispatcher.refresh_scheduled_rest_requests(fleet, city)
        return dt


def refresh_order_etas_if_due(current_timestamp=None, force=False, service=None):
    """委托 CoreDispatcher 刷新订单 ETA；保留为测试和手动触发入口。"""
    current_timestamp = float(current_timestamp if current_timestamp is not None else now_timestamp())
    return CoreDispatcher.refresh_order_etas_if_due(
        fleet,
        city,
        state_lock,
        current_timestamp=current_timestamp,
        force=force,
        service=service,
    )


def refresh_route_grasps_if_due(current_timestamp=None, force=False, service=None):
    """委托 CoreDispatcher 刷新车辆路线纠偏；保留为测试和手动触发入口。"""
    current_timestamp = float(current_timestamp if current_timestamp is not None else now_timestamp())
    return CoreDispatcher.refresh_route_grasps_if_due(
        fleet,
        state_lock,
        current_timestamp=current_timestamp,
        force=force,
        service=service,
    )


def _clock_loop():
    """后台真实时间时钟线程。"""
    global clock_last_timestamp

    clock_last_timestamp = now_timestamp()
    while True:
        time.sleep(CLOCK_INTERVAL_SECONDS)
        current_timestamp = now_timestamp()
        refresh_runtime_state(current_timestamp)


def _eta_loop():
    """后台高德 ETA 刷新线程；独立于车辆时钟线程运行。"""
    while True:
        time.sleep(ETA_REFRESH_INTERVAL_SECONDS)
        refresh_order_etas_if_due(now_timestamp(), force=True)


def _route_grasp_loop():
    """后台路线纠偏线程；独立于车辆时钟和订单 ETA 线程运行。"""
    return None


def start_clock_thread():
    """启动后台统一时钟线程；已启动时直接复用。"""
    global clock_thread, clock_last_timestamp

    if clock_thread is not None and clock_thread.is_alive():
        return clock_thread

    clock_last_timestamp = now_timestamp()
    clock_thread = threading.Thread(
        target=_clock_loop,
        daemon=True,
        name="RealtimeClockEngine",
    )
    clock_thread.start()
    return clock_thread


def start_eta_thread():
    """启动后台订单 ETA 刷新线程；已启动时直接复用。"""
    global eta_thread

    if eta_thread is not None and eta_thread.is_alive():
        return eta_thread

    eta_thread = threading.Thread(
        target=_eta_loop,
        daemon=True,
        name="OrderEtaRefreshEngine",
    )
    eta_thread.start()
    return eta_thread


def start_route_grasp_thread():
    """启动后台路线纠偏线程；已启动时直接复用。"""
    # 兼容入口：只启用路线更新触发式异步纠偏，不再启动周期扫描线程。
    CoreDispatcher.configure_route_grasp_async(state_lock=state_lock, enabled=True)
    CoreDispatcher.configure_route_grasp_async(state_lock=state_lock, enabled=True)
    return None


# ============================================================
# 功能二：预测模块测试历史订单注入--测试用
# 相关方法：_seed_completed_orders
# ============================================================

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
    now = now_datetime()
    for i in range(count):
        o_idx, d_idx = hot_pairs[i % len(hot_pairs)]
        o = city_map.pois[o_idx % len(city_map.pois)]
        d = city_map.pois[d_idx % len(city_map.pois)]
        request_time = now - timedelta(minutes=(count - i) * 5)
        order = Order(
            request_id=f"mock-completed-{i + 1:02d}",
            o_lon=o.lon,
            o_lat=o.lat,
            d_lon=d.lon,
            d_lat=d.lat,
            request_time=request_time,
            expected_pickup_earliest=request_time + timedelta(minutes=3),
            expected_pickup_latest=request_time + timedelta(minutes=18),
            passenger_count=1 + (i % 3),
            city_map=city_map,
            req_time=datetime_to_timestamp(request_time),
        )
        order.status = "completed"
        order.actual_pick_time = datetime_to_timestamp(request_time) + 180
        order.completion_time = datetime_to_timestamp(request_time) + 900
        CoreDispatcher.completed_orders_pool.append(order)


# ============================================================
# 功能三：系统初始化入口
# 相关方法：init_system
# ============================================================

def init_system(shp_path="shp/dxc_traffic_mars_shp_0606/dxc0606.shp"):
    """加载路网、创建车队、注入测试历史订单并启动后台匹配引擎。

    Args:
        shp_path (str): 路网 SHP 文件路径。

    Returns:
        None。

    Side Effects:
        更新模块级 city、fleet、matching_thread、system_initialized。
        启动后台匹配线程、真实时间线程、路线纠偏线程和订单 ETA 刷新线程。
    """
    global city, fleet, matching_thread, system_initialized

    with state_lock:
        city = CityGraph(shp_path)

        # 测试车队固定从三个 POI 出发，便于前端和接口测试复现路径。
        fleet = [
            Vehicle("巴士-绿色01", city.pois[0].id, "#10b981", zone=city.pois[0].zone),
            Vehicle("巴士-蓝色02", city.pois[12].id, "#3b82f6", zone=city.pois[12].zone),
            Vehicle("巴士-橙色03", city.pois[24].id, "#f59e0b", zone=city.pois[24].zone),
        ]
        current_timestamp = now_timestamp()
        for vehicle in fleet:
            vehicle.time = current_timestamp

        fleet[0].driver_id, fleet[0].driver_no = "700045866645051565", "6800A145"
        fleet[0].vehicle_id, fleet[0].plate_no = "72057594546143661", "粤A00001"

        fleet[1].driver_id, fleet[1].driver_no = "700045866645052222", "6800B222"
        fleet[1].vehicle_id, fleet[1].plate_no = "72057594546144444", "粤A00002"

        fleet[2].driver_id, fleet[2].driver_no = "700045866645053333", "6800C333"
        fleet[2].vehicle_id, fleet[2].plate_no = "72057594546145555", "粤A00003"

        CoreDispatcher.configure_route_grasp_async(state_lock=state_lock, enabled=True)

        for v in fleet:
            CoreDispatcher.refresh_vehicle_route_metadata(v, city)

        # 预测模块依赖历史订单样本；这里注入模拟完成订单，不进入实时订单池。
        _seed_completed_orders(city, count=30)
        system_initialized = True

    matching_thread = threading.Thread(
        target=CoreDispatcher.process_pool_matching,
        args=(fleet, city, state_lock),
        daemon=True,
        name="OrderMatchingEngine",
    )
    matching_thread.start()
    start_clock_thread()
    start_eta_thread()
