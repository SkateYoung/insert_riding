"""Flask API 路由层。

本模块只负责 HTTP 请求解析、参数校验和 JSON 响应组装。
调度、寻路、预测等业务逻辑统一委托给 api.core.CoreDispatcher。
"""

from flask import Blueprint, jsonify, request

from . import state
from . import persistence
from .auxiliary import AuxiliaryFunctions
from .core import CoreDispatcher
from .models import CityGraph, Order, SPEED_MPS, Vehicle
from .restrictions import OperationRestrictionError, normalize_policy_payload, policy_to_response


bp = Blueprint("api_routes", __name__)

REST_STATUS_TEXT = {
    "operating": "运营中",
    "preparing_closure": "准备收车中",
    "closing": "收车中",
    "resting": "休息中",
    "offline": "离线",
    "maintenance": "维修中",
}

DRIVER_EMPLOYMENT_STATUSES = ("active", "inactive", "blocked")
DRIVER_WORK_STATUSES = ("off_duty", "listening", "serving", "resting")
VEHICLE_OPERATION_STATUSES = ("operating", "resting", "closing", "offline", "maintenance")
VEHICLE_RUNTIME_STATUSES = {"operating", "resting", "closing"}
VEHICLE_TYPES = ("bus", "large_bus", "mid_bus", "small_bus")


# ============================================================
# 功能一：接口通用请求解析与响应格式转换
# 相关方法：_parse_datetime、_parse_optional_rest_time、_vehicle_to_dict
# ============================================================

