"""Flask API 路由层。

本模块只负责 HTTP 请求解析、参数校验和 JSON 响应组装。
调度、寻路、预测等业务逻辑统一委托给 api.core.CoreDispatcher。
"""

from flask import Blueprint, jsonify, request

from . import state
from .auxiliary import AuxiliaryFunctions
from .core import CoreDispatcher
from .models import Order, SPEED_MPS


bp = Blueprint("api_routes", __name__)

REST_STATUS_TEXT = {
    "operating": "运营中",
    "preparing_closure": "准备收车中",
    "closing": "收车中",
    "resting": "休息中",
}


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
        "time": v.time,
        "time_text": state.format_timestamp(v.time),
        "on_board_count": sum(o.passenger_count for o in v.on_board_orders),
        "on_board_orders": [o.request_id for o in v.on_board_orders],
        "gps": v.gps,
        "idle_target": v.idle_target,
        "idle_forecast": v.idle_forecast,
        "planned_route": [
            {
                "type": s["type"],
                "request_id": s["order"].request_id,
                "node_name": (
                    s["order"].o_node.name
                    if s["type"] == "O"
                    else s["order"].d_node.name
                ),
            }
            for s in v.planned_route
        ],
        "planned_route_point": v.planned_route_point,
        "last_node": v.last_node,
        "next_node": v.next_node,
        "progress": v.progress,
        "driving_time": v.driving_time,
        "is_resting": v.is_resting,
        "is_rest_requested": v.is_rest_requested,
        "rest_status": getattr(v, "rest_status", "operating"),
        "rest_status_text": REST_STATUS_TEXT.get(getattr(v, "rest_status", "operating"), "未知"),
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
        "rest_timer": getattr(v, "rest_timer", 0.0),
        "rest_started_time": getattr(v, "rest_started_time", None),
        "rest_started_time_text": (
            state.format_timestamp(v.rest_started_time)
            if getattr(v, "rest_started_time", None) is not None
            else None
        ),
        "can_accept_order": CoreDispatcher._vehicle_can_accept_order(v),
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
    return jsonify({"status": "ok", "initialized": state.system_initialized})


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
    data = request.get_json(silent=True) or {}
    shp_path = data.get("shp_path", "dxc_traffic_shp/dxc_rule.shp")
    try:
        with state.state_lock:
            if state.system_initialized:
                return jsonify({
                    "status": "already_initialized",
                    "nodes": len(state.city.nodes_map),
                    "pois": len(state.city.pois),
                })
            state.init_system(shp_path)
            return jsonify({
                "status": "initialized",
                "nodes": len(state.city.nodes_map),
                "pois": len(state.city.pois),
                "edges": len(state.city.edges),
                "system_time": state.current_time(),
            })
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

    try:
        request_id = str(data["request_id"])
        o_lon = float(origin["lon"])
        o_lat = float(origin["lat"])
        d_lon = float(destination["lon"])
        d_lat = float(destination["lat"])
        expected_pickup_earliest = _parse_datetime(expected_pickup_time.get("earliest"), "expected_pickup_time.earliest")
        expected_pickup_latest = _parse_datetime(expected_pickup_time.get("latest"), "expected_pickup_time.latest")
        passenger_count = int(data["passenger_count"])
    except KeyError as exc:
        return jsonify({"error": f"缺少必填字段: {exc.args[0]}"}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

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
            city_map=state.city,
            req_time=time_snapshot["timestamp"],
        )
        CoreDispatcher.pool_and_route_planning(state.fleet, order, state.city)
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
                    "req_time": o.req_time,
                }
                for o in CoreDispatcher.order_pool
            ],
        })


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
        result = CoreDispatcher.cancel_order(request_id, state.fleet, state.city, cancel_time=state.now_datetime())
    if result["status"] == "not_found":
        return jsonify(result), 404
    if result["status"] == "rejected":
        return jsonify(result), 409
    return jsonify(result)


# ============================================================
# 功能三：车辆状态、实时路径更新与仿真推进接口
# 相关接口：/fleet、/fleet/<vehicle_id>、/fleet/<vehicle_id>/path、/fleet/<vehicle_id>/rest、/tick、/status
# ============================================================

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
        return jsonify({"fleet": [_vehicle_to_dict(v) for v in state.fleet]})


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
        for v in state.fleet:
            if v.id == vehicle_id:
                return jsonify(_vehicle_to_dict(v))
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
        JSON: 吸附点、更新后的 planned_route_point、上下客变更和车辆订单状态。
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
        target_vehicle = None
        for v in state.fleet:
            if v.id == vehicle_id:
                target_vehicle = v
                break
        if target_vehicle is None:
            return jsonify({"error": "车辆未找到"}), 404

        path_result = CoreDispatcher.rebuild_vehicle_path_from_gps(target_vehicle, state.city, lon, lat)
    if path_result is None:
        return jsonify({"error": "当前订单计划中存在不可达路段"}), 409

    return jsonify({
        "vehicle_id": target_vehicle.id,
        **path_result,
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
        target_vehicle = None
        for v in state.fleet:
            if v.id == vehicle_id:
                target_vehicle = v
                break
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
            state.city,
            desired_rest_time=desired_rest_time,
            rest_duration_seconds=rest_duration_seconds,
        )
        estimated_finish_time = result.get("estimated_finish_time")
        return jsonify({
            "vehicle_id": target_vehicle.id,
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
        return jsonify({
            "initialized": state.system_initialized,
            "system_time": state.current_time(),
            "nodes_count": len(state.city.nodes_map),
            "pois_count": len(state.city.pois),
            "edges_count": len(state.city.edges),
            "fleet": [_vehicle_to_dict(v) for v in state.fleet],
            "order_pool_size": len(CoreDispatcher.order_pool),
            "completed_orders": len(CoreDispatcher.completed_orders_pool),
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
            AuxiliaryFunctions.export_visualization_data(state.city, file_path, state.fleet, speed_mps=SPEED_MPS)
        return jsonify({"status": "ok", "file": file_path})
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
        return jsonify({
            "pois": [
                {
                    "id": p.id,
                    "name": p.name,
                    "lon": p.lon,
                    "lat": p.lat,
                    "zone": p.zone,
                }
                for p in state.city.pois
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
        nodes = {
            node_id: {
                "id": node.id,
                "lon": node.lon,
                "lat": node.lat,
                "name": node.name,
                "zone": node.zone,
                "is_poi": node.is_poi,
            }
            for node_id, node in state.city.nodes_map.items()
        }
        lons = [node["lon"] for node in nodes.values()]
        lats = [node["lat"] for node in nodes.values()]

        return jsonify({
            "nodes": nodes,
            "edges": state.city.edges,
            "pois": [p.id for p in state.city.pois],
            "bounds": {
                "min_lon": min(lons),
                "max_lon": max(lons),
                "min_lat": min(lats),
                "max_lat": max(lats),
            },
        })
