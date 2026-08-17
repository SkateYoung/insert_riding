"""Flask 运行期共享状态。

该模块集中保存路网、车队、后台匹配线程等进程内单例对象。
接口层只读取这些状态，初始化统一由 init_system 完成。
"""

import threading
import time
import random
from datetime import datetime, timedelta, timezone

from . import persistence, reflect_mapping
from .error_logger import log_exception
from .models import CityGraph, Vehicle
from .core import CoreDispatcher


# ============================================================
# 功能一：Flask 进程内共享运行状态与统一业务时间
# 相关变量：city、fleet、matching_thread、clock_thread、eta_thread、route_grasp_thread、system_initialized
# ============================================================

city = None
fleet = None
city_maps = {}
operation_area_records = {}
default_operation_area_id = None
default_operation_area_code = None
fleet_by_area = {}
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
        "operation_restriction_policy_signatures": {
            str(operation_area_id): CoreDispatcher.current_operation_restriction_signature(operation_area_id)
            for operation_area_id in (city_maps or {})
        },
        "default_operation_area_id": None,
        "default_operation_area_code": None,
        "operation_area_count": len(city_maps or {}),
    }


def refresh_runtime_state(current_timestamp=None):
    """按真实 elapsed seconds 推进车辆状态并刷新休息控制。"""
    global clock_last_timestamp, clock_last_dt, clock_tick_count

    with state_lock:
        if not system_initialized or not city_maps or fleet is None:
            return 0.0

        current_timestamp = float(current_timestamp if current_timestamp is not None else now_timestamp())
        previous_timestamp = clock_last_timestamp or current_timestamp
        dt = max(0.0, current_timestamp - previous_timestamp)
        clock_last_timestamp = current_timestamp
        clock_last_dt = dt
        clock_tick_count += 1

        for vehicle in fleet:
            vehicle.tick(dt, current_time=current_timestamp)
        for operation_area_id, area_city in city_maps.items():
            CoreDispatcher.refresh_scheduled_rest_requests(fleet_by_area.get(operation_area_id, []), area_city)
        return dt


def refresh_order_etas_if_due(current_timestamp=None, force=False, service=None):
    """委托 CoreDispatcher 刷新订单 ETA；保留为测试和手动触发入口。"""
    current_timestamp = float(current_timestamp if current_timestamp is not None else now_timestamp())
    if not system_initialized:
        return 0
    if (
        not force
        and CoreDispatcher.eta_last_refresh_timestamp is not None
        and current_timestamp - CoreDispatcher.eta_last_refresh_timestamp < ETA_REFRESH_INTERVAL_SECONDS
    ):
        return 0
    changed = 0
    if not city_maps:
        if city is None:
            return 0
        return CoreDispatcher.refresh_order_etas_if_due(
            fleet or [],
            city,
            state_lock,
            current_timestamp=current_timestamp,
            force=True,
            service=service,
        )
    for operation_area_id, area_city in city_maps.items():
        changed += CoreDispatcher.refresh_order_etas_if_due(
            fleet_by_area.get(operation_area_id, []),
            area_city,
            state_lock,
            current_timestamp=current_timestamp,
            force=True,
            service=service,
        )
    return changed


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
    # CoreDispatcher.configure_route_grasp_async(state_lock=state_lock, enabled=True)
    return None


def load_active_operation_restriction_policy():
    """从持久化层加载当前生效的运营禁区策略。

    Returns:
        dict | None: 当前生效策略；未配置或读取失败时返回 None。
    """
    active_policies = []
    for operation_area_id in city_maps or {}:
        policy = persistence.get_active_operation_restriction_policy(operation_area_id=operation_area_id)
        if policy:
            active_policies.append(policy)
    CoreDispatcher.set_operation_restriction_policies(active_policies)
    return active_policies


def _coerce_operation_area_id(value):
    """把运营区 ID 统一转换为整数。"""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def operation_area_runtime_id(area):
    """读取运营区运行态 ID，优先使用 map_operation_area.area_id。"""
    if not area:
        return None
    return _coerce_operation_area_id(area.get("area_id")) or _coerce_operation_area_id(area.get("id"))


