# fleet_push.py
"""车辆路线变更后的车队快照推送工具。"""

import copy
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import requests


DEFAULT_FLEET_PUSH_URL = "http://127.0.0.1:18080/fleet/snapshot"
DEFAULT_FLEET_PUSH_TIMEOUT_SECONDS = 2.0

_executor = None
_executor_lock = threading.Lock()


def _push_url():
    """读取 fleet 推送地址，未配置时使用本地临时服务地址。"""
    return os.getenv("FLEET_PUSH_URL") or DEFAULT_FLEET_PUSH_URL


def _executor_instance():
    """懒加载异步推送线程池。"""
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="FleetPush")
        return _executor


def _json_safe(value):
    """递归转换为 requests json 参数可序列化的数据。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
            if key != "fleet_ref"
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _node_snapshot(node):
    """把路网节点对象转换为快照字段。"""
    if node is None:
        return None
    return {
        "id": getattr(node, "id", None),
        "lon": getattr(node, "lon", None),
        "lat": getattr(node, "lat", None),
        "name": getattr(node, "name", None),
        "zone": getattr(node, "zone", None),
    }


def _order_snapshot(order):
    """把订单对象转换为 fleet 推送中的轻量快照。"""
    if order is None:
        return None
    return {
        "request_id": getattr(order, "request_id", None),
        "status": getattr(order, "status", None),
        "passenger_count": getattr(order, "passenger_count", None),
        "origin": _node_snapshot(getattr(order, "o_node", None)),
        "destination": _node_snapshot(getattr(order, "d_node", None)),
        "request_time": getattr(order, "request_time", None),
        "expected_pickup_earliest": getattr(order, "expected_pickup_earliest", None),
        "expected_pickup_latest": getattr(order, "expected_pickup_latest", None),
        "answer_time": getattr(order, "answer_time", None),
        "actual_pickup_time": getattr(order, "actual_pick_time", None),
        "completion_time": getattr(order, "completion_time", None),
        "eta_status": getattr(order, "eta_status", None),
        "eta_error": getattr(order, "eta_error", None),
        "estimated_arrival_time": getattr(order, "estimated_arrival_time", None),
        "estimated_dropoff_time": getattr(order, "estimated_dropoff_time", None),
    }


def _route_step_snapshot(step):
    """把车辆 planned_route 步骤转换为快照字段。"""
    order = step.get("order") if isinstance(step, dict) else None
    step_type = step.get("type") if isinstance(step, dict) else None
    target = getattr(order, "o_node", None) if step_type == "O" else getattr(order, "d_node", None)
    return {
        "type": step_type,
        "request_id": getattr(order, "request_id", None),
        "target_node": _node_snapshot(target),
    }


def vehicle_snapshot(vehicle):
    """把车辆对象转换为 fleet 推送快照。"""
    return _json_safe({
        "id": getattr(vehicle, "id", None),
        "vehicle_id": getattr(vehicle, "vehicle_id", None) or getattr(vehicle, "id", None),
        "vehicle_code": getattr(vehicle, "vehicle_code", None),
        "plate_no": getattr(vehicle, "plate_no", None),
        "driver_id": getattr(vehicle, "driver_id", None),
        "driver_no": getattr(vehicle, "driver_no", None),
        "current_driver_code": getattr(vehicle, "current_driver_code", None),
        "gps": copy.deepcopy(getattr(vehicle, "gps", {}) or {}),
        "last_node": getattr(vehicle, "last_node", None),
        "next_node": getattr(vehicle, "next_node", None),
        "progress": getattr(vehicle, "progress", None),
        "operation_status": getattr(vehicle, "operation_status", getattr(vehicle, "rest_status", None)),
        "rest_status": getattr(vehicle, "rest_status", None),
        "is_resting": getattr(vehicle, "is_resting", None),
        "is_rest_requested": getattr(vehicle, "is_rest_requested", None),
        "on_board_count": sum(getattr(order, "passenger_count", 0) for order in getattr(vehicle, "on_board_orders", []) or []),
        "on_board_orders": [_order_snapshot(order) for order in getattr(vehicle, "on_board_orders", []) or []],
        "planned_route": [_route_step_snapshot(step) for step in getattr(vehicle, "planned_route", []) or []],
        "planned_route_point": copy.deepcopy(getattr(vehicle, "planned_route_point", None) or []),
        "planned_route_grasped_point": copy.deepcopy(getattr(vehicle, "planned_route_grasped_point", None) or []),
        "planned_route_segment_grasped_point": copy.deepcopy(getattr(vehicle, "planned_route_segment_grasped_point", None) or []),
        "planned_route_grasp_status": getattr(vehicle, "planned_route_grasp_status", None),
        "planned_route_grasp_error": getattr(vehicle, "planned_route_grasp_error", None),
        "planned_route_grasp_route_version": getattr(vehicle, "planned_route_grasp_route_version", None),
        "idle_target": copy.deepcopy(getattr(vehicle, "idle_target", None)),
        "idle_forecast": copy.deepcopy(getattr(vehicle, "idle_forecast", None)),
        "idle_target_eta_seconds": getattr(vehicle, "idle_target_eta_seconds", None),
        "idle_target_eta_time": getattr(vehicle, "idle_target_eta_time", None),
        "idle_target_eta_status": getattr(vehicle, "idle_target_eta_status", None),
        "idle_target_eta_error": getattr(vehicle, "idle_target_eta_error", None),
        "operation_restriction_policy_signature": getattr(vehicle, "operation_restriction_policy_signature", None),
    })


def fleet_snapshot(fleet):
    """把车队对象列表转换为完整快照。"""
    return [vehicle_snapshot(vehicle) for vehicle in fleet or []]


def build_payload(fleet, event):
    """构造发送给外部服务端的 fleet payload。"""
    clean_event = _json_safe(event or {})
    return {
        "event_type": clean_event.get("event_type") or "fleet_route_changed",
        "event_reason": clean_event.get("event_reason"),
        "vehicle_id": clean_event.get("vehicle_id"),
        "request_id": clean_event.get("request_id"),
        "route_version": clean_event.get("route_version"),
        "pushed_at": datetime.now().replace(microsecond=0).isoformat(sep=" "),
        "fleet": fleet_snapshot(fleet),
    }


def _post_payload(url, payload, timeout):
    """执行一次 HTTP 推送，失败只打印日志。"""
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return True
    except Exception as exc:
        print(f"[FleetPush] 推送 fleet 快照失败：{exc}")
        return False


def submit_fleet_snapshot(fleet, event, url=None, timeout=None):
    """异步推送完整 fleet 快照。

    Returns:
        bool: 成功提交到线程池返回 True；未提供 fleet 时返回 False。
    """
    if fleet is None:
        return False
    target_url = url or _push_url()
    payload = build_payload(fleet, event)
    _executor_instance().submit(
        _post_payload,
        target_url,
        payload,
        DEFAULT_FLEET_PUSH_TIMEOUT_SECONDS if timeout is None else float(timeout),
    )
    return True