def _parse_datetime(value, field_name):
    """解析接口传入的业务时间字符串。

    Args:
        value (str): 形如 "2026-02-28 08:30:15" 的时间字符串。
        field_name (str): 字段名，用于错误提示。

    Returns:
        datetime: 解析后的时间对象。

    Raises:
        ValueError: 字段缺失或格式无法解析。
    """
    if not value:
        raise ValueError(f"{field_name} 不能为空")
    try:
        return state.parse_business_datetime(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是 YYYY-MM-DD HH:MM:SS 格式") from exc


def _parse_optional_rest_time(value, vehicle):
    """把司机期望休息时间转成车辆仿真时间点。

    Args:
        value (str | int | float | None): 为空表示马上休息；数字表示从当前后端真实时间起的秒数；
            字符串按真实时间解析后折算成距离当前的秒数。
        vehicle (Vehicle): 当前车辆参数，保留用于接口签名稳定。

    Returns:
        float | None: 期望休息的车辆仿真时间点。
    """
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return state.now_timestamp() + max(0.0, float(value))

    rest_at = _parse_datetime(value, "desired_rest_time")
    return state.datetime_to_timestamp(rest_at)


def _parse_optional_event_timestamp(value):
    """解析可选业务事件时间；为空时返回当前业务时间戳。"""
    if value in (None, ""):
        return state.now_timestamp()
    return state.datetime_to_timestamp(_parse_datetime(value, "occurred_at"))


def _normalize_order_query_filters(data):
    """规范化订单管理查询条件。"""
    if not isinstance(data, dict):
        raise ValueError("请求体必须是 JSON 对象")
    filters = dict(data)
    created_at = filters.get("created_at")
    if created_at in (None, ""):
        return filters
    if not isinstance(created_at, dict):
        raise ValueError("created_at 必须是对象")
    normalized_created_at = {}
    for key in ("start", "end"):
        value = created_at.get(key)
        if value in (None, ""):
            continue
        normalized_created_at[key] = _parse_datetime(value, f"created_at.{key}")
    filters["created_at"] = normalized_created_at
    return filters


def _vehicle_to_dict(v):
    """将 Vehicle 对象转为接口可返回的 JSON 字典。

    Args:
        v (Vehicle): 运行期车辆对象。

    Returns:
        dict: 包含车辆身份、载客状态、订单计划、轨迹点和空车预测信息的快照。
    """
    return {
        "id": v.id,
        "color": v.color,
        "zone": v.op_zone,
        "capacity": v.capacity,
        "driver_id": v.driver_id,
        "driver_no": v.driver_no,
        "vehicle_id": v.vehicle_id,
        "plate_no": v.plate_no,
        "operation_area_id": getattr(v, "operation_area_id", None),
        "operation_area_code": getattr(v, "operation_area_code", None),
        "time": v.time,
        "time_text": state.format_timestamp(v.time),
        "on_board_count": sum(o.passenger_count for o in v.on_board_orders),
        "on_board_orders": [o.request_id for o in v.on_board_orders],
        "gps": v.gps,
        "idle_target": v.idle_target,
        "idle_forecast": v.idle_forecast,
        "idle_target_eta_seconds": getattr(v, "idle_target_eta_seconds", None),
        "idle_target_eta_time": getattr(v, "idle_target_eta_time", None),
        "idle_target_eta_time_text": (
            state.format_timestamp(v.idle_target_eta_time)
            if getattr(v, "idle_target_eta_time", None) is not None
            else None
        ),
        "idle_target_eta_status": getattr(v, "idle_target_eta_status", None),
        "idle_target_eta_error": getattr(v, "idle_target_eta_error", None),
        "planned_route": [
            {
                "type": s["type"],
                "request_id": s["order"].request_id,
                "node_name": (
                    s["order"].o_node.name
                    if s["type"] == "O"
                    else s["order"].d_node.name
                ),
                "target_node": CoreDispatcher._node_to_path_point(
                    s["order"].o_node
                    if s["type"] == "O"
                    else s["order"].d_node
                ),
            }
            for s in v.planned_route
        ],
        "planned_route_point": v.planned_route_point,
        "planned_route_grasped_point": getattr(v, "planned_route_grasped_point", []),
        "planned_route_segment_grasped_point": getattr(v, "planned_route_segment_grasped_point", []),
        "planned_route_grasp_status": getattr(v, "planned_route_grasp_status", None),
        "planned_route_grasp_error": getattr(v, "planned_route_grasp_error", None),
        "planned_route_grasp_route_version": getattr(v, "planned_route_grasp_route_version", None),
        "operation_restriction_policy_signature": getattr(v, "operation_restriction_policy_signature", None),
        "last_node": v.last_node,
        "next_node": v.next_node,
        "progress": v.progress,
        "driving_time": v.driving_time,
        "is_resting": v.is_resting,
        "is_rest_requested": v.is_rest_requested,
        "rest_status": getattr(v, "rest_status", "operating"),
        "rest_status_text": REST_STATUS_TEXT.get(getattr(v, "rest_status", "operating"), "未知"),
        "operation_status": getattr(v, "operation_status", getattr(v, "rest_status", "operating")),
        "desired_rest_time": getattr(v, "desired_rest_time", None),
        "desired_rest_time_text": (
            state.format_timestamp(v.desired_rest_time)
            if getattr(v, "desired_rest_time", None) is not None
            else None
        ),
        "rest_duration": getattr(v, "rest_duration", None),
        "rest_duration_minutes": (
            round(v.rest_duration / 60.0, 2)
            if getattr(v, "rest_duration", None) is not None
            else None
        ),
        "max_continuous_driving_seconds": getattr(v, "max_continuous_driving_seconds", None),
        "max_continuous_driving_minutes": (
            round(v.max_continuous_driving_seconds / 60.0, 2)
            if getattr(v, "max_continuous_driving_seconds", None) is not None
            else None
        ),
        "rest_timer": getattr(v, "rest_timer", 0.0),
        "rest_started_time": getattr(v, "rest_started_time", None),
        "rest_started_time_text": (
            state.format_timestamp(v.rest_started_time)
            if getattr(v, "rest_started_time", None) is not None
            else None
        ),
        "can_accept_order": CoreDispatcher._vehicle_can_accept_order(v),
    }


def _path_segment_to_dict(segment):
    """将内部路径分段转成路径更新接口的精简分段结构。"""
    item = {
        "type": segment.get("type"),
        "request_id": segment.get("request_id"),
        "target": segment.get("target_node"),
        "distance": segment.get("distance"),
        "points": segment.get("path", []),
    }
    if "forecast" in segment:
        item["forecast"] = segment["forecast"]
    return item


def _path_result_to_response(vehicle, path_result):
    """组装 /fleet/<vehicle_id>/path 的对外响应结构。

    CoreDispatcher 返回的是内部计算结构；HTTP 层在这里统一压缩命名、
    去掉重复字段，并保留少量过渡期兼容字段。
    """
    route_points = path_result.get("path", [])
    snapped_point = path_result.get("snapped_point") or {}
    snap_edge = snapped_point.get("edge") or {}
    snap_point = {
        "id": snapped_point.get("id"),
        "lon": snapped_point.get("lon"),
        "lat": snapped_point.get("lat"),
        "name": snapped_point.get("name"),
        "zone": snapped_point.get("zone"),
        "edge_u": snap_edge.get("u"),
        "edge_v": snap_edge.get("v"),
        "progress": snapped_point.get("progress"),
        "is_projection": True,
    }

    return {
        "vehicle": {
            "id": vehicle.id,
            "vehicle_id": vehicle.vehicle_id,
        },
        "gps": path_result.get("gps"),
        "reported_gps": path_result.get("reported_gps"),
        "snap": {
            "point": snap_point,
            "edge": snap_edge,
            "progress": snapped_point.get("progress"),
            "distance_to_gps": snapped_point.get("distance_to_gps"),
            "source": snapped_point.get("snap_source"),
            "next_node": snapped_point.get("next_node"),
            "raw_point": path_result.get("reported_gps"),
        },
        "route": {
            "points": route_points,
            "distance": path_result.get("total_distance", 0.0),
            "planned_step_count": path_result.get("planned_route_size", 0),
            "segments": [
                _path_segment_to_dict(segment)
                for segment in path_result.get("segments", [])
            ],
        },
        "events": path_result.get("changed_steps", []),
        "orders": {
            "on_board": path_result.get("on_board_orders", []),
            "remaining": path_result.get("planned_route", []),
        },
        "path": route_points,
        "snapped_point": snapped_point,
    }


def _format_optional_timestamp(timestamp_value):
    """将可选时间戳转成展示文本。"""
    if timestamp_value is None:
        return None
    try:
        return state.format_timestamp(timestamp_value)
    except (TypeError, ValueError, OSError):
        return None


def _order_node_to_dict(node):
    """将订单起终点节点转成乘客端返回结构。"""
    return {
        "name": node.name if node else None,
        "lon": node.lon if node else None,
        "lat": node.lat if node else None,
    }


def _restriction_policy_response(policy):
    """把禁区策略统一转换成接口响应结构。"""
    return policy_to_response(policy)


def _sync_active_restriction_policy(policy, operation_area_id=None):
    """同步进程内当前禁区策略，并返回响应结构。"""
    area_id = operation_area_id
    if area_id is None and policy:
        area_id = policy.get("operation_area_id")
    if area_id is None:
        return _restriction_policy_response(policy)
    CoreDispatcher.set_operation_restriction_policy(policy, operation_area_id=area_id)
    return _restriction_policy_response(policy)


def _nearest_node_from_coords(city_map, lon, lat):
    """根据经纬度查找最近的路网节点。"""
    best_node = None
    best_dist = float("inf")
    for node in city_map.nodes_map.values():
        dist = AuxiliaryFunctions.haversine_distance(float(lon), float(lat), node.lon, node.lat)
        if dist < best_dist:
            best_node = node
            best_dist = dist
    return best_node, best_dist


def _route_test_node(city_map, payload, key):
    """解析路线测试起终点，并吸附到路网节点。"""
    node_id = payload.get(f"{key}_node_id") or payload.get(f"{key}NodeId")
    if node_id:
        node = city_map.nodes_map.get(str(node_id))
        if node is None:
            raise ValueError(f"{key}_node_id 未找到")
        return node, 0.0

    point = payload.get(key) or {}
    lon = point.get("lon", point.get("lng", point.get("longitude")))
    lat = point.get("lat", point.get("latitude"))
    if lon is None or lat is None:
        raise ValueError(f"{key} 必须包含 lon/lat 或 {key}_node_id")
    node, dist = _nearest_node_from_coords(city_map, float(lon), float(lat))
    if node is None:
        raise ValueError(f"{key} 无法吸附到路网节点")
    return node, dist


def _json_error(message, status=400, **extra):
    """生成统一的 JSON 错误响应。

    Args:
        message (str): 对外返回的错误信息。
        status (int): HTTP 状态码。
        **extra: 需要附加到响应体中的扩展字段。

    Returns:
        tuple: Flask 响应对象与 HTTP 状态码。
    """
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


class StationRequestError(ValueError):
    """站点管理接口的可细分请求错误。"""

    def __init__(self, message, code, status=400, field=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field


def _station_error_payload(code, message, field=None, **extra):
    """组装站点管理接口错误响应体。"""
    payload = {"error": code, "code": code, "message": message}
    if field:
        payload["field"] = field
    payload.update(extra)
    return payload


def _station_error_response(code, message, status=400, field=None, **extra):
    """生成站点管理接口错误响应。"""
    return jsonify(_station_error_payload(code, message, field=field, **extra)), status


def _station_request_items(data):
    """兼容单站点对象和 stations 批量数组。"""
    if not isinstance(data, dict):
        raise StationRequestError("请求体必须是 JSON 对象", "invalid_json_body")
    if "stations" not in data:
        return [data]
    stations = data.get("stations")
    if not isinstance(stations, list) or not stations:
        raise StationRequestError("stations 必须是非空数组", "stations_required", field="stations")
    for index, item in enumerate(stations):
        if not isinstance(item, dict):
            raise StationRequestError(f"stations[{index}] 必须是 JSON 对象", "invalid_json_body", field=f"stations[{index}]")
    return stations


def _station_required_int(item, field):
    """读取站点请求中的必填整数字段。"""
    value = item.get(field)
    if value in (None, ""):
        raise StationRequestError("缺少 operation_area_id", "operation_area_id_required", field=field)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise StationRequestError("operation_area_id 必须是整数", "operation_area_id_invalid", field=field) from exc


def _station_optional_int(item, field):
    """读取站点请求中的可选整数字段。"""
    value = item.get(field)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise StationRequestError(f"{field} 必须是整数", f"{field}_invalid", field=field) from exc


def _station_coordinate(item, names, required_code, invalid_code):
    """读取并校验站点经纬度字段。"""
    raw = None
    field = names[0]
    for name in names:
        if item.get(name) not in (None, ""):
            raw = item.get(name)
            field = name
            break
    if raw in (None, ""):
        raise StationRequestError("缺少经纬度坐标", required_code, field=field)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise StationRequestError("经纬度必须是数字", invalid_code, field=field) from exc
    return value


def _validate_station_coordinate_range(lon, lat):
    """校验经纬度范围。"""
    if lon < -180 or lon > 180:
        raise StationRequestError("经度超出合法范围", "station_coordinate_out_of_range", field="lon")
    if lat < -90 or lat > 90:
        raise StationRequestError("纬度超出合法范围", "station_coordinate_out_of_range", field="lat")


def _normalize_station_create_payload(item):
    """规范化新增站点请求项。"""
    operation_area_id = _station_required_int(item, "operation_area_id")
    station_name = str(item.get("station_name") or item.get("poi_name") or "").strip()
    if not station_name:
        raise StationRequestError("缺少站点名称", "station_name_required", field="station_name")
    lon = _station_coordinate(item, ("lon", "lng", "longitude"), "station_lon_required", "station_lon_invalid")
    lat = _station_coordinate(item, ("lat", "latitude"), "station_lat_required", "station_lat_invalid")
    _validate_station_coordinate_range(lon, lat)
    payload = dict(item)
    payload.update({
        "operation_area_id": operation_area_id,
        "station_name": station_name,
        "lon": lon,
        "lat": lat,
        "station_id": _station_optional_int(item, "station_id"),
        "dept_id": _station_optional_int(item, "dept_id"),
        "direction_angle": _station_optional_int(item, "direction_angle"),
    })
    return payload


def _normalize_station_delete_payload(item):
    """规范化删除站点请求项。"""
    lon = _station_coordinate(item, ("lon", "lng", "longitude"), "station_lon_required", "station_lon_invalid")
    lat = _station_coordinate(item, ("lat", "latitude"), "station_lat_required", "station_lat_invalid")
    _validate_station_coordinate_range(lon, lat)
    operation_area_id = None
    if item.get("operation_area_id") not in (None, ""):
        operation_area_id = _station_required_int(item, "operation_area_id")
    return {
        "lon": lon,
        "lat": lat,
        "operation_area_id": operation_area_id,
    }


def _station_exception_result(index, exc, fallback_code="station_operation_failed"):
    """把单条站点操作异常转换为批量结果项。"""
    if isinstance(exc, StationRequestError):
        status = exc.status
        payload = _station_error_payload(exc.code, str(exc), field=exc.field)
    elif isinstance(exc, persistence.PersistenceUnavailable):
        status = 503
        payload = _station_error_payload("database_unavailable", str(exc) or "数据库不可用")
    elif isinstance(exc, persistence.PersistenceConflict):
        status = 409
        payload = _station_error_payload(exc.code, str(exc), field=exc.field)
    elif isinstance(exc, KeyError) and str(exc).strip("'") == "operation_area_not_found":
        status = 404
        payload = _station_error_payload("operation_area_not_found", "运营区不存在", field="operation_area_id")
    else:
        status = 500
        payload = _station_error_payload(fallback_code, str(exc))
    payload.update({"index": index, "success": False, "status": status})
    return payload


def _station_batch_status(results, success_status):
    """根据逐项结果确定批量接口 HTTP 状态码。"""
    success_count = sum(1 for item in results if item.get("success"))
    if success_count == len(results):
        return success_status
    if success_count > 0:
        return 207
    statuses = [int(item.get("status") or 400) for item in results]
    if 503 in statuses:
        return 503
    if 500 in statuses:
        return 500
    if all(status == 404 for status in statuses):
        return 404
    if all(status == 409 for status in statuses):
        return 409
    return 400


def _refresh_station_runtime_areas(operation_area_ids):
    """新增或删除站点后刷新已加载运营区的 POI。"""
    refreshed = []
    skipped = []
    for area_id in sorted({int(item) for item in operation_area_ids if item not in (None, "")}):
        try:
            city_map = (state.city_maps or {}).get(area_id)
            area = _operation_area_by_area_id(area_id)
            if city_map is None or area is None:
                skipped.append({"operation_area_id": area_id, "reason": "operation_area_not_loaded"})
                continue
            poi_count = state._apply_database_pois(city_map, area)
            refreshed.append({"operation_area_id": area_id, "poi_count": poi_count})
        except Exception as exc:
            skipped.append({
                "operation_area_id": area_id,
                "reason": "runtime_refresh_failed",
                "message": str(exc),
            })
    return {
        "refreshed": refreshed,
        "skipped": skipped,
        "runtime_refreshed": bool(refreshed) and not skipped,
    }


def _preflight_operation_area_runtime_load(area):
    """新增运营区入库前预检查 SHP 是否可进入运行态。"""
    operation_area_id = _optional_int(area, "area_id")
    area_code = str((area or {}).get("code") or "").strip()
    shp_path = str((area or {}).get("shp_path") or "").strip()
    if operation_area_id is None:
        return {"status": "skipped", "reason": "operation_area_id_empty"}
    if not area_code:
        return {"status": "skipped", "reason": "operation_area_code_empty"}
    if not shp_path:
        return {"status": "skipped", "reason": "shp_path_empty"}
    if (
        str((area or {}).get("status") or "").strip() != "enabled"
        or str((area or {}).get("audit_status") or "").strip() != "approved"
    ):
        return {"status": "skipped", "reason": "operation_area_not_active"}
    shp_encoding = str((area or {}).get("shp_encoding") or "utf-8").strip() or "utf-8"
    city_map = CityGraph(shp_path, shp_encoding=shp_encoding)
    area["shp_encoding"] = getattr(city_map, "shp_encoding", shp_encoding)
    poi_count = state._apply_database_pois(city_map, area)
    bounds = state._city_bounds(city_map)
    return {
        "status": "ready",
        "operation_area_id": operation_area_id,
        "code": area_code,
        "node_count": len(city_map.nodes_map),
        "edge_count": len(city_map.edges),
        "poi_count": poi_count,
        "bounds_json": bounds,
        "shp_encoding": getattr(city_map, "shp_encoding", shp_encoding),
    }


def _request_operation_area_id(data=None):
    """读取请求中的运营区 ID；为空时不再使用默认运营区。"""
    data = data or {}
    raw_area_id = (
        request.args.get("operation_area_id")
        or data.get("operation_area_id")
    )
    if raw_area_id in (None, ""):
        return None
    try:
        return int(raw_area_id)
    except (TypeError, ValueError):
        return None


def _city_for_operation_area_or_error(operation_area_id=None):
    """读取运营区对应路网；不存在时返回错误响应。"""
    if operation_area_id in (None, ""):
        return None, _json_error("缺少 operation_area_id", 400, operation_area_id=None)
    try:
        area_id = int(operation_area_id)
    except (TypeError, ValueError):
        return None, _json_error("operation_area_id 必须是整数", 400, operation_area_id=operation_area_id)
    city_map = (state.city_maps or {}).get(area_id)
    if city_map is None:
        return None, _json_error("运营区未加载或不存在", 404, operation_area_id=area_id)
    return city_map, None


def _city_for_vehicle(vehicle):
    """读取车辆所属运营区对应路网。"""
    return state.city_for_vehicle(vehicle)


OPERATION_AREA_CREATE_REQUIRED_FIELDS = (
    "area_id",
    "org_id",
    "dept_id",
    "org_code",
    "org_name",
    "name",
    "code",
    "status",
    "city_code",
    "city_name",
    "country_code",
    "country_name",
    "shp_path",
    "load_on_startup",
)


def _operation_area_value(data, field):
    """读取运营区字段，兼容 county/country 命名。"""
    if field == "country_code":
        return data.get("country_code", data.get("county_code"))
    if field == "country_name":
        return data.get("country_name", data.get("county_name"))
    return data.get(field)


def _normalize_operation_area_payload(data, *, existing_code=None, require_create_fields=False):
    """规范化运营区管理请求体。"""
    payload = dict(data or {})
    code = str(existing_code or payload.get("code") or "").strip()
    if not code:
        raise ValueError("code 不能为空")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("name 不能为空")
    if require_create_fields:
        missing_fields = []
        for field in OPERATION_AREA_CREATE_REQUIRED_FIELDS:
            value = _operation_area_value(payload, field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)
        if missing_fields:
            raise ValueError(f"运营区创建缺少必填字段：{', '.join(missing_fields)}")
    status = str(payload.get("status") or "pending").strip()
    audit_status = str(payload.get("audit_status") or "pending").strip()
    if status not in {"pending", "disabled", "enabled", "rejected"}:
        raise ValueError("status 必须是 pending/disabled/enabled/rejected 之一")
    if audit_status not in {"pending", "approved", "rejected"}:
        raise ValueError("audit_status 必须是 pending/approved/rejected 之一")
    payload["code"] = code
    payload["name"] = name
    payload["status"] = status
    payload["audit_status"] = audit_status
    payload["load_on_startup"] = payload.get("load_on_startup", 1)
    payload["county_code"] = _operation_area_value(payload, "country_code")
    payload["county_name"] = _operation_area_value(payload, "country_name")
    payload["shp_encoding"] = str(payload.get("shp_encoding") or "utf-8").strip() or "utf-8"
    payload["coord_system"] = str(payload.get("coord_system") or "gcj02").strip()
    return payload


def _normalize_driver_payload(data, *, existing_code=None):
    """校验并规范化司机档案请求体。

    Args:
        data (dict): 前端传入的司机档案字段。
        existing_code (str | None): 更新接口路径中的司机编码；传入时以该值为准。

    Returns:
        dict: 可直接写入持久化层的司机档案字段。

    Raises:
        ValueError: 必填字段缺失或枚举值非法。
    """
    payload = dict(data or {})
    driver_code = str(existing_code or payload.get("driver_code") or "").strip()
    if not driver_code:
        raise ValueError("driver_code 不能为空")
    employment_status = str(payload.get("employment_status") or "active").strip()
    work_status = str(payload.get("work_status") or "off_duty").strip()
    if employment_status not in DRIVER_EMPLOYMENT_STATUSES:
        raise ValueError(f"employment_status 必须是 {', '.join(DRIVER_EMPLOYMENT_STATUSES)} 之一")
    if work_status not in DRIVER_WORK_STATUSES:
        raise ValueError(f"work_status 必须是 {', '.join(DRIVER_WORK_STATUSES)} 之一")
    return {
        "driver_code": driver_code,
        "driver_no": str(payload.get("driver_no") or "").strip() or None,
        "driver_name": str(payload.get("driver_name") or payload.get("driver_no") or driver_code).strip(),
        "phone": str(payload.get("phone") or "").strip() or None,
        "id_card_no": str(payload.get("id_card_no") or "").strip() or None,
        "license_no": str(payload.get("license_no") or "").strip() or None,
        "license_class": str(payload.get("license_class") or "").strip() or None,
        "license_expire_date": payload.get("license_expire_date") or None,
        "service_city": str(payload.get("service_city") or "").strip() or None,
        "employment_status": employment_status,
        "work_status": work_status,
        "remark": str(payload.get("remark") or "").strip() or None,
    }


def _extract_position(data):
    """从请求体中解析车辆经纬度。

    Args:
        data (dict): 车辆请求体，支持 initial_position、position 或顶层 lon/lat。

    Returns:
        dict | None: 解析后的 {"lon": float, "lat": float}；未传位置时返回 None。

    Raises:
        ValueError: 坐标缺失、格式非法或超出经纬度范围。
    """
    point = data.get("initial_position") or data.get("position") or {}
    lon = data.get("lon", data.get("lng", data.get("longitude", point.get("lon", point.get("lng", point.get("longitude"))))))
    lat = data.get("lat", data.get("latitude", point.get("lat", point.get("latitude"))))
    if lon in (None, "") and lat in (None, ""):
        return None
    if lon in (None, "") or lat in (None, ""):
        raise ValueError("车辆位置必须同时包含 lon/lat")
    lon = float(lon)
    lat = float(lat)
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("车辆经纬度超出范围")
    return {"lon": lon, "lat": lat}


def _runtime_payload_from_position(position, operation_status, existing_vehicle=None, operation_area_id=None):
    """把车辆位置和运营状态转换成运行快照字段。

    Args:
        position (dict | None): 车辆经纬度；为空时可复用已有车辆运行位置。
        operation_status (str): 前端指定的车辆运营状态。
        existing_vehicle (dict | None): 数据库中已有车辆档案。

    Returns:
        tuple: (runtime_payload, snap_info)，分别表示可落库的运行字段和吸附结果。

    Raises:
        ValueError: 系统已初始化但车辆位置无法吸附到路网节点。
    """
    rest_status = operation_status if operation_status in {"resting", "closing"} else "operating"
    payload = {
        "rest_status": rest_status,
        "can_accept_order": operation_status == "operating",
    }
    snap_info = None
    if position is None and existing_vehicle:
        if existing_vehicle.get("current_lon") is not None and existing_vehicle.get("current_lat") is not None:
            position = {"lon": existing_vehicle.get("current_lon"), "lat": existing_vehicle.get("current_lat")}
    if state.system_initialized and position is not None:
        city_map = state.city_for_operation_area(operation_area_id)
        if city_map is None:
            raise ValueError("运营区未加载或不存在")
        node, dist = _nearest_node_from_coords(city_map, position["lon"], position["lat"])
        if node is None:
            raise ValueError("车辆位置无法吸附到路网节点")
        payload.update({
            "current_lon": position["lon"],
            "current_lat": position["lat"],
            "last_node_code": node.id,
            "next_node_code": node.id,
            "edge_progress": 0.0,
        })
        snap_info = {
            "node": CoreDispatcher._node_to_path_point(node),
            "snap_distance_m": dist,
        }
    elif position is not None:
        payload.update({
            "current_lon": position["lon"],
            "current_lat": position["lat"],
        })
    elif existing_vehicle:
        payload.update({
            "current_lon": existing_vehicle.get("current_lon"),
            "current_lat": existing_vehicle.get("current_lat"),
            "last_node_code": existing_vehicle.get("last_node_code"),
            "next_node_code": existing_vehicle.get("next_node_code"),
            "edge_progress": existing_vehicle.get("edge_progress", 0.0),
        })
    return payload, snap_info


def _required_positive_int(payload, field):
    """读取必填正整数字段。"""
    if field not in payload or payload.get(field) in (None, ""):
        raise ValueError(f"{field} 不能为空")
    try:
        value = int(payload.get(field))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是正整数") from exc
    if value <= 0:
        raise ValueError(f"{field} 必须是正整数")
    return value


def _optional_int(payload, field):
    """读取可选整数字段。"""
    value = payload.get(field)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是整数") from exc


def _operation_area_by_area_id(area_id):
    """按运营区业务 area_id 查找运营区。"""
    if area_id in (None, ""):
        return None
    target_area_id = int(area_id)
    for area in persistence.list_operation_areas():
        try:
            if int(area.get("area_id") or 0) == target_area_id:
                return area
        except (TypeError, ValueError):
            continue
    return None


def _reject_vehicle_area_code_fields(payload):
    """拒绝车辆接口继续使用运营区编码字段。"""
    for field in ("operation_area_code", "area_code"):
        if payload.get(field) not in (None, ""):
            raise ValueError("车辆接口不再接受 operation_area_code/area_code，请传 operation_area_id")


def _operation_area_code_by_area_id(area_id):
    """按运营区业务 area_id 解析运营区展示编码。"""
    if area_id in (None, ""):
        return None
    area = _operation_area_by_area_id(area_id)
    if area is None:
        raise ValueError("operation_area_id 对应的运营区不存在")
    return str(area.get("code") or "").strip() or None


def _payload_has_position_field(payload):
    """判断车辆请求体是否包含位置字段。"""
    return any(key in payload for key in ("initial_position", "position")) or any(
        payload.get(key) not in (None, "")
        for key in ("lon", "lng", "longitude", "lat", "latitude")
    )


def _normalize_vehicle_payload(data, *, existing_code=None, existing_vehicle=None, create=False):
    """校验并规范化车辆档案请求体。

    Args:
        data (dict): 前端传入的车辆档案字段。
        existing_code (str | None): 更新接口路径中的车辆编码；传入时以该值为准。
        existing_vehicle (dict | None): 数据库中已有车辆档案，用于复用运行位置。

    Returns:
        tuple: (payload, snap_info)，payload 可直接写入持久化层。

    Raises:
        ValueError: 必填字段缺失、枚举非法或可运行车辆缺少位置。
    """
    payload = dict(data or {})
    vehicle_code = str(existing_code or payload.get("vehicle_code") or "").strip()
    if not vehicle_code:
        raise ValueError("vehicle_code 不能为空")
    plate_no = str(payload.get("plate_no") or "").strip()
    if not plate_no:
        raise ValueError("plate_no 不能为空")
    raw_operation_status = payload.get("operation_status", payload.get("status"))
    operation_status = str(raw_operation_status or "offline").strip()
    if create:
        if raw_operation_status in (None, ""):
            raise ValueError("新增车辆时 operation_status 必须为 offline")
        if operation_status != "offline":
            raise ValueError("新增车辆时 operation_status 必须为 offline")
        if _payload_has_position_field(payload):
            raise ValueError("新增车辆时不允许传入 initial_position")
    if operation_status not in VEHICLE_OPERATION_STATUSES:
        raise ValueError(f"operation_status 必须是 {', '.join(VEHICLE_OPERATION_STATUSES)} 之一")
    _reject_vehicle_area_code_fields(payload)
    operation_area_id = _optional_int(
        payload,
        "operation_area_id",
    )
    if operation_area_id is None and existing_vehicle:
        operation_area_id = _optional_int(existing_vehicle, "operation_area_id")
    operation_area_code = _operation_area_code_by_area_id(operation_area_id)
    if operation_status in VEHICLE_RUNTIME_STATUSES and state.system_initialized and operation_area_id is None:
        raise ValueError("可运行车辆必须指定有效的 operation_area_id")
    if operation_status in VEHICLE_RUNTIME_STATUSES and state.system_initialized and state.city_for_operation_area(operation_area_id) is None:
        raise ValueError("车辆所属运营区未加载或不存在")
    vehicle_type = str(payload.get("vehicle_type") or "bus").strip()
    if vehicle_type not in VEHICLE_TYPES:
        raise ValueError(f"vehicle_type 必须是 {', '.join(VEHICLE_TYPES)} 之一")
    current_driver_code = str(payload.get("current_driver_code") or payload.get("driver_code") or "").strip() or None
    position = _extract_position(payload)
    if operation_status in VEHICLE_RUNTIME_STATUSES and position is None and not existing_vehicle:
        raise ValueError("可运行车辆必须提供 initial_position")
    runtime_payload, snap_info = _runtime_payload_from_position(
        position,
        operation_status,
        existing_vehicle=existing_vehicle,
        operation_area_id=operation_area_id,
    )
    if create:
        seat_count = _required_positive_int(payload, "seat_count")
        max_load_count = _required_positive_int(payload, "max_load_count")
    else:
        seat_count = int(payload.get("seat_count") or payload.get("max_load_count") or 0)
        max_load_count = int(payload.get("max_load_count") or payload.get("seat_count") or 0)
    result = {
        "vehicle_code": vehicle_code,
        "plate_no": plate_no,
        "vehicle_type": vehicle_type,
        "seat_count": seat_count,
        "max_load_count": max_load_count,
        "vehicle_color": str(payload.get("vehicle_color") or "").strip() or None,
        "vehicle_model": str(payload.get("vehicle_model") or "").strip() or None,
        "operation_status": operation_status,
        "operation_mode": str(payload.get("operation_mode") or "dynamic_bus").strip(),
        "operation_area_id": operation_area_id,
        "operation_area_code": operation_area_code,
        "current_driver_code": current_driver_code,
        "remark": str(payload.get("remark") or "").strip() or None,
    }
    result.update(runtime_payload)
    return result, snap_info


def _runtime_vehicle_by_code(vehicle_code):
    """按车辆业务编码查找当前内存运行车队中的车辆。

    Args:
        vehicle_code (str): 车辆业务编码。

    Returns:
        Vehicle | None: 匹配到的运行期车辆对象；未找到时返回 None。
    """
    for vehicle in state.fleet or []:
        if str(getattr(vehicle, "vehicle_id", "")) == str(vehicle_code) or str(getattr(vehicle, "id", "")) == str(vehicle_code):
            return vehicle
    return None


def _fleet_vehicle_by_vehicle_id(vehicle_id):
    """按 vehicle_id 查找当前内存运行车队中的车辆。

    Args:
        vehicle_id (str): URL 路径中的车辆业务 ID。

    Returns:
        Vehicle | None: 匹配到的运行期车辆对象；未找到时返回 None。
    """
    vehicle_id = str(vehicle_id or "")
    for vehicle in state.fleet or []:
        if str(getattr(vehicle, "vehicle_id", "")) == vehicle_id:
            return vehicle
    return None


def _runtime_vehicle_has_tasks(vehicle):
    """判断运行期车辆是否仍有未完成任务。

    Args:
        vehicle (Vehicle): 运行期车辆对象。

    Returns:
        bool: 车辆上有乘客或仍有计划路线时返回 True。
    """
    return bool(getattr(vehicle, "on_board_orders", None) or getattr(vehicle, "planned_route", None))


def _set_runtime_vehicle_status(vehicle, operation_status):
    """把运营状态同步到运行期车辆休息状态字段。

    Args:
        vehicle (Vehicle): 运行期车辆对象。
        operation_status (str): operating/resting/closing 中的一种。

    Returns:
        None。
    """
    vehicle.operation_status = operation_status
    if operation_status == "operating":
        vehicle.is_resting = False
        vehicle.is_rest_requested = False
        vehicle.rest_status = "operating"
    elif operation_status == "resting":
        vehicle.is_resting = True
        vehicle.is_rest_requested = True
        vehicle.rest_status = "resting"
    elif operation_status == "closing":
        vehicle.is_resting = False
        vehicle.is_rest_requested = True
        vehicle.rest_status = "closing"


def _apply_vehicle_record_to_runtime(vehicle_record):
    """把车辆档案变更应用到内存运行车队。

    Args:
        vehicle_record (dict): 持久化层返回的车辆档案与运行位置字段。

    Returns:
        dict: 运行态是否已应用、执行动作以及可选车辆快照。

    Raises:
        PersistenceConflict: 车辆有未完成任务时不能退出运行车队。
        ValueError: 可运行车辆缺少可用路网节点。
    """
    if not state.system_initialized:
        return {"runtime_applied": False, "reason": "system_not_initialized"}
    operation_status = vehicle_record.get("operation_status") or "offline"
    vehicle_code = vehicle_record.get("vehicle_code")
    existing = _runtime_vehicle_by_code(vehicle_code)
    operation_area_id = _optional_int(vehicle_record, "operation_area_id")
    if operation_area_id is None and existing is not None:
        operation_area_id = getattr(existing, "operation_area_id", None)
    operation_area_code = str(vehicle_record.get("operation_area_code") or getattr(existing, "operation_area_code", "") or "").strip()
    city_map = state.city_for_operation_area(operation_area_id)
    if operation_status not in VEHICLE_RUNTIME_STATUSES:
        if existing is not None:
            if _runtime_vehicle_has_tasks(existing):
                raise persistence.PersistenceConflict("车辆仍有未完成任务，不能退出运营", code="vehicle_has_tasks")
            state.fleet.remove(existing)
            area_fleet = state.fleet_by_area.get(getattr(existing, "operation_area_id", None))
            if area_fleet is not None and existing in area_fleet:
                area_fleet.remove(existing)
        return {"runtime_applied": True, "runtime_action": "removed"}
    if operation_area_id is None or city_map is None:
        raise ValueError("可运行车辆所属运营区未加载或不存在")

    node_id = vehicle_record.get("next_node_code") or vehicle_record.get("last_node_code")
    if not node_id and vehicle_record.get("current_lon") is not None and vehicle_record.get("current_lat") is not None:
        node, _ = _nearest_node_from_coords(city_map, vehicle_record["current_lon"], vehicle_record["current_lat"])
        node_id = node.id if node else None
    node = city_map.nodes_map.get(node_id)
    if node is None:
        raise ValueError("可运行车辆缺少可用路网节点")

    if existing is None:
        color = vehicle_record.get("vehicle_color") or "#64748b"
        capacity = vehicle_record.get("max_load_count") or vehicle_record.get("seat_count") or 10
        existing = Vehicle(vehicle_code, node.id, color, getattr(node, "zone", None), capacity=capacity)
        state.fleet.append(existing)
        state.fleet_by_area.setdefault(operation_area_id, []).append(existing)
        action = "created"
    elif getattr(existing, "operation_area_id", None) != operation_area_id:
        old_area_fleet = state.fleet_by_area.get(getattr(existing, "operation_area_id", None))
        if old_area_fleet is not None and existing in old_area_fleet:
            old_area_fleet.remove(existing)
        state.fleet_by_area.setdefault(operation_area_id, []).append(existing)
        action = "updated"
    else:
        action = "updated"

    existing.id = vehicle_code
    existing.vehicle_id = vehicle_code
    existing.plate_no = vehicle_record.get("plate_no") or vehicle_code
    existing.operation_area_id = operation_area_id
    existing.operation_area_code = operation_area_code
    existing.capacity = vehicle_record.get("max_load_count") or vehicle_record.get("seat_count") or existing.capacity
    existing.color = vehicle_record.get("vehicle_color") or existing.color
    existing.driver_id = vehicle_record.get("current_driver_code") or ""
    existing.driver_no = vehicle_record.get("current_driver_no") or ""
    existing.gps = {
        "lon": vehicle_record.get("current_lon"),
        "lat": vehicle_record.get("current_lat"),
    }
    existing.last_node = node.id
    existing.next_node = node.id
    existing.progress = float(vehicle_record.get("edge_progress") or 0.0)
    existing.time = state.now_timestamp()
    _set_runtime_vehicle_status(existing, operation_status)
    CoreDispatcher.refresh_vehicle_route_metadata(existing, city_map)
    persistence.record_vehicle_runtime(existing)
    return {
        "runtime_applied": True,
        "runtime_action": action,
        "vehicle": _vehicle_to_dict(existing),
    }


def _vehicle_payload_has_runtime_position(vehicle_payload):
    """判断车辆 payload 是否包含可用于入队的运行位置。

    Args:
        vehicle_payload (dict): 已规范化的车辆请求字段或运行字段。

    Returns:
        bool: 包含路网节点或经纬度时返回 True。
    """
    return bool(
        vehicle_payload.get("last_node_code")
        or vehicle_payload.get("next_node_code")
        or (
            vehicle_payload.get("current_lon") is not None
            and vehicle_payload.get("current_lat") is not None
        )
    )


def _admin_error_response(exc):
    """把管理接口内部异常转换为统一 HTTP 响应。

    Args:
        exc (Exception): 路由处理过程中捕获的异常。

    Returns:
        tuple: Flask JSON 响应与 HTTP 状态码。
    """
    if isinstance(exc, persistence.PersistenceUnavailable):
        return jsonify({"error": "database_unavailable", "message": str(exc)}), 503
    if isinstance(exc, persistence.PersistenceConflict):
        return jsonify({"error": exc.code, "message": str(exc), "field": exc.field}), 409
    if isinstance(exc, KeyError) and str(exc).strip("'") == "driver_not_found":
        return jsonify({"error": "driver_not_found", "message": "司机不存在"}), 404
    if isinstance(exc, ValueError):
        return jsonify({"error": str(exc)}), 400
    return jsonify({"error": str(exc)}), 500


def _find_order_eta_context(request_id):
    """从订单池、车辆任务和归档池中查找乘客订单上下文。"""
    request_id = str(request_id)

    for order in CoreDispatcher.order_pool:
        if str(order.request_id) == request_id:
            return order, "matching", None

    for vehicle in state.fleet or []:
        for order in vehicle.on_board_orders:
            if str(order.request_id) == request_id:
                return order, "riding", vehicle

        matched_steps = [
            step
            for step in vehicle.planned_route
            if str(step["order"].request_id) == request_id
        ]
        if matched_steps:
            order = matched_steps[0]["order"]
            has_pickup_step = any(step["type"] == "O" for step in matched_steps)
            return order, "waiting" if has_pickup_step else "riding", vehicle

    for order in CoreDispatcher.completed_orders_pool:
        if str(order.request_id) == request_id:
            status = getattr(order, "status", None) or "completed"
            return order, status, None

    return None, None, None


def _order_eta_response(order, order_status, vehicle):
    """组装乘客端订单 ETA 响应。"""
    estimated_arrival_time = (
        getattr(order, "estimated_arrival_time", None)
        if getattr(order, "estimated_arrival_time", None) is not None
        else getattr(order, "actual_pick_time", None)
    )
    estimated_dropoff_time = (
        getattr(order, "estimated_dropoff_time", None)
        if getattr(order, "estimated_dropoff_time", None) is not None
        else getattr(order, "completion_time", None)
    )
    eta_status = getattr(order, "eta_status", None)
    if eta_status is None:
        if order_status == "matching":
            eta_status = "not_assigned"
        elif order_status in {"completed", "cancelled"}:
            eta_status = order_status
        else:
            eta_status = "pending"

    return {
        "request_id": str(order.request_id),
        "status": order_status,
        "vehicle": (
            {
                "id": vehicle.id,
                "vehicle_id": vehicle.vehicle_id,
                "plate_no": vehicle.plate_no,
            }
            if vehicle is not None
            else None
        ),
        "origin": _order_node_to_dict(order.o_node),
        "destination": _order_node_to_dict(order.d_node),
        "eta": {
            "provider": "amap",
            "status": eta_status,
            "updated_at": getattr(order, "eta_updated_at", None),
            "updated_at_text": _format_optional_timestamp(getattr(order, "eta_updated_at", None)),
            "estimated_arrival_time": estimated_arrival_time,
            "estimated_arrival_time_text": _format_optional_timestamp(estimated_arrival_time),
            "estimated_arrival_eta_seconds": getattr(order, "estimated_arrival_eta_seconds", None),
            "estimated_dropoff_time": estimated_dropoff_time,
            "estimated_dropoff_time_text": _format_optional_timestamp(estimated_dropoff_time),
            "estimated_dropoff_eta_seconds": getattr(order, "estimated_dropoff_eta_seconds", None),
            "error": getattr(order, "eta_error", None),
        },
    }


# ============================================================
# 功能二：系统初始化与订单池接口
# 相关接口：/health、/time、/init、/order、/orders/pool
# ============================================================

@bp.route("/health", methods=["GET"])
def health():
    """健康检查接口。

    Request:
        GET /health

    Returns:
        JSON: status 表示服务状态，initialized 表示系统是否已完成初始化。
    """
    db_status = persistence.status()
    return jsonify({
        "status": "ok",
        "initialized": state.system_initialized,
        "db_enabled": db_status.get("enabled"),
        "db_available": db_status.get("available"),
        "db_database": db_status.get("database"),
        "db_tenant_id": db_status.get("tenant_id"),
        "db_queue_size": db_status.get("queue_size"),
        "db_last_error": db_status.get("last_error"),
    })


@bp.route("/time", methods=["GET"])
def get_time():
    """获取后端统一真实时间。"""
    return jsonify(state.current_time())


@bp.route("/init", methods=["POST"])
def init_route():
    """初始化整个调度系统。

    Request:
        POST /init
        Body JSON 可选字段:
            shp_path (str): 自定义路网 SHP 文件路径。

    Returns:
        JSON: 初始化状态、路网节点数量、POI 数量和道路边数量。
    """
    try:
        with state.state_lock:
            if state.system_initialized:
                return jsonify({
                    "status": "already_initialized",
                    "loaded_areas": state.loaded_operation_areas(),
                    "default_operation_area_id": None,
                    "default_operation_area_code": None,
                    "nodes": sum(len(city.nodes_map) for city in state.city_maps.values()),
                    "pois": sum(len(city.pois) for city in state.city_maps.values()),
                })
            result = state.init_system()
            result["system_time"] = state.current_time()
            result["default_operation_area_id"] = None
            result["default_operation_area_code"] = None
            status_code = 200 if result.get("status") == "initialized" else 400
            return jsonify(result), status_code
    except FileNotFoundError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/order", methods=["POST"])
def create_order():
    """创建新订单并注入调度池。

    Request:
        POST /order
        Body JSON 必填字段:
            request_id (str): 请求 ID。
            origin (dict): 起点坐标，包含 lon/lat。
            destination (dict): 终点坐标，包含 lon/lat。
            expected_pickup_time (dict): 期望上车时间窗，包含 earliest/latest。
            passenger_count (int): 乘客人数。
        说明:
            request_time 由后端统一时间系统自动生成；前端传入时会被忽略。

    Returns:
        JSON: 请求 ID、吸附后的起终点 POI 信息和当前订单池大小。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化，请先调用 POST /init"}), 400

    data = request.get_json(silent=True) or {}
    origin = data.get("origin") or {}
    destination = data.get("destination") or {}
    expected_pickup_time = data.get("expected_pickup_time") or {}
    operation_area_id = _request_operation_area_id(data)
    operation_area = _operation_area_by_area_id(operation_area_id)
    operation_area_code = str((operation_area or {}).get("code") or "").strip() or None
    city_map, area_error = _city_for_operation_area_or_error(operation_area_id)
    if area_error is not None:
        return area_error

    try:
        request_id = str(data["request_id"])
        o_lon = float(origin["lon"])
        o_lat = float(origin["lat"])
        d_lon = float(destination["lon"])
        d_lat = float(destination["lat"])
        expected_pickup_earliest = _parse_datetime(expected_pickup_time.get("earliest"), "expected_pickup_time.earliest")
        expected_pickup_latest = _parse_datetime(expected_pickup_time.get("latest"), "expected_pickup_time.latest")
        passenger_count = int(data["passenger_count"])
        passenger_phone = str(data["passenger_phone"]).strip()
        passenger_id = str(data.get("passenger_id") or "").strip()
    except KeyError as exc:
        return jsonify({"error": f"缺少必填字段: {exc.args[0]}"}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    if not operation_area_id: 
        return jsonify({"error": "operation_area_id 必须填写"}), 400
    if not passenger_phone:
        return jsonify({"error": "passenger_phone 必须填写"}), 400
    if passenger_count <= 0:
        return jsonify({"error": "passenger_count 必须为正整数"}), 400
    if expected_pickup_latest < expected_pickup_earliest:
        return jsonify({"error": "expected_pickup_time.latest 不能早于 earliest"}), 400

    with state.state_lock:
        time_snapshot = state.current_time()
        request_time = state.parse_business_datetime(time_snapshot["time_text"])
        order = Order(
            request_id=request_id,
            o_lon=o_lon,
            o_lat=o_lat,
            d_lon=d_lon,
            d_lat=d_lat,
            request_time=request_time,
            expected_pickup_earliest=expected_pickup_earliest,
            expected_pickup_latest=expected_pickup_latest,
            passenger_count=passenger_count,
            city_map=city_map,
            passenger_phone=passenger_phone,
            passenger_id=passenger_id,
            operation_area_id=operation_area_id,
            operation_area_code=operation_area_code,
            req_time=time_snapshot["timestamp"],
        )
        CoreDispatcher.pool_and_route_planning(state.fleet_for_operation_area(operation_area_id), order, city_map)
        pool_size = len(CoreDispatcher.order_pool)

    return jsonify({
        "status": "pooled",
        "request_id": order.request_id,
        "origin_node": order.o_node.name,
        "origin_coords": {"lon": order.o_node.lon, "lat": order.o_node.lat},
        "destination_node": order.d_node.name,
        "destination_coords": {"lon": order.d_node.lon, "lat": order.d_node.lat},
        "request_time": order.request_time.isoformat(sep=" "),
        "expected_pickup_time": {
            "earliest": order.expected_pickup_earliest.isoformat(sep=" "),
            "latest": order.expected_pickup_latest.isoformat(sep=" "),
        },
        "passenger_count": order.passenger_count,
        "passenger_phone": order.passenger_phone,
        "passenger_id": order.passenger_id,
        "operation_area_id": order.operation_area_id,
        "operation_area_code": order.operation_area_code,
        "pool_size": pool_size,
    })


@bp.route("/orders/pool", methods=["GET"])
def get_order_pool():
    """查看订单池当前状态。

    Request:
        GET /orders/pool

    Returns:
        JSON: 待匹配订单数量、已完成订单数量和待匹配订单列表。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    with state.state_lock:
        return jsonify({
            "pool_size": len(CoreDispatcher.order_pool),
            "completed_orders_size": len(CoreDispatcher.completed_orders_pool),
            "orders": [
                {
                    "request_id": o.request_id,
                    "origin": o.o_node.name,
                    "destination": o.d_node.name,
                    "request_time": o.request_time.isoformat(sep=" "),
                    "expected_pickup_time": {
                        "earliest": o.expected_pickup_earliest.isoformat(sep=" "),
                        "latest": o.expected_pickup_latest.isoformat(sep=" "),
                    },
                    "passenger_count": o.passenger_count,
                    "operation_area_id": getattr(o, "operation_area_id", None),
                    "operation_area_code": getattr(o, "operation_area_code", None),
                    "req_time": o.req_time,
                }
                for o in CoreDispatcher.order_pool
            ],
        })


@bp.route("/orders/<request_id>/eta", methods=["GET"])
def get_order_eta(request_id):
    """乘客端按订单号查询预计接驾到达和预计送达时间。"""
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400

    with state.state_lock:
        order, order_status, vehicle = _find_order_eta_context(request_id)
        if order is None:
            return jsonify({
                "error": "订单未找到",
                "request_id": str(request_id),
            }), 404
        return jsonify(_order_eta_response(order, order_status, vehicle))


@bp.route("/orders/<request_id>/cancel", methods=["POST"])
def cancel_order(request_id):
    """乘客端取消未上车订单。

    Args:
        request_id (str): URL 路径中的请求 ID。

    Request:
        POST /orders/<request_id>/cancel

    Returns:
        JSON: 取消结果；已派车订单会返回刷新后的车辆轨迹。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400

    with state.state_lock:
        cancel_city = None
        for order in CoreDispatcher.order_pool:
            if str(order.request_id) == str(request_id):
                cancel_city = state.city_for_operation_area(getattr(order, "operation_area_id", None))
                break
        else:
            for vehicle in state.fleet or []:
                if any(str(order.request_id) == str(request_id) for order in getattr(vehicle, "on_board_orders", []) or []):
                    cancel_city = _city_for_vehicle(vehicle)
                    break
                if any(str(step["order"].request_id) == str(request_id) for step in getattr(vehicle, "planned_route", []) or []):
                    cancel_city = _city_for_vehicle(vehicle)
                    break
        result = CoreDispatcher.cancel_order(request_id, state.fleet, cancel_city, cancel_time=state.now_datetime())
    if result["status"] == "not_found":
        return jsonify(result), 404
    if result["status"] == "rejected":
        return jsonify(result), 409
    return jsonify(result)


@bp.route("/admin/orders/query", methods=["POST"])
def admin_query_orders():
    """服务端按组合条件查询订单数据库。"""
    try:
        filters = _normalize_order_query_filters(request.get_json(silent=True) or {})
        orders = persistence.query_orders(filters)
        return jsonify({
            "count": len(orders),
            "orders": orders,
        })
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/stations", methods=["POST"])
def admin_create_stations():
    """新增单个或多个站点。"""
    data = request.get_json(silent=True)
    try:
        items = _station_request_items(data)
    except StationRequestError as exc:
        return _station_error_response(exc.code, str(exc), status=exc.status, field=exc.field)

    results = []
    affected_area_ids = set()
    for index, item in enumerate(items):
        try:
            payload = _normalize_station_create_payload(item)
            station = persistence.create_station(payload)
            affected_area_ids.add(station.get("operation_area_id"))
            results.append({
                "index": index,
                "success": True,
                "status": 201,
                "station": station,
            })
        except Exception as exc:
            results.append(_station_exception_result(index, exc, fallback_code="station_create_failed"))

    with state.state_lock:
        runtime_refresh = _refresh_station_runtime_areas(affected_area_ids)
    status_code = _station_batch_status(results, 201)
    return jsonify({
        "total": len(results),
        "success_count": sum(1 for item in results if item.get("success")),
        "failure_count": sum(1 for item in results if not item.get("success")),
        "results": results,
        "runtime_refresh": runtime_refresh,
    }), status_code


@bp.route("/admin/stations", methods=["DELETE"])
def admin_delete_stations():
    """按经纬度删除单个或多个站点。"""
    data = request.get_json(silent=True)
    try:
        items = _station_request_items(data)
    except StationRequestError as exc:
        return _station_error_response(exc.code, str(exc), status=exc.status, field=exc.field)

    results = []
    affected_area_ids = set()
    for index, item in enumerate(items):
        try:
            payload = _normalize_station_delete_payload(item)
            station = persistence.delete_station_by_coordinate(
                payload["lon"],
                payload["lat"],
                operation_area_id=payload.get("operation_area_id"),
            )
            if station is None:
                raise StationRequestError(
                    "数据库中不存在该经纬度站点",
                    "station_not_found_by_coordinate",
                    status=404,
                    field="lon,lat",
                )
            affected_area_ids.add(station.get("operation_area_id"))
            results.append({
                "index": index,
                "success": True,
                "status": 200,
                "station": station,
            })
        except Exception as exc:
            results.append(_station_exception_result(index, exc, fallback_code="station_delete_failed"))

    with state.state_lock:
        runtime_refresh = _refresh_station_runtime_areas(affected_area_ids)
    status_code = _station_batch_status(results, 200)
    return jsonify({
        "total": len(results),
        "success_count": sum(1 for item in results if item.get("success")),
        "failure_count": sum(1 for item in results if not item.get("success")),
        "results": results,
        "runtime_refresh": runtime_refresh,
    }), status_code


@bp.route("/admin/operation-areas", methods=["GET"])
def admin_list_operation_areas():
    """查询运营区列表。"""
    try:
        include_deleted = str(request.args.get("include_deleted") or "").lower() in {"1", "true", "yes"}
        return jsonify({
            "areas": persistence.list_operation_areas(include_deleted=include_deleted),
            "loaded_areas": state.loaded_operation_areas(),
            "default_operation_area_id": None,
            "default_operation_area_code": None,
        })
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/operation-areas", methods=["POST"])
def admin_create_operation_area():
    """新增运营区。"""
    try:
        payload = _normalize_operation_area_payload(
            request.get_json(silent=True) or {},
            require_create_fields=True,
        )
        try:
            runtime_preflight = _preflight_operation_area_runtime_load(payload)
        except Exception as exc:
            return jsonify({
                "error": "operation_area_runtime_load_failed",
                "message": str(exc),
            }), 400
        if runtime_preflight.get("status") != "ready":
            return jsonify({
                "error": "operation_area_runtime_not_ready",
                "runtime_load": runtime_preflight,
            }), 400
        area = None
        area = persistence.save_operation_area(payload, create=True)
        runtime_load = state.load_operation_area_into_runtime(area)
        if runtime_load.get("status") != "ready":
            persistence.hard_delete_operation_area_by_area_id(area.get("area_id"))
            return jsonify({
                "error": "operation_area_runtime_not_ready",
                "runtime_load": runtime_load,
            }), 400
        return jsonify({"area": area, "runtime_load": runtime_load}), 201
    except Exception as exc:
        if "area" in locals() and area:
            try:
                persistence.hard_delete_operation_area_by_area_id(area.get("area_id"))
            except Exception:
                pass
        return _admin_error_response(exc)


def _operation_area_path_id(area_id):
    """解析运营区接口路径中的 area_id。"""
    try:
        value = int(area_id)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


@bp.route("/admin/operation-areas/<area_id>", methods=["GET"])
def admin_get_operation_area(area_id):
    """查询单个运营区。"""
    operation_area_id = _operation_area_path_id(area_id)
    if operation_area_id is None:
        return jsonify({"error": "operation_area_id_invalid", "operation_area_id": str(area_id)}), 400
    area = persistence.get_operation_area_by_area_id(operation_area_id)
    if area is None:
        return jsonify({"error": "operation_area_not_found", "operation_area_id": operation_area_id}), 404
    loaded = next((
        item for item in state.loaded_operation_areas()
        if str(item.get("area_id") or "") == str(operation_area_id)
    ), None)
    return jsonify({"area": area, "loaded": loaded})


@bp.route("/admin/operation-areas/<area_id>", methods=["PUT"])
def admin_update_operation_area(area_id):
    """更新运营区。"""
    try:
        operation_area_id = _operation_area_path_id(area_id)
        if operation_area_id is None:
            return jsonify({"error": "operation_area_id_invalid", "operation_area_id": str(area_id)}), 400
        existing = persistence.get_operation_area_by_area_id(operation_area_id)
        if existing is None:
            return jsonify({"error": "operation_area_not_found", "operation_area_id": operation_area_id}), 404
        data = request.get_json(silent=True) or {}
        data["area_id"] = operation_area_id
        if not data.get("code"):
            data["code"] = existing.get("code")
        payload = _normalize_operation_area_payload(data)
        area = persistence.save_operation_area(payload, create=False)
        if area is None:
            return jsonify({"error": "operation_area_not_found", "operation_area_id": operation_area_id}), 404
        runtime_load = state.load_operation_area_into_runtime(area)
        return jsonify({"area": area, "runtime_load": runtime_load})
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/operation-areas/<area_id>", methods=["DELETE"])
def admin_delete_operation_area(area_id):
    """软删除运营区。"""
    try:
        operation_area_id = _operation_area_path_id(area_id)
        if operation_area_id is None:
            return jsonify({"error": "operation_area_id_invalid", "operation_area_id": str(area_id)}), 400
        deleted = persistence.delete_operation_area_by_area_id(operation_area_id)
        if not deleted:
            return jsonify({"error": "operation_area_not_found", "operation_area_id": operation_area_id}), 404
        return jsonify({"status": "deleted", "operation_area_id": operation_area_id})
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/operation-areas/<area_id>/load-test", methods=["POST"])
def admin_test_operation_area_load(area_id):
    """测试指定运营区 SHP 是否可以加载。"""
    operation_area_id = _operation_area_path_id(area_id)
    if operation_area_id is None:
        return jsonify({"error": "operation_area_id_invalid", "operation_area_id": str(area_id)}), 400
    area = persistence.get_operation_area_by_area_id(operation_area_id)
    if area is None:
        return jsonify({"error": "operation_area_not_found", "operation_area_id": operation_area_id}), 404
    shp_path = str(area.get("shp_path") or "").strip()
    if not shp_path:
        return jsonify({"error": "shp_path 不能为空", "operation_area_id": operation_area_id}), 400
    try:
        shp_encoding = str(area.get("shp_encoding") or "utf-8").strip() or "utf-8"
        city_map = CityGraph(shp_path, shp_encoding=shp_encoding)
        state._apply_database_pois(city_map, area)
        bounds = state._city_bounds(city_map)
        result = {
            "load_status": "ready",
            "load_error": None,
            "node_count": len(city_map.nodes_map),
            "edge_count": len(city_map.edges),
            "poi_count": len(city_map.pois),
            "bounds_json": bounds,
            "shp_encoding": getattr(city_map, "shp_encoding", shp_encoding),
        }
        persistence.record_operation_area_load_result_by_area_id(operation_area_id, result)
        return jsonify({"status": "ready", "operation_area_id": operation_area_id, "result": result})
    except Exception as exc:
        result = {
            "load_status": "error",
            "load_error": str(exc),
            "node_count": None,
            "edge_count": None,
            "poi_count": None,
            "bounds_json": None,
        }
        persistence.record_operation_area_load_result_by_area_id(operation_area_id, result)
        return jsonify({"status": "error", "operation_area_id": operation_area_id, "error": str(exc)}), 400


# ============================================================
# 功能三：运营禁区、司机车辆管理与车辆运行接口
# 相关接口：/operation-restrictions/*、/admin/*、/fleet/*、/tick、/status
# ============================================================

@bp.route("/operation-restrictions/policies", methods=["GET"])
def list_operation_restriction_policies():
    """查询运营禁区策略列表。

    Request:
        GET /operation-restrictions/policies

    Returns:
        JSON: 未软删除策略列表，以及指定运营区当前生效策略。
    """
    operation_area_id = _request_operation_area_id()
    policies = persistence.list_operation_restriction_policies(operation_area_id=operation_area_id)
    active_policy = (
        persistence.get_active_operation_restriction_policy(operation_area_id=operation_area_id)
        if operation_area_id is not None
        else None
    )
    if operation_area_id is not None:
        _sync_active_restriction_policy(active_policy, operation_area_id=operation_area_id)
    return jsonify({
        "operation_area_id": operation_area_id,
        "policies": [_restriction_policy_response(policy) for policy in policies],
        "active_policy": _restriction_policy_response(active_policy),
    })


@bp.route("/operation-restrictions/policies", methods=["POST"])
def create_operation_restriction_policy():
    """创建运营禁区策略。

    Request:
        POST /operation-restrictions/policies
        Body JSON 字段:
            policy_code (str): 策略编号，允许重复。
            policy_name (str): 策略名称，同租户下必须唯一。
            polygons (list): 禁区 polygon 列表。

    Returns:
        JSON: 创建后的策略快照；校验失败返回 400。
    """
    data = request.get_json(silent=True) or {}
    try:
        operation_area_id = _request_operation_area_id(data)
        if operation_area_id is None:
            return jsonify({"error": "operation_area_id_required"}), 400
        policy = normalize_policy_payload(data, require_identity=True)
        policy["operation_area_id"] = operation_area_id
        if persistence.get_operation_restriction_policy(policy["policy_name"]):
            return jsonify({
                "error": "policy_name_exists",
                "message": "禁区策略名称已存在",
                "policy_name": policy["policy_name"],
            }), 400
        saved = persistence.save_operation_restriction_policy(policy)
        active = persistence.get_active_operation_restriction_policy(operation_area_id=operation_area_id)
        _sync_active_restriction_policy(active, operation_area_id=operation_area_id)
        return jsonify({"policy": _restriction_policy_response(saved)}), 201
    except OperationRestrictionError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/operation-restrictions/policies/<policy_identity>", methods=["GET"])
def get_operation_restriction_policy(policy_identity):
    """查询单个运营禁区策略。

    Args:
        policy_identity (str): URL 路径中的策略名称或策略编号。

    Returns:
        JSON: 策略快照；不存在时返回 404。
    """
    operation_area_id = _request_operation_area_id()
    policy = persistence.get_operation_restriction_policy(
        policy_identity,
        operation_area_id=operation_area_id,
    )
    if policy is None:
        return jsonify({"error": "policy_not_found", "policy_identity": str(policy_identity)}), 404
    return jsonify({"policy": _restriction_policy_response(policy)})


@bp.route("/operation-restrictions/policies/<policy_identity>", methods=["PUT"])
def update_operation_restriction_policy(policy_identity):
    """更新单个运营禁区策略。

    Args:
        policy_identity (str): URL 路径中的策略名称或策略编号。

    Request:
        PUT /operation-restrictions/policies/<policy_identity>
        Body JSON 字段同创建接口；编辑已有策略时不允许修改 policy_name。

    Returns:
        JSON: 更新后的策略快照；策略不存在返回 404。
    """
    data = request.get_json(silent=True) or {}
    try:
        requested_area_id = _request_operation_area_id(data)
        policy = normalize_policy_payload(data, require_identity=True)
        existing = persistence.get_operation_restriction_policy(policy_identity)
        if existing is None:
            return jsonify({"error": "policy_not_found", "policy_identity": str(policy_identity)}), 404
        if policy["policy_name"] != existing.get("policy_name"):
            return jsonify({
                "error": "policy_name_immutable",
                "message": "禁区策略名称是唯一标识，编辑已有策略时不能修改名称",
                "policy_name": existing.get("policy_name"),
            }), 400
        old_operation_area_id = existing.get("operation_area_id")
        operation_area_id = requested_area_id or old_operation_area_id
        if operation_area_id is None:
            return jsonify({"error": "operation_area_id_required"}), 400
        policy["operation_area_id"] = operation_area_id
        policy["is_active"] = bool(existing.get("is_active"))
        saved = persistence.save_operation_restriction_policy(policy)
        active = persistence.get_active_operation_restriction_policy(operation_area_id=operation_area_id)
        _sync_active_restriction_policy(active, operation_area_id=operation_area_id)
        if old_operation_area_id and old_operation_area_id != operation_area_id:
            old_active = persistence.get_active_operation_restriction_policy(
                operation_area_id=old_operation_area_id
            )
            _sync_active_restriction_policy(old_active, operation_area_id=old_operation_area_id)
        return jsonify({"policy": _restriction_policy_response(saved)})
    except OperationRestrictionError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/operation-restrictions/policies/<policy_identity>", methods=["DELETE"])
def delete_operation_restriction_policy(policy_identity):
    """软删除单个运营禁区策略。

    Args:
        policy_identity (str): URL 路径中的策略名称或策略编号。

    Returns:
        JSON: 删除结果和删除后的当前生效策略；策略不存在返回 404。
    """
    try:
        existing = persistence.get_operation_restriction_policy(policy_identity)
        operation_area_id = existing.get("operation_area_id") if existing else None
        deleted = persistence.delete_operation_restriction_policy(policy_identity)
        if not deleted:
            return jsonify({"error": "policy_not_found", "policy_identity": str(policy_identity)}), 404
        active = persistence.get_active_operation_restriction_policy(operation_area_id=operation_area_id)
        _sync_active_restriction_policy(active, operation_area_id=operation_area_id)
        return jsonify({
            "status": "deleted",
            "policy_identity": str(policy_identity),
            "operation_area_id": operation_area_id,
            "active_policy": _restriction_policy_response(active),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/operation-restrictions/active", methods=["GET"])
def get_active_operation_restriction_policy():
    """查询当前生效的运营禁区策略。

    Request:
        GET /operation-restrictions/active

    Returns:
        JSON: 指定运营区当前生效策略；未设置时 policy 为 null。
    """
    operation_area_id = _request_operation_area_id()
    if operation_area_id is None:
        return jsonify({"error": "operation_area_id_required"}), 400
    active = persistence.get_active_operation_restriction_policy(operation_area_id=operation_area_id)
    _sync_active_restriction_policy(active, operation_area_id=operation_area_id)
    return jsonify({
        "operation_area_id": operation_area_id,
        "policy": _restriction_policy_response(active),
    })


@bp.route("/operation-restrictions/active", methods=["POST"])
def set_active_operation_restriction_policy():
    """选择当前生效的禁区策略，或关闭禁区限制。

    Request:
        POST /operation-restrictions/active
        Body JSON 字段:
            policy_name (str | null): 策略名称。
            policy_code (str | null): 策略编号；policy_name 为空时使用。

    Returns:
        JSON: 切换结果和当前生效策略；策略不存在或禁用时返回 404。
    """
    data = request.get_json(silent=True) or {}
    operation_area_id = _request_operation_area_id(data)
    if operation_area_id is None:
        return jsonify({"error": "operation_area_id_required"}), 400
    policy_identity = data.get("policy_name")
    if policy_identity in (None, ""):
        policy_identity = data.get("policy_code")
    try:
        active = persistence.set_active_operation_restriction_policy(
            policy_identity,
            operation_area_id=operation_area_id,
        )
        if policy_identity not in (None, "") and active is None:
            return jsonify({
                "error": "policy_not_found_or_disabled",
                "policy_identity": str(policy_identity),
                "operation_area_id": operation_area_id,
            }), 404
        _sync_active_restriction_policy(active, operation_area_id=operation_area_id)
        return jsonify({
            "status": "active_updated",
            "operation_area_id": operation_area_id,
            "policy": _restriction_policy_response(active),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/admin/driver-vehicle/options", methods=["GET"])
def admin_driver_vehicle_options():
    """返回司机车辆管理表单选项和当前档案。

    Request:
        GET /admin/driver-vehicle/options

    Returns:
        JSON: 司机状态枚举、车辆状态枚举、车辆类型枚举，以及当前司机/车辆列表。
    """
    return jsonify({
        "driver_employment_statuses": list(DRIVER_EMPLOYMENT_STATUSES),
        "driver_work_statuses": list(DRIVER_WORK_STATUSES),
        "vehicle_operation_statuses": list(VEHICLE_OPERATION_STATUSES),
        "vehicle_types": list(VEHICLE_TYPES),
        "drivers": persistence.list_drivers(),
        "vehicles": persistence.list_vehicles(),
        "operation_areas": persistence.list_operation_areas(),
        "loaded_operation_areas": state.loaded_operation_areas(),
        "default_operation_area_id": None,
        "default_operation_area_code": None,
    })


@bp.route("/admin/drivers", methods=["GET"])
def admin_list_drivers():
    """查询司机档案列表。

    Request:
        GET /admin/drivers

    Returns:
        JSON: 未软删除司机档案列表。
    """
    return jsonify({"drivers": persistence.list_drivers()})


@bp.route("/admin/drivers", methods=["POST"])
def admin_create_driver():
    """创建司机档案。

    Request:
        POST /admin/drivers
        Body JSON 字段:
            driver_code (str): 司机业务编码，创建后不可修改。
            driver_no (str): 司机工号，同租户下唯一。
            driver_name (str): 司机姓名；未传时回退为工号或编码。

    Returns:
        JSON: 创建后的司机档案；唯一约束冲突返回 409。
    """
    try:
        payload = _normalize_driver_payload(request.get_json(silent=True) or {})
        return jsonify({"driver": persistence.save_driver(payload, create=True)}), 201
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/drivers/<driver_code>", methods=["GET"])
def admin_get_driver(driver_code):
    """查询单个司机档案。

    Args:
        driver_code (str): URL 路径中的司机业务编码。

    Returns:
        JSON: 司机档案；不存在时返回 404。
    """
    driver = persistence.get_driver(driver_code)
    if driver is None:
        return jsonify({"error": "driver_not_found", "driver_code": str(driver_code)}), 404
    return jsonify({"driver": driver})


@bp.route("/admin/drivers/<driver_code>", methods=["PUT"])
def admin_update_driver(driver_code):
    """更新司机档案。

    Args:
        driver_code (str): URL 路径中的司机业务编码，更新时不可修改。

    Request:
        PUT /admin/drivers/<driver_code>
        Body JSON 字段同创建接口；driver_code 以路径参数为准。

    Returns:
        JSON: 更新后的司机档案；不存在时返回 404，唯一约束冲突返回 409。
    """
    try:
        payload = _normalize_driver_payload(request.get_json(silent=True) or {}, existing_code=driver_code)
        driver = persistence.save_driver(payload, create=False)
        if driver is None:
            return jsonify({"error": "driver_not_found", "driver_code": str(driver_code)}), 404
        return jsonify({"driver": driver})
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/drivers/<driver_code>", methods=["DELETE"])
def admin_delete_driver(driver_code):
    """软删除司机档案。

    Args:
        driver_code (str): URL 路径中的司机业务编码。

    Returns:
        JSON: 删除结果；司机仍被车辆绑定时返回 409。
    """
    try:
        deleted = persistence.delete_driver(driver_code)
        if not deleted:
            return jsonify({"error": "driver_not_found", "driver_code": str(driver_code)}), 404
        return jsonify({"status": "deleted", "driver_code": str(driver_code)})
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/vehicles", methods=["GET"])
def admin_list_vehicles():
    """查询车辆档案列表。

    Request:
        GET /admin/vehicles

    Returns:
        JSON: 未软删除车辆档案列表，包含当前司机和运行位置字段。
    """
    return jsonify({"vehicles": persistence.list_vehicles()})


@bp.route("/admin/vehicles", methods=["POST"])
def admin_create_vehicle():
    """创建离线车辆档案。

    Request:
        POST /admin/vehicles
        Body JSON 字段:
            vehicle_code (str): 车辆业务编码，创建后不可修改。
            plate_no (str): 车牌号，同租户下唯一。
            operation_status (str): 必须为 offline。
            seat_count (int): 座位数，必填。
            max_load_count (int): 核载人数，必填。

    Returns:
        JSON: 创建后的车辆档案和运行态同步结果。
    """
    try:
        with state.state_lock:
            payload, snap_info = _normalize_vehicle_payload(request.get_json(silent=True) or {}, create=True)
            vehicle = persistence.save_vehicle(payload, create=True)
            runtime = _apply_vehicle_record_to_runtime(vehicle)
        return jsonify({"vehicle": vehicle, "runtime": runtime, "snap": snap_info}), 201
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/vehicles/<vehicle_code>", methods=["GET"])
def admin_get_vehicle(vehicle_code):
    """查询单个车辆档案。

    Args:
        vehicle_code (str): URL 路径中的车辆业务编码。

    Returns:
        JSON: 车辆档案；不存在时返回 404。
    """
    vehicle = persistence.get_vehicle(vehicle_code)
    if vehicle is None:
        return jsonify({"error": "vehicle_not_found", "vehicle_code": str(vehicle_code)}), 404
    return jsonify({"vehicle": vehicle})


@bp.route("/admin/vehicles/<vehicle_code>", methods=["PUT"])
def admin_update_vehicle(vehicle_code):
    """更新车辆档案并按状态同步运行车队。

    Args:
        vehicle_code (str): URL 路径中的车辆业务编码，更新时不可修改。

    Request:
        PUT /admin/vehicles/<vehicle_code>
        Body JSON 字段同创建接口；vehicle_code 以路径参数为准。

    Returns:
        JSON: 更新后的车辆档案、运行态同步结果和可选吸附结果。
    """
    try:
        with state.state_lock:
            existing = persistence.get_vehicle(vehicle_code)
            if existing is None:
                return jsonify({"error": "vehicle_not_found", "vehicle_code": str(vehicle_code)}), 404
            payload, snap_info = _normalize_vehicle_payload(
                request.get_json(silent=True) or {},
                existing_code=vehicle_code,
                existing_vehicle=existing,
            )
            runtime_vehicle = _runtime_vehicle_by_code(vehicle_code) if state.system_initialized else None
            if payload["operation_status"] not in VEHICLE_RUNTIME_STATUSES and runtime_vehicle and _runtime_vehicle_has_tasks(runtime_vehicle):
                raise persistence.PersistenceConflict("车辆仍有未完成任务，不能退出运营", code="vehicle_has_tasks")
            if payload["operation_status"] in VEHICLE_RUNTIME_STATUSES and state.system_initialized and not _vehicle_payload_has_runtime_position(payload):
                raise ValueError("可运行车辆必须提供 initial_position 或已有运行位置")
            vehicle = persistence.save_vehicle(payload, create=False)
            runtime = _apply_vehicle_record_to_runtime(vehicle)
        return jsonify({"vehicle": vehicle, "runtime": runtime, "snap": snap_info})
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/vehicles/<vehicle_code>", methods=["DELETE"])
def admin_delete_vehicle(vehicle_code):
    """软删除车辆档案并从运行车队移除。

    Args:
        vehicle_code (str): URL 路径中的车辆业务编码。

    Returns:
        JSON: 删除结果；车辆仍有未完成任务时返回 409。
    """
    try:
        with state.state_lock:
            runtime_vehicle = _runtime_vehicle_by_code(vehicle_code) if state.system_initialized else None
            if runtime_vehicle and _runtime_vehicle_has_tasks(runtime_vehicle):
                raise persistence.PersistenceConflict("车辆仍有未完成任务，不能删除", code="vehicle_has_tasks")
            if runtime_vehicle and state.fleet is not None:
                state.fleet.remove(runtime_vehicle)
                area_fleet = state.fleet_by_area.get(getattr(runtime_vehicle, "operation_area_id", None))
                if area_fleet is not None and runtime_vehicle in area_fleet:
                    area_fleet.remove(runtime_vehicle)
            deleted = persistence.delete_vehicle(vehicle_code)
        if not deleted:
            return jsonify({"error": "vehicle_not_found", "vehicle_code": str(vehicle_code)}), 404
        return jsonify({"status": "deleted", "vehicle_code": str(vehicle_code)})
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/vehicles/<vehicle_code>/status", methods=["POST"])
def admin_update_vehicle_status(vehicle_code):
    """更新车辆运营状态。

    Args:
        vehicle_code (str): URL 路径中的车辆业务编码。

    Request:
        POST /admin/vehicles/<vehicle_code>/status
        Body JSON 字段:
            operation_status (str): 目标运营状态。
            initial_position (dict): 激活可运行状态时可选提供的 lon/lat。
        说明:
            切换为 operating 时车辆可以不绑定司机；如传入司机则校验司机存在且未绑定其他车辆。

    Returns:
        JSON: 更新后的车辆档案、运行态同步结果和可选吸附结果。
    """
    data = request.get_json(silent=True) or {}
    operation_status = str(data.get("operation_status") or data.get("status") or "").strip()
    if operation_status not in VEHICLE_OPERATION_STATUSES:
        return jsonify({"error": f"operation_status 必须是 {', '.join(VEHICLE_OPERATION_STATUSES)} 之一"}), 400
    try:
        with state.state_lock:
            existing = persistence.get_vehicle(vehicle_code)
            if existing is None:
                return jsonify({"error": "vehicle_not_found", "vehicle_code": str(vehicle_code)}), 404
            runtime_vehicle = _runtime_vehicle_by_code(vehicle_code) if state.system_initialized else None
            if operation_status not in VEHICLE_RUNTIME_STATUSES and runtime_vehicle and _runtime_vehicle_has_tasks(runtime_vehicle):
                raise persistence.PersistenceConflict("车辆仍有未完成任务，不能退出运营", code="vehicle_has_tasks")
            _reject_vehicle_area_code_fields(data)
            operation_area_id = _optional_int(data, "operation_area_id")
            if operation_area_id is None:
                operation_area_id = _optional_int(existing, "operation_area_id")
            operation_area_code = _operation_area_code_by_area_id(operation_area_id)
            if operation_status in VEHICLE_RUNTIME_STATUSES and state.system_initialized and operation_area_id is None:
                raise ValueError("可运行车辆必须指定有效的 operation_area_id")
            if operation_status in VEHICLE_RUNTIME_STATUSES and state.system_initialized and state.city_for_operation_area(operation_area_id) is None:
                raise ValueError("车辆所属运营区未加载或不存在")
            runtime_payload, snap_info = _runtime_payload_from_position(
                _extract_position(data),
                operation_status,
                existing_vehicle=existing,
                operation_area_id=operation_area_id,
            )
            runtime_payload["operation_area_id"] = operation_area_id
            runtime_payload["operation_area_code"] = operation_area_code
            if operation_status in VEHICLE_RUNTIME_STATUSES and state.system_initialized and not _vehicle_payload_has_runtime_position(runtime_payload):
                raise ValueError("可运行车辆必须提供 initial_position 或已有运行位置")
            vehicle = persistence.update_vehicle_status(vehicle_code, operation_status, runtime_payload=runtime_payload)
            runtime = _apply_vehicle_record_to_runtime(vehicle)
        return jsonify({"vehicle": vehicle, "runtime": runtime, "snap": snap_info})
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/admin/vehicles/<vehicle_code>/bind-driver", methods=["POST"])
def admin_bind_vehicle_driver(vehicle_code):
    """绑定或解绑车辆司机。

    Args:
        vehicle_code (str): URL 路径中的车辆业务编码。

    Request:
        POST /admin/vehicles/<vehicle_code>/bind-driver
        Body JSON 字段:
            driver_code (str | null): 司机业务编码；为空表示解绑。
            operator (str | None): 可选操作人标识。
        说明:
            同一司机只能绑定一台车；operating 车辆也允许解绑司机。

    Returns:
        JSON: 更新后的车辆档案和运行态同步结果。
    """
    data = request.get_json(silent=True) or {}
    try:
        with state.state_lock:
            vehicle = persistence.bind_vehicle_driver(
                vehicle_code,
                data.get("driver_code"),
                operator=data.get("operator"),
            )
            if vehicle is None:
                return jsonify({"error": "vehicle_not_found", "vehicle_code": str(vehicle_code)}), 404
            runtime = _apply_vehicle_record_to_runtime(vehicle)
        return jsonify({"vehicle": vehicle, "runtime": runtime})
    except Exception as exc:
        return _admin_error_response(exc)


@bp.route("/fleet", methods=["GET"])
def get_fleet():
    """获取全部车辆状态。

    Request:
        GET /fleet

    Returns:
        JSON: fleet 数组，每项为 _vehicle_to_dict 生成的车辆快照。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    with state.state_lock:
        operation_area_id = _request_operation_area_id()
        selected_fleet = (
            state.fleet_for_operation_area(operation_area_id)
            if operation_area_id is not None
            else (state.fleet or [])
        )
        operation_area = _operation_area_by_area_id(operation_area_id)
        return jsonify({
            "operation_area_id": operation_area_id,
            "operation_area_code": (operation_area or {}).get("code"),
            "fleet": [_vehicle_to_dict(v) for v in selected_fleet],
        })


@bp.route("/fleet/<vehicle_id>", methods=["GET"])
def get_vehicle(vehicle_id):
    """获取单辆车状态。

    Args:
        vehicle_id (str): URL 路径中的车辆业务 ID。

    Returns:
        JSON: 指定车辆快照；车辆不存在时返回 404。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    with state.state_lock:
        vehicle = _fleet_vehicle_by_vehicle_id(vehicle_id)
        if vehicle is not None:
            return jsonify(_vehicle_to_dict(vehicle))
    return jsonify({"error": "车辆未找到"}), 404


@bp.route("/fleet/<vehicle_id>/path", methods=["POST"])
def update_vehicle_path(vehicle_id):
    """根据车辆 GPS 坐标实时更新车辆后续路网轨迹。

    Args:
        vehicle_id (str): URL 路径中的车辆业务 ID。

    Request:
        POST /fleet/<vehicle_id>/path
        Body JSON 字段:
            lon/lng/longitude (float): 车辆当前 GPS 经度。
            lat/latitude (float): 车辆当前 GPS 纬度。

    Returns:
        JSON: 车辆 GPS、路网吸附、后续轨迹、上下客事件和订单状态。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400

    data = request.get_json(silent=True) or {}
    lon = data.get("lon", data.get("lng", data.get("longitude")))
    lat = data.get("lat", data.get("latitude"))
    if lon is None or lat is None:
        return jsonify({"error": "请求体必须包含 lon/lat 车辆 GPS 坐标"}), 400

    try:
        lon = float(lon)
        lat = float(lat)
    except (TypeError, ValueError):
        return jsonify({"error": "lon/lat 必须是数字"}), 400

    with state.state_lock:
        target_vehicle = _fleet_vehicle_by_vehicle_id(vehicle_id)
        if target_vehicle is None:
            return jsonify({"error": "车辆未找到"}), 404

        city_map = _city_for_vehicle(target_vehicle)
        if city_map is None:
            return jsonify({"error": "车辆所属运营区未加载或不存在"}), 409
        path_result = CoreDispatcher.update_vehicle_position_from_gps(
            target_vehicle,
            city_map,
            lon,
            lat,
            current_timestamp=state.now_timestamp(),
        )
    if path_result is None:
        return jsonify({"error": "车辆当前位置无法吸附到路网"}), 409

    return jsonify(_path_result_to_response(target_vehicle, path_result))


@bp.route("/fleet/<vehicle_id>/boarding-events", methods=["POST"])
def confirm_vehicle_boarding_event(vehicle_id):
    """司机端显式确认车辆当前上下客步骤。"""
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400

    data = request.get_json(silent=True) or {}
    action = data.get("action")
    request_id = data.get("request_id")
    lon = data.get("lon", data.get("lng", data.get("longitude")))
    lat = data.get("lat", data.get("latitude"))
    threshold = data.get("distance_threshold_m", 30.0)
    try:
        occurred_at = _parse_optional_event_timestamp(data.get("occurred_at"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with state.state_lock:
        target_vehicle = _fleet_vehicle_by_vehicle_id(vehicle_id)
        if target_vehicle is None:
            return jsonify({"error": "车辆未找到"}), 404

        result = CoreDispatcher.confirm_vehicle_boarding_event(
            target_vehicle,
            action,
            request_id=request_id,
            lon=lon,
            lat=lat,
            distance_threshold_m=threshold,
            current_timestamp=occurred_at,
        )
        if not result.get("ok"):
            status_code = int(result.get("status_code") or 400)
            payload = {key: value for key, value in result.items() if key not in {"ok", "status_code"}}
            return jsonify(payload), status_code

        return jsonify({
            "status": "ok",
            "event": result.get("event"),
            "orders": {
                "on_board": result.get("on_board_orders", []),
                "remaining": result.get("planned_route", []),
            },
            "vehicle": _vehicle_to_dict(target_vehicle),
        })


@bp.route("/fleet/<vehicle_id>/amap-route/replan", methods=["POST"])
def replan_vehicle_amap_route(vehicle_id):
    """同步优先重规划单辆车的高德驾车路线。"""
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400

    with state.state_lock:
        target_vehicle = _fleet_vehicle_by_vehicle_id(vehicle_id)
        if target_vehicle is None:
            return jsonify({"error": "车辆未找到"}), 404

        city_map = _city_for_vehicle(target_vehicle)
        if city_map is None:
            return jsonify({"error": "车辆所属运营区未加载或不存在"}), 409
        prepared = CoreDispatcher.prepare_vehicle_amap_replan_job(target_vehicle, city_map)
        if not prepared.get("ok"):
            status_code = int(prepared.get("status_code") or 409)
            payload = {key: value for key, value in prepared.items() if key not in {"ok", "status_code"}}
            return jsonify(payload), status_code
        job = prepared["job"]

    try:
        route_result = CoreDispatcher._run_route_grasp_job(CoreDispatcher._get_route_planner(), job)
    except Exception as exc:
        route_result = {
            "ok": False,
            "status": "error",
            "reason": str(exc),
            "segments": [],
        }

    with state.state_lock:
        target_vehicle = _fleet_vehicle_by_vehicle_id(vehicle_id)
        if target_vehicle is None:
            return jsonify({"error": "车辆未找到"}), 404
        applied = CoreDispatcher._apply_route_grasp_result_to_vehicle(target_vehicle, job, route_result)
        if not applied:
            return jsonify({
                "error": "车辆路线版本已变化，重规划结果已丢弃",
                "route_version": job.get("route_version"),
                "vehicle": _vehicle_to_dict(target_vehicle),
            }), 409

        return jsonify({
            "status": getattr(target_vehicle, "planned_route_grasp_status", None),
            "ok": bool(isinstance(route_result, dict) and route_result.get("ok")),
            "route_version": getattr(target_vehicle, "planned_route_grasp_route_version", None),
            "grasp_error": getattr(target_vehicle, "planned_route_grasp_error", None),
            "segments": getattr(target_vehicle, "planned_route_segment_grasped_point", []),
            "path": getattr(target_vehicle, "planned_route_grasped_point", []),
            "vehicle": _vehicle_to_dict(target_vehicle),
        })


@bp.route("/fleet/<vehicle_id>/rest", methods=["POST"])
def request_vehicle_rest(vehicle_id):
    """司机端请求休息。

    Args:
        vehicle_id (str): URL 路径中的车辆业务 ID。

    Request:
        POST /fleet/<vehicle_id>/rest
        Body JSON 可选字段:
            desired_rest_time (str|float): 期望休息时间；为空表示马上收车休息。
            rest_duration_minutes (float): 可选休息时长，后端会限制在 15-30 分钟。

    Returns:
        JSON: 系统休息决策、预计完成当前订单时间和车辆最新状态。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400

    data = request.get_json(silent=True) or {}
    with state.state_lock:
        target_vehicle = _fleet_vehicle_by_vehicle_id(vehicle_id)
        if target_vehicle is None:
            return jsonify({"error": "车辆未找到"}), 404

        try:
            desired_rest_time = _parse_optional_rest_time(data.get("desired_rest_time"), target_vehicle)
            rest_duration_seconds = None
            if data.get("rest_duration_minutes") not in (None, ""):
                rest_duration_seconds = float(data["rest_duration_minutes"]) * 60.0
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        result = CoreDispatcher.request_driver_rest(
            target_vehicle,
            _city_for_vehicle(target_vehicle),
            desired_rest_time=desired_rest_time,
            rest_duration_seconds=rest_duration_seconds,
        )
        persistence.record_rest_request(target_vehicle, result)
        estimated_finish_time = result.get("estimated_finish_time")
        return jsonify({
            "vehicle_id": target_vehicle.vehicle_id,
            "decision": result.get("decision"),
            "rest_status": result.get("status"),
            "rest_status_text": REST_STATUS_TEXT.get(result.get("status"), "未知"),
            "estimated_finish_time": estimated_finish_time,
            "estimated_finish_time_text": (
                state.format_timestamp(estimated_finish_time)
                if estimated_finish_time is not None
                else None
            ),
            "estimated_finish_after_seconds": (
                estimated_finish_time - target_vehicle.time
                if estimated_finish_time is not None
                else None
            ),
            "vehicle": _vehicle_to_dict(target_vehicle),
        })


@bp.route("/tick", methods=["POST"])
def tick_vehicles():
    """推进所有车辆的仿真时间。

    Request:
        POST /tick
        Body JSON 可选字段:
            dt (float): 推进秒数，默认 1 秒。

    Returns:
        JSON: 本次推进时长和推进后的车队状态。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    dt = state.refresh_runtime_state()
    with state.state_lock:
        return jsonify({
            "dt": dt,
            "system_time": state.current_time(),
            "fleet": [_vehicle_to_dict(v) for v in state.fleet],
        })


@bp.route("/status", methods=["GET"])
def full_status():
    """获取系统全量状态快照。

    Request:
        GET /status

    Returns:
        JSON: 初始化状态、路网规模、车队状态、订单池和完成订单统计。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    with state.state_lock:
        loaded_city_maps = list((state.city_maps or {}).values())
        return jsonify({
            "initialized": state.system_initialized,
            "system_time": state.current_time(),
            "nodes_count": sum(len(city_map.nodes_map) for city_map in loaded_city_maps),
            "pois_count": sum(len(city_map.pois) for city_map in loaded_city_maps),
            "edges_count": sum(len(city_map.edges) for city_map in loaded_city_maps),
            "default_operation_area_id": None,
            "default_operation_area_code": None,
            "loaded_areas": state.loaded_operation_areas(),
            "fleet": [_vehicle_to_dict(v) for v in state.fleet],
            "order_pool_size": len(CoreDispatcher.order_pool),
            "completed_orders": len(CoreDispatcher.completed_orders_pool),
            "operation_restriction_policies": {
                str(area_id): _restriction_policy_response(
                    CoreDispatcher.current_operation_restriction_policy(area_id)
                )
                for area_id in (state.city_maps or {})
            },
        })


# ============================================================
# 功能四：地图与前端可视化数据接口 --测试用
# 相关接口：/export、/pois、/map/road-network
# ============================================================

@bp.route("/export", methods=["POST"])
def export_visualization():
    """导出前端可视化数据。

    Request:
        POST /export
        Body JSON 可选字段:
            file_path (str): 导出的 JS 文件路径。

    Returns:
        JSON: 导出状态和文件路径；导出失败时返回错误信息。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path", "map_data.js")
    try:
        with state.state_lock:
            operation_area_id = _request_operation_area_id(data)
            city_map, area_error = _city_for_operation_area_or_error(operation_area_id)
            if area_error is not None:
                return area_error
            AuxiliaryFunctions.export_visualization_data(
                city_map,
                file_path,
                state.fleet_for_operation_area(operation_area_id),
                speed_mps=SPEED_MPS,
            )
        return jsonify({"status": "ok", "file": file_path, "operation_area_id": operation_area_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/pois", methods=["GET"])
def get_pois():
    """获取所有 POI 站点列表。

    Request:
        GET /pois

    Returns:
        JSON: POI 的 id、名称、经纬度和分区。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    with state.state_lock:
        operation_area_id = _request_operation_area_id()
        operation_area = _operation_area_by_area_id(operation_area_id)
        city_map, area_error = _city_for_operation_area_or_error(operation_area_id)
        if area_error is not None:
            return area_error
        return jsonify({
            "operation_area_id": operation_area_id,
            "operation_area_code": (operation_area or {}).get("code"),
            "pois": [
                {
                    "id": p.id,
                    "name": p.name,
                    "lon": p.lon,
                    "lat": p.lat,
                    "zone": p.zone,
                }
                for p in city_map.pois
            ]
        })


@bp.route("/map/road-network", methods=["GET"])
def get_road_network():
    """获取前端绘图所需的路网数据。

    Request:
        GET /map/road-network

    Returns:
        JSON: 路网节点字典、有向边列表、POI ID 列表和地图边界。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400

    with state.state_lock:
        operation_area_id = _request_operation_area_id()
        operation_area = _operation_area_by_area_id(operation_area_id)
        city_map, area_error = _city_for_operation_area_or_error(operation_area_id)
        if area_error is not None:
            return area_error
        nodes = {
            node_id: {
                "id": node.id,
                "lon": node.lon,
                "lat": node.lat,
                "name": node.name,
                "zone": node.zone,
                "is_poi": node.is_poi,
            }
            for node_id, node in city_map.nodes_map.items()
        }
        lons = [node["lon"] for node in nodes.values()]
        lats = [node["lat"] for node in nodes.values()]

        return jsonify({
            "nodes": nodes,
            "edges": city_map.edges,
            "pois": [p.id for p in city_map.pois],
            "operation_area_id": operation_area_id,
            "operation_area_code": (operation_area or {}).get("code"),
            "bounds": {
                "min_lon": min(lons),
                "max_lon": max(lons),
                "min_lat": min(lats),
                "max_lat": max(lats),
            },
        })