def normalize_operation_area_id(operation_area_id=None):
    """规范化运营区 ID；为空时不再回退默认运营区。"""
    return _coerce_operation_area_id(operation_area_id)


def normalize_operation_area_code(operation_area_code=None):
    """规范化运营区编码；为空时不再回退默认运营区。"""
    operation_area_code = str(operation_area_code or "").strip()
    return operation_area_code or None


def city_for_operation_area(operation_area_id=None):
    """按运营区 ID 读取已加载的路网。"""
    area_id = normalize_operation_area_id(operation_area_id)
    if area_id is not None:
        return city_maps.get(area_id)
    return None


def city_for_vehicle(vehicle):
    """按车辆所属运营区读取已加载的路网。"""
    return city_for_operation_area(getattr(vehicle, "operation_area_id", None))


def fleet_for_operation_area(operation_area_id=None):
    """按运营区 ID 读取运行态车队。"""
    area_id = normalize_operation_area_id(operation_area_id)
    if area_id is not None:
        return fleet_by_area.get(area_id, [])
    return []


def loaded_operation_areas():
    """返回当前已加载运营区概要。"""
    result = []
    for operation_area_id, city_map in (city_maps or {}).items():
        area = operation_area_records.get(operation_area_id) or {}
        result.append({
            "operation_area_id": operation_area_id,
            "code": area.get("code"),
            "name": area.get("name"),
            "shp_path": area.get("shp_path"),
            "is_default": False,
            "nodes": len(getattr(city_map, "nodes_map", {}) or {}),
            "pois": len(getattr(city_map, "pois", []) or []),
            "edges": len(getattr(city_map, "edges", []) or []),
            "fleet_size": len(fleet_by_area.get(operation_area_id, []) or []),
        })
    return result


def _operation_area_can_load_runtime(area):
    """判断运营区是否满足运行态加载条件。"""
    if not area:
        return False
    return (
        str(area.get("status") or "").strip() == "enabled"
        and str(area.get("audit_status") or "").strip() == "approved"
        and bool(str(area.get("shp_path") or "").strip())
    )


def _operation_area_shp_encoding(area):
    """读取运营区 SHP/DBF 编码；为空时使用 utf-8 打底。"""
    return str((area or {}).get("shp_encoding") or "utf-8").strip() or "utf-8"


def _load_operation_area_city(area):
    """加载单个运营区 SHP 并写回加载结果。"""
    operation_area_id = operation_area_runtime_id(area)
    area_code = str(area.get("code") or "").strip()
    shp_path = str(area.get("shp_path") or "").strip()
    if operation_area_id is None:
        raise ValueError("运营区缺少 operation_area_id")
    area_city = CityGraph(shp_path, shp_encoding=_operation_area_shp_encoding(area))
    area_city.operation_area_id = operation_area_id
    area_city.operation_area_code = area_code
    area_city.operation_area = area
    _apply_database_pois(area_city, area)
    bounds = _city_bounds(area_city)
    stats = {
        "load_status": "ready",
        "load_error": None,
        "node_count": len(area_city.nodes_map),
        "edge_count": len(area_city.edges),
        "poi_count": len(area_city.pois),
        "bounds_json": bounds,
        "shp_encoding": getattr(area_city, "shp_encoding", _operation_area_shp_encoding(area)),
    }
    persistence.record_operation_area_load_result(area_code, stats)
    return area_city, {
        "operation_area_id": operation_area_id,
        "code": area_code,
        "name": area.get("name"),
        "shp_path": shp_path,
        "nodes": stats["node_count"],
        "edges": stats["edge_count"],
        "pois": stats["poi_count"],
        "bounds": bounds,
        "shp_encoding": stats["shp_encoding"],
    }


