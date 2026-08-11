# -*- coding: utf-8 -*-
"""通勤快线 HTTP API。

本文件只负责通勤快线接口解析和响应封装，核心匹配逻辑放在
api.commute_express.CommuteExpressService 中，避免污染动态巴士调度接口。
"""

from flask import Blueprint, jsonify, request

from . import persistence, state
from .commute_express import CommuteExpressError, CommuteExpressService
from .error_logger import log_exception


bp = Blueprint("commute_routes", __name__)


# ============================================================
# 功能一：通用响应和运行态辅助
# 相关方法：_json_body、_error_response、_line_runtime_context
# ============================================================

def _json_body():
    """读取 JSON 请求体；空请求体按空对象处理。"""
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CommuteExpressError("请求体必须是 JSON 对象", code="invalid_json_body", status_code=400)
    return data


def _error_response(code, message, status_code=400, field=None):
    """生成稳定错误响应。"""
    payload = {"error": code, "message": message}
    if field:
        payload["field"] = field
    return jsonify(payload), status_code


def _handle_exception(exc):
    """把业务异常转换为 HTTP JSON 响应。"""
    if isinstance(exc, CommuteExpressError):
        if exc.status_code >= 500:
            log_exception("api.commute_routes.error", exc, context={"status": exc.status_code, "code": exc.code})
        return _error_response(exc.code, str(exc), exc.status_code, exc.field)
    if isinstance(exc, persistence.PersistenceUnavailable):
        log_exception("api.commute_routes.error", exc, context={"status": 503, "code": "database_unavailable"})
        return _error_response("database_unavailable", str(exc) or "数据库不可用", 503)
    if isinstance(exc, persistence.PersistenceConflict):
        code = getattr(exc, "code", "conflict")
        status_code = 404 if code == "commute_stop_not_found_by_coordinate" else 409
        return _error_response(code, str(exc), status_code, getattr(exc, "field", None))
    if isinstance(exc, KeyError):
        return _error_response(str(exc) or "not_found", "资源不存在", 404)
    if isinstance(exc, ValueError):
        return _error_response("invalid_request", str(exc), 400)
    log_exception("api.commute_routes.error", exc, context={"status": 500, "code": "commute_internal_error"})
    return _error_response("commute_internal_error", str(exc), 500)


def _runtime_vehicle_by_code(vehicle_code):
    """从当前运行车队里按车辆业务编码查找车辆。"""
    vehicle_code = str(vehicle_code or "").strip()
    if not vehicle_code:
        return None
    for vehicle in state.fleet or []:
        if (
            str(getattr(vehicle, "vehicle_id", "") or "") == vehicle_code
            or str(getattr(vehicle, "id", "") or "") == vehicle_code
        ):
            return vehicle
    return None


def _vehicle_snapshot(vehicle):
    """生成通勤快线接口使用的单车运行态摘要。"""
    if vehicle is None:
        return None
    planned_route = []
    for step in getattr(vehicle, "planned_route", []) or []:
        order = step.get("order")
        target_poi_id = (
            getattr(order, "commute_origin_poi_id", None)
            if step.get("type") == "O"
            else getattr(order, "commute_destination_poi_id", None)
        )
        target_node = (
            getattr(order, "o_node", None)
            if step.get("type") == "O"
            else getattr(order, "d_node", None)
        )
        planned_route.append({
            "type": step.get("type"),
            "request_id": getattr(order, "request_id", None),
            "line_code": getattr(order, "line_code", None),
            "target_poi_id": target_poi_id,
            "target_station_name": getattr(target_node, "name", None),
            "status": getattr(order, "status", None),
        })
    return {
        "vehicle_id": getattr(vehicle, "vehicle_id", None) or getattr(vehicle, "id", None),
        "vehicle_code": getattr(vehicle, "vehicle_id", None) or getattr(vehicle, "id", None),
        "plate_no": getattr(vehicle, "plate_no", None),
        "operation_mode": getattr(vehicle, "operation_mode", None),
        "operation_area_id": getattr(vehicle, "operation_area_id", None),
        "gps": getattr(vehicle, "gps", None),
        "last_node": getattr(vehicle, "last_node", None),
        "next_node": getattr(vehicle, "next_node", None),
        "planned_route": planned_route,
    }


def _commute_result_payload(result):
    """把服务层结果转换成可 JSON 序列化的响应体。"""
    payload = dict(result or {})
    vehicle = payload.pop("vehicle", None)
    if vehicle is not None:
        payload["vehicle"] = _vehicle_snapshot(vehicle)
    return payload


def _line_runtime_context(line_code, *, with_stops=True):
    """读取线路和同运营区车队。"""
    line = persistence.get_commute_line(line_code, with_stops=with_stops)
    if not line:
        raise CommuteExpressError("通勤快线线路不存在", code="commute_line_not_found", status_code=404)
    operation_area_id = line.get("operation_area_id")
    return line, state.fleet_for_operation_area(operation_area_id)


def _sync_runtime_vehicle_assignment(assignment):
    """车辆绑定快线后同步运行态车辆的业务模式和运营区。"""
    vehicle = _runtime_vehicle_by_code(assignment.get("vehicle_code"))
    if vehicle is None:
        return False
    vehicle.operation_mode = assignment.get("task_mode")
    vehicle.operation_area_id = assignment.get("operation_area_id")
    vehicle.commute_line_code = assignment.get("line_code")
    for area_fleet in (state.fleet_by_area or {}).values():
        if vehicle in area_fleet:
            area_fleet.remove(vehicle)
    state.fleet_by_area.setdefault(vehicle.operation_area_id, []).append(vehicle)
    return True


