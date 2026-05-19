"""Flask API 路由层。

本模块只负责 HTTP 请求解析、参数校验和 JSON 响应组装。
调度、寻路、预测等业务逻辑统一委托给 api.core.CoreDispatcher。
"""

import time

from flask import Blueprint, jsonify, request

from . import state
from .auxiliary import AuxiliaryFunctions
from .core import CoreDispatcher
from .models import Order, SPEED_MPS


bp = Blueprint("api_routes", __name__)


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
        "on_board_count": len(v.on_board_orders),
        "on_board_orders": [o.id for o in v.on_board_orders],
        "gps": v.gps,
        "idle_target": v.idle_target,
        "idle_forecast": v.idle_forecast,
        "planned_route": [
            {
                "type": s["type"],
                "order_id": s["order"].id,
                "node_name": (
                    s["order"].p_node.name
                    if s["type"] == "P"
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
    }


@bp.route("/health", methods=["GET"])
def health():
    """健康检查接口。

    Request:
        GET /health

    Returns:
        JSON: status 表示服务状态，initialized 表示系统是否已完成初始化。
    """
    return jsonify({"status": "ok", "initialized": state.system_initialized})


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
    if state.system_initialized:
        return jsonify({
            "status": "already_initialized",
            "nodes": len(state.city.nodes_map),
            "pois": len(state.city.pois),
        })

    data = request.get_json(silent=True) or {}
    shp_path = data.get("shp_path", "dxc_traffic_shp/dxc_rule.shp")
    try:
        state.init_system(shp_path)
        return jsonify({
            "status": "initialized",
            "nodes": len(state.city.nodes_map),
            "pois": len(state.city.pois),
            "edges": len(state.city.edges),
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
        Body JSON 可选字段:
            plon/plat (float): 乘客上车原始经纬度。
            dlon/dlat (float): 乘客下车原始经纬度。

    Returns:
        JSON: 新订单 ID、吸附后的上下车 POI 信息和当前订单池大小。
    """
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化，请先调用 POST /init"}), 400

    data = request.get_json(silent=True) or {}
    plon = data.get("plon", 113.395)
    plat = data.get("plat", 23.045)
    dlon = data.get("dlon", 113.410)
    dlat = data.get("dlat", 23.055)

    order_id = int(time.time() * 1000) % 100000
    order = Order(order_id, plon, plat, dlon, dlat, req_time=time.time(), city_map=state.city)
    CoreDispatcher.pool_and_route_planning(state.fleet, order, state.city)

    return jsonify({
        "status": "pooled",
        "order_id": order.id,
        "pickup_node": order.p_node.name,
        "pickup_coords": {"lon": order.p_node.lon, "lat": order.p_node.lat},
        "dropoff_node": order.d_node.name,
        "dropoff_coords": {"lon": order.d_node.lon, "lat": order.d_node.lat},
        "pool_size": len(CoreDispatcher.order_pool),
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
    return jsonify({
        "pool_size": len(CoreDispatcher.order_pool),
        "completed_size": len(CoreDispatcher.completed_orders_pool),
        "orders": [
            {
                "id": o.id,
                "pickup": o.p_node.name,
                "dropoff": o.d_node.name,
                "req_time": o.req_time,
            }
            for o in CoreDispatcher.order_pool
        ],
    })


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

    target_vehicle = None
    for v in state.fleet:
        if v.id == vehicle_id:
            target_vehicle = v
            break
    if target_vehicle is None:
        return jsonify({"error": "车辆未找到"}), 404

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

    path_result = CoreDispatcher.rebuild_vehicle_path_from_gps(target_vehicle, state.city, lon, lat)
    if path_result is None:
        return jsonify({"error": "当前订单计划中存在不可达路段"}), 409

    return jsonify({
        "vehicle_id": target_vehicle.id,
        **path_result,
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
    data = request.get_json(silent=True) or {}
    dt = float(data.get("dt", 1.0))
    for v in state.fleet:
        v.tick(dt)
    return jsonify({
        "dt": dt,
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
    return jsonify({
        "initialized": state.system_initialized,
        "nodes_count": len(state.city.nodes_map),
        "pois_count": len(state.city.pois),
        "edges_count": len(state.city.edges),
        "fleet": [_vehicle_to_dict(v) for v in state.fleet],
        "order_pool_size": len(CoreDispatcher.order_pool),
        "completed_orders": len(CoreDispatcher.completed_orders_pool),
    })


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