def _ensure_runtime_threads_started():
    """确保多运营区调度相关后台线程已启动。"""
    global matching_thread
    if matching_thread is None or not matching_thread.is_alive():
        matching_thread = threading.Thread(
            target=CoreDispatcher.process_pool_matching,
            args=(fleet, city_maps, state_lock),
            daemon=True,
            name="OrderMatchingEngine",
        )
        matching_thread.start()
    start_clock_thread()
    start_eta_thread()


def load_operation_area_into_runtime(area_or_code):
    """把单个运营区加载进当前运行态。"""
    global city, fleet, system_initialized

    area = (
        persistence.get_operation_area(area_or_code)
        if isinstance(area_or_code, str)
        else dict(area_or_code or {})
    )
    area_code = str((area or {}).get("code") or area_or_code or "").strip()
    operation_area_id = operation_area_runtime_id(area)
    if not area_code:
        return {"status": "skipped", "reason": "operation_area_code_empty"}
    if operation_area_id is None:
        return {"status": "skipped", "code": area_code, "reason": "operation_area_id_empty"}
    if area is None:
        return {"status": "skipped", "code": area_code, "reason": "operation_area_not_found"}
    if not _operation_area_can_load_runtime(area):
        return {"status": "skipped", "code": area_code, "reason": "operation_area_not_active"}

    try:
        area_city, loaded_item = _load_operation_area_city(area)
    except Exception as exc:
        error_text = str(exc)
        log_exception(
            "api.state.load_operation_area",
            exc,
            context={
                "operation_area_id": operation_area_id,
                "operation_area_code": area_code,
                "shp_path": (area or {}).get("shp_path"),
            },
        )
        try:
            persistence.record_operation_area_load_result(area_code, {
                "load_status": "error",
                "load_error": error_text,
                "node_count": None,
                "edge_count": None,
                "poi_count": None,
                "bounds_json": None,
            })
        except Exception as write_exc:
            log_exception(
                "api.state.operation_area_load_writeback",
                write_exc,
                context={"operation_area_code": area_code, "load_error": error_text},
            )
            print(f"[State.Area] 运营区 {area_code} 加载失败状态写回失败：{write_exc}")
        return {"status": "error", "code": area_code, "error": error_text}

    with state_lock:
        if fleet is None:
            fleet = []

        old_area_fleet = list(fleet_by_area.get(operation_area_id, []) or [])
        if old_area_fleet:
            fleet[:] = [vehicle for vehicle in fleet if vehicle not in old_area_fleet]

        city_maps[operation_area_id] = area_city
        operation_area_records[operation_area_id] = dict(area)
        active_policy = persistence.get_active_operation_restriction_policy(operation_area_id=operation_area_id)
        CoreDispatcher.set_operation_restriction_policy(active_policy, operation_area_id=operation_area_id)

        city = None

        current_timestamp = now_timestamp()
        area_fleet = load_fleet_from_persistence(area_city, current_timestamp, operation_area_id=operation_area_id)
        fleet_by_area[operation_area_id] = area_fleet
        fleet.extend(area_fleet)

        CoreDispatcher.configure_route_grasp_async(state_lock=state_lock, enabled=True)
        for vehicle in area_fleet:
            CoreDispatcher.refresh_vehicle_route_metadata(vehicle, area_city)
        system_initialized = True

    _ensure_runtime_threads_started()
    return {
        "status": "ready",
        "area": loaded_item,
        "default_operation_area_id": None,
        "default_operation_area_code": None,
        "fleet_size": len(fleet_by_area.get(operation_area_id, []) or []),
    }


def _city_bounds(city_map):
    """计算路网边界。"""
    nodes = list(getattr(city_map, "nodes_map", {}).values())
    if not nodes:
        return None
    lons = [node.lon for node in nodes]
    lats = [node.lat for node in nodes]
    return {
        "min_lon": min(lons),
        "max_lon": max(lons),
        "min_lat": min(lats),
        "max_lat": max(lats),
    }


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


def _node_id_from_coords(lon, lat):
    """按 CityGraph 节点规则生成经纬度节点 ID。"""
    return f"{float(lon):.6f}_{float(lat):.6f}"


