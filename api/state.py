"""Flask 运行期共享状态。

该模块集中保存路网、车队、后台匹配线程等进程内单例对象。
接口层只读取这些状态，初始化统一由 init_system 完成。
"""

import threading
import time
import random
from datetime import datetime, timedelta, timezone

from . import persistence
from .models import CityGraph, Vehicle
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
runtime_random = random.SystemRandom()
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
        "eta_refresh_max_workers": CoreDispatcher._eta_refresh_worker_count(
            len(fleet or [])
            if fleet is not None
            else int(CoreDispatcher.ETA_REFRESH_MAX_WORKERS)
        ),
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
        "operation_restriction_policy_signature": CoreDispatcher.current_operation_restriction_signature(),
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
        loop_started = time.monotonic()
        refresh_order_etas_if_due(now_timestamp(), force=True)
        elapsed = time.monotonic() - loop_started
        time.sleep(max(0.5, ETA_REFRESH_INTERVAL_SECONDS - elapsed))


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


def load_active_operation_restriction_policy():
    """从持久化层加载当前生效的运营禁区策略。

    Returns:
        dict | None: 当前生效策略；未配置或读取失败时返回 None。
    """
    policy = persistence.get_active_operation_restriction_policy()
    CoreDispatcher.set_operation_restriction_policy(policy)
    return policy


def _nearest_node_from_coords(city_map, lon, lat):
    """按经纬度查找最近路网节点。

    Args:
        city_map (CityGraph): 当前路网对象。
        lon (float): 经度。
        lat (float): 纬度。

    Returns:
        Node | None: 最近的路网节点；路网为空时返回 None。
    """
    best_node = None
    best_dist = float("inf")
    for node in city_map.nodes_map.values():
        dx = float(lon) - float(node.lon)
        dy = float(lat) - float(node.lat)
        dist = dx * dx + dy * dy
        if dist < best_dist:
            best_dist = dist
            best_node = node
    return best_node


def _random_poi_node(city_map):
    """从当前路网 POI 中随机选择一个车辆起始节点。"""
    pois = list(getattr(city_map, "pois", []) or [])
    if not pois:
        return None
    return runtime_random.choice(pois)


def _vehicle_from_db_record(record, city_map, current_timestamp):
    """把数据库车辆档案转换成运行期 Vehicle 对象。

    Args:
        record (dict): 持久化层读取的车辆档案与运行位置字段。
        city_map (CityGraph): 当前路网对象。
        current_timestamp (float): 初始化时统一使用的仿真时间戳。

    Returns:
        Vehicle | None: 可进入运行车队的车辆对象；离线、维修或缺少位置时返回 None。
    """
    operation_status = record.get("operation_status") or "offline"
    if operation_status not in {"operating", "resting", "closing", "idle", "serving"}:
        return None
    node = None
    # node = city_map.nodes_map.get(record.get("next_node_code") or record.get("last_node_code"))
    # if node is None and record.get("current_lon") is not None and record.get("current_lat") is not None:
    #     node = _nearest_node_from_coords(city_map, record["current_lon"], record["current_lat"])
    if node is None:
        node = _random_poi_node(city_map)
    if node is None:
        return None
    vehicle_code = record.get("vehicle_code")
    capacity = record.get("max_load_count") or record.get("seat_count") or 10
    vehicle = Vehicle(
        vehicle_code,
        node.id,
        record.get("vehicle_color") or "#64748b",
        getattr(node, "zone", None),
        capacity=capacity,
    )
    vehicle.time = current_timestamp
    vehicle.vehicle_id = vehicle_code
    vehicle.plate_no = record.get("plate_no") or vehicle_code
    vehicle.driver_id = record.get("current_driver_code") or ""
    vehicle.driver_no = record.get("current_driver_no") or ""
    # vehicle.gps = {
    #     "lon": record.get("current_lon") if record.get("current_lon") is not None else node.lon,
    #     "lat": record.get("current_lat") if record.get("current_lat") is not None else node.lat,
    # }
    vehicle.gps = {
        "lon": node.lon,
        "lat": node.lat,
    }
    vehicle.operation_status = operation_status
    if operation_status == "operating":
        vehicle.rest_status = "operating"
        vehicle.is_resting = False
        vehicle.is_rest_requested = False
    elif operation_status == "resting":
        vehicle.rest_status = "resting"
        vehicle.is_resting = True
        vehicle.is_rest_requested = True
    elif operation_status == "closing":
        vehicle.rest_status = "closing"
        vehicle.is_resting = False
        vehicle.is_rest_requested = True
    return vehicle


def load_fleet_from_persistence(city_map, current_timestamp):
    """从数据库车辆档案加载运行车队。

    Args:
        city_map (CityGraph): 当前路网对象。
        current_timestamp (float): 初始化时统一使用的仿真时间戳。

    Returns:
        list[Vehicle]: 可运行车辆列表；读取失败或没有可用车辆时返回空列表。
    """
    loaded = []
    try:
        for record in persistence.list_vehicles():
            vehicle = _vehicle_from_db_record(record, city_map, current_timestamp)
            if vehicle is not None:
                loaded.append(vehicle)
    except Exception as exc:
        print(f"[State.Init] 数据库车辆加载失败，当前车队置为空：{exc}")
        return []
    return loaded


# ============================================================
# 功能二：系统初始化入口
# 相关方法：init_system
# ============================================================

def init_system(shp_path="shp/dxc_traffic_mars_shp_0606/dxc0606.shp"):
    """加载路网、从数据库读取车队并启动后台匹配引擎。

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
        load_active_operation_restriction_policy()

        current_timestamp = now_timestamp()
        fleet = load_fleet_from_persistence(city, current_timestamp)

        CoreDispatcher.configure_route_grasp_async(state_lock=state_lock, enabled=True)

        for v in fleet:
            CoreDispatcher.refresh_vehicle_route_metadata(v, city)

        CoreDispatcher.completed_orders_pool = []
        system_initialized = True
        persistence.record_initial_state(city, fleet)

    matching_thread = threading.Thread(
        target=CoreDispatcher.process_pool_matching,
        args=(fleet, city, state_lock),
        daemon=True,
        name="OrderMatchingEngine",
    )
    matching_thread.start()
    start_clock_thread()
    start_eta_thread()