# ============================================================
# 功能二：线路管理接口
# 相关接口：/commute/lines、/commute/lines/<line_code>/stops
# ============================================================

@bp.route("/commute/lines", methods=["GET"])
def list_commute_lines():
    """查询通勤快线线路列表。"""
    try:
        include_deleted = str(request.args.get("include_deleted") or "").lower() in {"1", "true", "yes"}
        return jsonify({"lines": persistence.list_commute_lines(include_deleted=include_deleted)})
    except Exception as exc:
        return _handle_exception(exc)


@bp.route("/commute/lines", methods=["POST"])
def create_commute_line():
    """创建通勤快线线路，可同时携带 stops 初始化固定站序。"""
    try:
        data = _json_body()
        line = persistence.save_commute_line(data, create=True)
        if isinstance(data.get("stops"), list):
            line["stops"] = persistence.replace_commute_line_stops(line["line_code"], data["stops"])
        else:
            line["stops"] = []
        return jsonify({"status": "created", "line": line}), 201
    except Exception as exc:
        return _handle_exception(exc)


@bp.route("/commute/lines/<line_code>", methods=["GET"])
def get_commute_line(line_code):
    """查询单条通勤快线线路。"""
    try:
        line = persistence.get_commute_line(line_code, with_stops=True)
        if not line:
            return _error_response("commute_line_not_found", "通勤快线线路不存在", 404)
        return jsonify({"line": line})
    except Exception as exc:
        return _handle_exception(exc)


@bp.route("/commute/lines/<line_code>", methods=["PUT"])
def update_commute_line(line_code):
    """更新通勤快线线路主信息。"""
    try:
        data = _json_body()
        data["line_code"] = line_code
        line = persistence.save_commute_line(data, create=False)
        if isinstance(data.get("stops"), list):
            line["stops"] = persistence.replace_commute_line_stops(line_code, data["stops"])
        else:
            line["stops"] = persistence.list_commute_line_stops(line_code)
        return jsonify({"status": "updated", "line": line})
    except Exception as exc:
        return _handle_exception(exc)


@bp.route("/commute/lines/<line_code>", methods=["DELETE"])
def delete_commute_line(line_code):
    """软删除通勤快线线路。"""
    try:
        deleted = persistence.delete_commute_line(line_code)
        if not deleted:
            return _error_response("commute_line_not_found", "通勤快线线路不存在", 404)
        return jsonify({"status": "deleted", "line_code": line_code})
    except Exception as exc:
        return _handle_exception(exc)


@bp.route("/commute/lines/<line_code>/stops", methods=["PUT"])
def replace_commute_line_stops(line_code):
    """整体替换通勤快线固定站序。"""
    try:
        data = _json_body()
        stops = data.get("stops")
        if not isinstance(stops, list) or not stops:
            return _error_response("commute_stops_required", "stops 必须是非空数组", 400, "stops")
        result = persistence.replace_commute_line_stops(line_code, stops)
        if result is None:
            return _error_response("commute_line_not_found", "通勤快线线路不存在", 404)
        return jsonify({"status": "updated", "line_code": line_code, "stops": result})
    except Exception as exc:
        return _handle_exception(exc)


# ============================================================
# 功能三：车辆绑定和快线订单接口
# 相关接口：/commute/vehicles/assign、/commute/orders
# ============================================================

@bp.route("/commute/vehicles/assign", methods=["POST"])
def assign_commute_vehicle():
    """把车辆绑定到通勤快线线路，并设置任务模式。"""
    try:
        data = _json_body()
        with state.state_lock:
            assignment = persistence.assign_commute_vehicle(data)
            runtime_applied = _sync_runtime_vehicle_assignment(assignment)
        return jsonify({
            "status": "assigned",
            "assignment": assignment,
            "runtime_applied": runtime_applied,
        })
    except Exception as exc:
        return _handle_exception(exc)


@bp.route("/commute/orders", methods=["POST"])
def create_commute_order():
    """创建通勤快线订单并尝试按固定线路匹配车辆。"""
    try:
        data = _json_body()
        line_code = str(data.get("line_code") or "").strip()
        if not line_code:
            return _error_response("line_code_required", "line_code 不能为空", 400, "line_code")
        _, fleet = _line_runtime_context(line_code, with_stops=True)
        with state.state_lock:
            result = CommuteExpressService.create_order(data, fleet, request_time=state.now_datetime())
        return jsonify(_commute_result_payload(result)), 201
    except Exception as exc:
        return _handle_exception(exc)


@bp.route("/commute/orders/<request_id>", methods=["GET"])
def get_commute_order(request_id):
    """查询通勤快线订单。"""
    try:
        order = persistence.get_commute_order(request_id)
        if not order:
            return _error_response("commute_order_not_found", "通勤快线订单不存在", 404)
        return jsonify({"order": order})
    except Exception as exc:
        return _handle_exception(exc)


@bp.route("/commute/orders/<request_id>/cancel", methods=["POST"])
def cancel_commute_order(request_id):
    """取消通勤快线订单。"""
    try:
        order = persistence.get_commute_order(request_id)
        if not order:
            return _error_response("commute_order_not_found", "通勤快线订单不存在", 404)
        fleet = state.fleet_for_operation_area(order.get("operation_area_id"))
        with state.state_lock:
            result = CommuteExpressService.cancel_order(request_id, fleet)
        return jsonify(result)
    except Exception as exc:
        return _handle_exception(exc)