def _node_from_reflect_coords(city_map, lon, lat, tolerance=0.0000015):
    """按 reflect 映射坐标查找当前路网中已有节点。"""
    nodes_map = getattr(city_map, "nodes_map", {}) or {}
    try:
        node_id = _node_id_from_coords(lon, lat)
        lon_value = float(lon)
        lat_value = float(lat)
    except (TypeError, ValueError):
        return None

    direct_node = nodes_map.get(node_id)
    if direct_node is not None:
        return direct_node

    best_node = None
    best_dist = float(tolerance) * float(tolerance)
    for node in nodes_map.values():
        dx = lon_value - float(node.lon)
        dy = lat_value - float(node.lat)
        dist = dx * dx + dy * dy
        if dist <= best_dist:
            best_dist = dist
            best_node = node
    return best_node


def _runtime_node_for_poi_record(city_map, record, reflect_index):
    """优先使用 reflect 映射选择 POI 路网节点，失败时回退原始坐标吸附。"""
    lon = record.get("longitude")
    lat = record.get("latitude")
    if lon is None or lat is None:
        return None, None

    reflect_record = reflect_mapping.find_reflect_station(
        reflect_index,
        record.get("poi_name"),
        record.get("areas"),
        record.get("station_direction"),
    )
    if reflect_record is not None:
        reflect_node = _node_from_reflect_coords(
            city_map,
            reflect_record.get("gd_lng"),
            reflect_record.get("gd_lat"),
        )
        reflect_snap_mode = "existing_node"
        if reflect_node is None:
            reflect_node = _nearest_node_from_coords(
                city_map,
                reflect_record.get("gd_lng"),
                reflect_record.get("gd_lat"),
            )
            reflect_snap_mode = "nearest_node"
        if reflect_node is not None:
            metadata = {
                "poi_snap_source": "reflect_csv" if reflect_snap_mode == "existing_node" else "reflect_csv_nearest_node",
                "reflect_snap_mode": reflect_snap_mode,
                "reflect_station_name": reflect_record.get("station_name"),
                "reflect_road_name": reflect_record.get("road_name"),
                "reflect_direction": reflect_record.get("direction"),
                "reflect_lng": reflect_record.get("gd_lng"),
                "reflect_lat": reflect_record.get("gd_lat"),
            }
            return reflect_node, metadata

    fallback_node = _nearest_node_from_coords(city_map, lon, lat)
    if fallback_node is None:
        return None, None
    return fallback_node, {
        "poi_snap_source": "nearest_node",
        "reflect_snap_mode": None,
        "reflect_station_name": None,
        "reflect_road_name": None,
        "reflect_direction": None,
        "reflect_lng": None,
        "reflect_lat": None,
    }


def _random_poi_node(city_map):
    """从当前路网 POI 中随机选择一个车辆起始节点。"""
    pois = list(getattr(city_map, "pois", []) or [])
    if not pois:
        return None
    return runtime_random.choice(pois)


def _operation_area_poi_ids(operation_area):
    """提取可用于匹配 map_poi.operation_area_id 的运营区 ID。"""
    ids = []
    if not operation_area:
        return ids
    for key in ("id", "area_id"):
        raw_value = operation_area.get(key)
        if raw_value in (None, ""):
            continue
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            continue
        if value not in ids:
            ids.append(value)
    return ids


