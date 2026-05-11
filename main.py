# main.py
"""打车平台主干引导引擎 — Flask 架构版。
提供 RESTful API 以便测试与集成，保留原有分层架构（models / core / auxiliary）。
"""

import subprocess
import sys
import os
import io
import threading
import time

# # 强制 UTF-8 输出，解决 Windows 控制台 GBK 乱码问题
# try:
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
# except (AttributeError, OSError):
#     sys.stdout.reconfigure(encoding="utf-8")

try:
    import shapefile
except ImportError:
    print("检测到系统中缺失解析 shp 文件的模块 pyshp，正在为您自动拉取按装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyshp"])
    import shapefile
    print("pyshp 挂载成功！")

from flask import Flask, request, jsonify

from models import CityGraph, Vehicle, Order, SPEED_MPS
from core import CoreDispatcher
from auxiliary import AuxiliaryFunctions

app = Flask(__name__)

# ── 全局状态 ──
city = None
fleet = None
matching_thread = None
system_initialized = False


# ── 序列化工具 ──
def _vehicle_to_dict(v):
    """将 Vehicle 对象转为 JSON 可序列化的字典。"""
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
        "last_node": v.last_node,
        "next_node": v.next_node,
        "progress": v.progress,
        "driving_time": v.driving_time,
        "is_resting": v.is_resting,
        "is_rest_requested": v.is_rest_requested,
    }


# ── 系统初始化 ──
def init_system(shp_path="dxc_traffic_shp/dxc_rule.shp"):
    """加载路网、创建车队、启动后台匹配引擎。"""
    global city, fleet, matching_thread, system_initialized

    city = CityGraph(shp_path)

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

    matching_thread = threading.Thread(
        target=CoreDispatcher.process_pool_matching,
        args=(fleet, city),
        daemon=True,
        name="OrderMatchingEngine",
    )
    matching_thread.start()

    system_initialized = True


# ── CORS 支持 ──
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ── API 路由 ──

@app.route("/health", methods=["GET"])
def health():
    """健康检查。"""
    return jsonify({"status": "ok", "initialized": system_initialized})


@app.route("/init", methods=["POST"])
def init_route():
    """初始化整个调度系统（加载路网、车队、启动匹配引擎）。

    请求体 (JSON, 可选):
        shp_path: SHP 文件路径，默认 "dxc_traffic_shp/dxc_rule.shp"
    """
    global system_initialized
    if system_initialized:
        return jsonify({"status": "already_initialized",
                        "nodes": len(city.nodes_map),
                        "pois": len(city.pois)})
    data = request.get_json(silent=True) or {}
    shp_path = data.get("shp_path", "dxc_traffic_shp/dxc_rule.shp")
    try:
        init_system(shp_path)
        return jsonify({
            "status": "initialized",
            "nodes": len(city.nodes_map),
            "pois": len(city.pois),
            "edges": len(city.edges),
        })
    except FileNotFoundError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/order", methods=["POST"])
def create_order():
    """创建新订单并注入调度池。

    请求体 (JSON):
        plon: 上车经度 (默认 113.395)
        plat: 上车纬度 (默认 23.045)
        dlon: 下车经度 (默认 113.410)
        dlat: 下车纬度 (默认 23.055)
    """
    if not system_initialized:
        return jsonify({"error": "系统未初始化，请先调用 POST /init"}), 400

    data = request.get_json(silent=True) or {}
    plon = data.get("plon", 113.395)
    plat = data.get("plat", 23.045)
    dlon = data.get("dlon", 113.410)
    dlat = data.get("dlat", 23.055)

    order_id = int(time.time() * 1000) % 100000
    order = Order(order_id, plon, plat, dlon, dlat, req_time=time.time(), city_map=city)
    CoreDispatcher.pool_and_route_planning(fleet, order, city)

    return jsonify({
        "status": "pooled",
        "order_id": order.id,
        "pickup_node": order.p_node.name,
        "pickup_coords": {"lon": order.p_node.lon, "lat": order.p_node.lat},
        "dropoff_node": order.d_node.name,
        "dropoff_coords": {"lon": order.d_node.lon, "lat": order.d_node.lat},
        "pool_size": len(CoreDispatcher.order_pool),
    })


@app.route("/orders/pool", methods=["GET"])
def get_order_pool():
    """查看订单池当前状态。"""
    if not system_initialized:
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


@app.route("/fleet", methods=["GET"])
def get_fleet():
    """获取全部车辆状态。"""
    if not system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    return jsonify({"fleet": [_vehicle_to_dict(v) for v in fleet]})


@app.route("/fleet/<vehicle_id>", methods=["GET"])
def get_vehicle(vehicle_id):
    """获取单辆车状态。"""
    if not system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    for v in fleet:
        if v.id == vehicle_id:
            return jsonify(_vehicle_to_dict(v))
    return jsonify({"error": "车辆未找到"}), 404


@app.route("/tick", methods=["POST"])
def tick_vehicles():
    """推进所有车辆的时间步进（用于物理仿真测试）。

    请求体 (JSON, 可选):
        dt: 步进秒数，默认 1.0
    """
    if not system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    data = request.get_json(silent=True) or {}
    dt = float(data.get("dt", 1.0))
    for v in fleet:
        v.tick(dt)
    return jsonify({
        "dt": dt,
        "fleet": [_vehicle_to_dict(v) for v in fleet],
    })


@app.route("/status", methods=["GET"])
def full_status():
    """获取系统全量状态快照。"""
    if not system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    return jsonify({
        "initialized": system_initialized,
        "nodes_count": len(city.nodes_map),
        "pois_count": len(city.pois),
        "edges_count": len(city.edges),
        "fleet": [_vehicle_to_dict(v) for v in fleet],
        "order_pool_size": len(CoreDispatcher.order_pool),
        "completed_orders": len(CoreDispatcher.completed_orders_pool),
    })


@app.route("/export", methods=["POST"])
def export_visualization():
    """导出可视化数据到 map_data.js（供前端 demo.html 使用）。"""
    if not system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path", "map_data.js")
    try:
        AuxiliaryFunctions.export_visualization_data(city, file_path, fleet, speed_mps=SPEED_MPS)
        return jsonify({"status": "ok", "file": file_path})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/pois", methods=["GET"])
def get_pois():
    """获取所有 POI 站点列表。"""
    if not system_initialized:
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
            for p in city.pois
        ]
    })


# ── 入口 ──
if __name__ == "__main__":
    print("调度系统后端节点启动初始化中...")
    try:
        init_system()
        print(f"[系统] 路网加载完成：{len(city.nodes_map)} 节点，{len(city.pois)} POI")
        print("[系统] 后台统筹派单引擎已在独立线程启动。")
    except Exception as e:
        print(f"[警告] 自动初始化失败: {e}")
        print("[提示] 可通过 POST /init 手动初始化")

    port = int(os.environ.get("PORT", 5000))
    print(f"\n[OK] Flask API 已就绪: http://localhost:{port}")
    print("   可用端点: /health /init /order /fleet /orders/pool /status /tick /export /pois\n")
    app.run(host="0.0.0.0", port=port, debug=False)