def _apply_database_pois(city_map, operation_area):
    """使用数据库站点替换当前运营区 POI，并吸附到最近路网节点。"""
    if isinstance(operation_area, dict):
        area = dict(operation_area)
    else:
        area = persistence.get_operation_area(operation_area)
    operation_area_code = str((area or {}).get("code") or "").strip()
    operation_area_ids = _operation_area_poi_ids(area)

    for node in getattr(city_map, "pois", []) or []:
        node.is_poi = False
        node.poi_code = None
        node.station_id = None
        node.operation_area_id = None
        node.operation_area_code = None
        node.poi_snap_source = None
        node.reflect_snap_mode = None
        node.reflect_station_name = None
        node.reflect_road_name = None
        node.reflect_direction = None
        node.reflect_lng = None
        node.reflect_lat = None
    city_map.pois = []

    if not operation_area_ids:
        print(f"[State.Init] 运营区 {operation_area_code or 'unknown'} 缺少可匹配 map_poi.operation_area_id 的 ID，未加载 POI。")
        return 0

    try:
        poi_records = persistence.list_pois(operation_area_ids=operation_area_ids)
    except Exception as exc:
        log_exception(
            "api.state.apply_database_pois",
            exc,
            context={
                "operation_area_code": operation_area_code,
                "operation_area_ids": operation_area_ids,
            },
        )
        print(f"[State.Init] 运营区 {operation_area_code or operation_area_ids} 站点读取失败，当前运营区不加载 POI：{exc}")
        return 0
    if not poi_records:
        return 0

    reflect_index = reflect_mapping.load_reflect_station_index()
    snapped = []
    mapping_results = []
    seen_ids = set()
    for record in poi_records:
        node, snap_metadata = _runtime_node_for_poi_record(city_map, record, reflect_index)
        if node is None or node.id in seen_ids:
            continue
        node.is_poi = True
        node.name = record.get("poi_name") or record.get("station_name") or record.get("poi_code") or node.name
        node.station_id = record.get("station_id")
        node.poi_code = record.get("poi_code")
        node.operation_area_id = record.get("operation_area_id")
        node.operation_area_code = operation_area_code
        for key, value in (snap_metadata or {}).items():
            setattr(node, key, value)
        snapped.append(node)
        seen_ids.add(node.id)
        mapping_results.append({
            "poi_code": record.get("poi_code"),
            "poi_name": record.get("poi_name") or record.get("station_name"),
            "areas": record.get("areas"),
            "station_direction": record.get("station_direction"),
            "database_lng": record.get("longitude"),
            "database_lat": record.get("latitude"),
            "snap_source": getattr(node, "poi_snap_source", None),
            "reflect_snap_mode": getattr(node, "reflect_snap_mode", None),
            "reflect_direction": getattr(node, "reflect_direction", None),
            "reflect_lng": getattr(node, "reflect_lng", None),
            "reflect_lat": getattr(node, "reflect_lat", None),
            "snapped_node_id": node.id,
            "snapped_lng": node.lon,
            "snapped_lat": node.lat,
        })
    city_map.poi_mapping_results = mapping_results
    if snapped:
        city_map.pois = snapped
    source_counts = {}
    for item in mapping_results:
        source = item.get("snap_source") or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
        print(
            "[State.POIMap] "
            f"area={operation_area_code or operation_area_ids} "
            f"poi={item.get('poi_name') or item.get('poi_code')} "
            f"road={item.get('areas')} "
            f"direction={item.get('station_direction')} "
            f"source={item.get('snap_source')} "
            f"mode={item.get('reflect_snap_mode')} "
            f"reflect_direction={item.get('reflect_direction')} "
            f"db=({item.get('database_lng')},{item.get('database_lat')}) "
            f"reflect=({item.get('reflect_lng')},{item.get('reflect_lat')}) "
            f"node={item.get('snapped_node_id')} "
            f"node_coord=({item.get('snapped_lng')},{item.get('snapped_lat')})"
        )
    print(
        f"[State.POIMap] 运营区 {operation_area_code or operation_area_ids} "
        f"POI 映射完成：loaded={len(snapped)}, source_counts={source_counts}"
    )
    return len(snapped)


def _vehicle_from_db_record(record, city_map, current_timestamp, operation_area_id=None):
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

    current_lon = record.get("current_lon")
    current_lat = record.get("current_lat")
    if current_lon is None or current_lat is None:
        return None
    try:
        current_lon = float(current_lon)
        current_lat = float(current_lat)
    except (TypeError, ValueError):
        return None

    node = _nearest_node_from_coords(city_map, current_lon, current_lat)
    if node is None:
        return None
    last_node = city_map.nodes_map.get(record.get("last_node_code")) or node
    next_node = city_map.nodes_map.get(record.get("next_node_code")) or node

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
    vehicle.operation_area_id = operation_area_id or record.get("operation_area_id")
    vehicle.operation_area_code = record.get("operation_area_code") or ""
    vehicle.driver_id = record.get("current_driver_code") or ""
    vehicle.driver_no = record.get("current_driver_no") or ""
    vehicle.gps = {
        "lon": current_lon,
        "lat": current_lat,
    }
    vehicle.last_node = (last_node or node).id
    vehicle.next_node = (next_node or node).id
    try:
        vehicle.progress = float(record.get("edge_progress") or 0.0)
    except (TypeError, ValueError):
        vehicle.progress = 0.0
    vehicle.operation_status = operation_status
    vehicle.operation_mode = record.get("operation_mode") or "dynamic_bus"
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


def load_fleet_from_persistence(city_map, current_timestamp, operation_area_id=None):
    """从数据库车辆档案加载运行车队。

    Args:
        city_map (CityGraph): 当前路网对象。
        current_timestamp (float): 初始化时统一使用的仿真时间戳。

    Returns:
        list[Vehicle]: 可运行车辆列表；读取失败或没有可用车辆时返回空列表。
    """
    loaded = []
    expected_area_id = _coerce_operation_area_id(operation_area_id)
    try:
        for record in persistence.list_vehicles():
            record_area_id = _coerce_operation_area_id(record.get("operation_area_id"))
            if expected_area_id is not None and record_area_id != expected_area_id:
                continue
            vehicle = _vehicle_from_db_record(
                record,
                city_map,
                current_timestamp,
                operation_area_id=record_area_id,
            )
            if vehicle is not None:
                loaded.append(vehicle)
    except Exception as exc:
        log_exception(
            "api.state.load_fleet_from_persistence",
            exc,
            context={"operation_area_id": expected_area_id},
        )
        print(f"[State.Init] 数据库车辆加载失败，当前车队置为空：{exc}")
        return []
    return loaded


# ============================================================
# 功能二：系统初始化入口
# 相关方法：init_system
# ============================================================

def _legacy_init_system(shp_path="shp/tianhe_shp/zjgc_osm.shp"):
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


def init_system(shp_path=None):
    """从数据库生效运营区加载一个或多个 SHP 路网并启动后台调度。"""
    global city, fleet, matching_thread, system_initialized
    global city_maps, operation_area_records, default_operation_area_id, default_operation_area_code, fleet_by_area

    loaded_areas = []
    failed_areas = []

    with state_lock:
        startup_areas = persistence.list_startup_operation_areas()
        if not startup_areas:
            city = None
            fleet = []
            city_maps = {}
            operation_area_records = {}
            default_operation_area_id = None
            default_operation_area_code = None
            fleet_by_area = {}
            CoreDispatcher.set_operation_restriction_policies([])
            system_initialized = False
            return {
                "status": "no_operation_area",
                "message": "数据库中没有可加载的生效运营区。",
                "loaded_areas": [],
                "failed_areas": [],
            }

        new_city_maps = {}
        new_area_records = {}
        for area in startup_areas:
            operation_area_id = operation_area_runtime_id(area)
            area_code = str(area.get("code") or "").strip()
            area_shp_path = str(area.get("shp_path") or "").strip()
            if operation_area_id is None or not area_code or not area_shp_path:
                continue
            try:
                area_city = CityGraph(area_shp_path, shp_encoding=_operation_area_shp_encoding(area))
                area_city.operation_area_id = operation_area_id
                area_city.operation_area_code = area_code
                area_city.operation_area = area
                _apply_database_pois(area_city, area)
                bounds = _city_bounds(area_city)
                stats = {
                    "load_status": "ready",
                    "load_error": None,
                    "node_count": len(area_city.nodes_map),
                    "edge_count": len(area_city.edges),
                    "poi_count": len(area_city.pois),
                    "bounds_json": bounds,
                    "shp_encoding": getattr(area_city, "shp_encoding", _operation_area_shp_encoding(area)),
                }
                persistence.record_operation_area_load_result(area_code, stats)
                loaded_item = {
                    "operation_area_id": operation_area_id,
                    "code": area_code,
                    "name": area.get("name"),
                    "shp_path": area_shp_path,
                    "nodes": stats["node_count"],
                    "edges": stats["edge_count"],
                    "pois": stats["poi_count"],
                    "bounds": bounds,
                    "shp_encoding": stats["shp_encoding"],
                }
                loaded_areas.append(loaded_item)
                new_city_maps[operation_area_id] = area_city
                new_area_records[operation_area_id] = dict(area)
            except Exception as exc:
                error_text = str(exc)
                log_exception(
                    "api.state.init_system.load_operation_area",
                    exc,
                    context={
                        "operation_area_id": operation_area_id,
                        "operation_area_code": area_code,
                        "shp_path": area_shp_path,
                    },
                )
                failed_areas.append({
                    "code": area_code,
                    "name": area.get("name"),
                    "shp_path": area_shp_path,
                    "error": error_text,
                })
                try:
                    persistence.record_operation_area_load_result(area_code, {
                        "load_status": "error",
                        "load_error": error_text,
                        "node_count": None,
                        "edge_count": None,
                        "poi_count": None,
                        "bounds_json": None,
                    })
                except Exception as write_exc:
                    log_exception(
                        "api.state.init_system.load_writeback",
                        write_exc,
                        context={"operation_area_code": area_code, "load_error": error_text},
                    )
                    print(f"[State.Init] 运营区 {area_code} 加载失败状态写回失败：{write_exc}")

        if not new_city_maps:
            city = None
            fleet = []
            city_maps = {}
            operation_area_records = {}
            default_operation_area_id = None
            default_operation_area_code = None
            fleet_by_area = {}
            CoreDispatcher.set_operation_restriction_policies([])
            system_initialized = False
            return {
                "status": "operation_area_load_failed",
                "message": "所有生效运营区 SHP 均加载失败。",
                "loaded_areas": [],
                "failed_areas": failed_areas,
            }

        city_maps = new_city_maps
        operation_area_records = new_area_records
        default_operation_area_id = None
        default_operation_area_code = None
        city = None
        load_active_operation_restriction_policy()

        current_timestamp = now_timestamp()
        fleet_by_area = {}
        all_fleet = []
        for operation_area_id, area_city in city_maps.items():
            area_fleet = load_fleet_from_persistence(area_city, current_timestamp, operation_area_id=operation_area_id)
            fleet_by_area[operation_area_id] = area_fleet
            all_fleet.extend(area_fleet)
        fleet = all_fleet

        CoreDispatcher.configure_route_grasp_async(state_lock=state_lock, enabled=True)

        for operation_area_id, area_fleet in fleet_by_area.items():
            area_city = city_maps[operation_area_id]
            for vehicle in area_fleet:
                CoreDispatcher.refresh_vehicle_route_metadata(vehicle, area_city)

        CoreDispatcher.completed_orders_pool = []
        system_initialized = True
        persistence.record_initial_state(None, fleet)

    matching_thread = threading.Thread(
        target=CoreDispatcher.process_pool_matching,
        args=(fleet, city_maps, state_lock),
        daemon=True,
        name="OrderMatchingEngine",
    )
    matching_thread.start()
    start_clock_thread()
    start_eta_thread()
    return {
        "status": "initialized",
        "loaded_areas": loaded_areas,
        "failed_areas": failed_areas,
        "default_operation_area_id": None,
        "default_operation_area_code": None,
        "nodes": sum(item["nodes"] for item in loaded_areas),
        "pois": sum(item["pois"] for item in loaded_areas),
        "edges": sum(item["edges"] for item in loaded_areas),
    }
