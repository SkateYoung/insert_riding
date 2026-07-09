# -*- coding: utf-8 -*-
"""Vehicle navigation push helpers."""

import copy
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from urllib.parse import quote

import requests


DEFAULT_FLEET_PUSH_BASE_URL = "http://127.0.0.1:18080"
DEFAULT_VEHICLE_NAVIGATION_PATH = "/bus/python-dispatch/internal/fleet/{vehicleId}/push-navigation"
DEFAULT_FLEET_PUSH_TIMEOUT_SECONDS = 2.0

_executor = None
_executor_lock = threading.Lock()


def _push_base_url():
    """Read the vehicle navigation push base URL."""
    return (os.getenv("FLEET_PUSH_BASE_URL") or DEFAULT_FLEET_PUSH_BASE_URL).rstrip("/")


def _vehicle_identity(vehicle):
    """Return the business vehicle id, falling back to the internal id."""
    if vehicle is None:
        return None
    return getattr(vehicle, "vehicle_id", None) or getattr(vehicle, "id", None)


def _push_url_for_vehicle(vehicle_id, base_url=None):
    """Build the target URL for a single vehicle navigation push."""
    vehicle_id = str(vehicle_id or "").strip()
    if not vehicle_id:
        return None
    encoded_vehicle_id = quote(vehicle_id, safe="")
    return (
        (base_url or _push_base_url()).rstrip("/")
        + DEFAULT_VEHICLE_NAVIGATION_PATH.format(vehicleId=encoded_vehicle_id)
    )


def _executor_instance():
    """Lazily create the async push executor."""
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="FleetPush")
        return _executor


def _json_safe(value):
    """Convert common runtime objects to JSON-serializable values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _node_snapshot(node):
    """Serialize a road node for the vehicle snapshot."""
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
    """Serialize an order for the vehicle snapshot."""
    if order is None:
        return None
    return {
        "request_id": getattr(order, "request_id", None),
        "status": getattr(order, "status", None),
        "passenger_count": getattr(order, "passenger_count", None),
        "passenger_phone": getattr(order, "passenger_phone", None),
        "passenger_id": getattr(order, "passenger_id", None),
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
    """Serialize one planned route step for the vehicle snapshot."""
    order = step.get("order") if isinstance(step, dict) else None
    step_type = step.get("type") if isinstance(step, dict) else None
    target = getattr(order, "o_node", None) if step_type == "O" else getattr(order, "d_node", None)
    return {
        "type": step_type,
        "request_id": getattr(order, "request_id", None),
        "target_node": _node_snapshot(target),
    }


def vehicle_snapshot(vehicle):
    """Serialize a vehicle into the navigation push snapshot."""
    return _json_safe({
        "id": getattr(vehicle, "id", None),
        "vehicle_id": _vehicle_identity(vehicle),
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
        "on_board_count": sum(
            getattr(order, "passenger_count", 0)
            for order in getattr(vehicle, "on_board_orders", []) or []
        ),
        "on_board_orders": [
            _order_snapshot(order)
            for order in getattr(vehicle, "on_board_orders", []) or []
        ],
        "planned_route": [
            _route_step_snapshot(step)
            for step in getattr(vehicle, "planned_route", []) or []
        ],
        "planned_route_point": copy.deepcopy(getattr(vehicle, "planned_route_point", None) or []),
        "planned_route_grasped_point": copy.deepcopy(getattr(vehicle, "planned_route_grasped_point", None) or []),
        "planned_route_segment_grasped_point": copy.deepcopy(
            getattr(vehicle, "planned_route_segment_grasped_point", None) or []
        ),
        "planned_route_grasp_status": getattr(vehicle, "planned_route_grasp_status", None),
        "planned_route_grasp_error": getattr(vehicle, "planned_route_grasp_error", None),
        "planned_route_grasp_route_version": getattr(vehicle, "planned_route_grasp_route_version", None),
        "idle_target": copy.deepcopy(getattr(vehicle, "idle_target", None)),
        "idle_forecast": copy.deepcopy(getattr(vehicle, "idle_forecast", None)),
        "idle_target_eta_seconds": getattr(vehicle, "idle_target_eta_seconds", None),
        "idle_target_eta_time": getattr(vehicle, "idle_target_eta_time", None),
        "idle_target_eta_status": getattr(vehicle, "idle_target_eta_status", None),
        "idle_target_eta_error": getattr(vehicle, "idle_target_eta_error", None),
        "operation_restriction_policy_signature": getattr(
            vehicle,
            "operation_restriction_policy_signature",
            None,
        ),
    })


def build_payload(vehicle, event):
    """Build the single vehicle navigation push payload."""
    clean_event = _json_safe(event or {})
    vehicle_id = clean_event.get("vehicle_id") or _vehicle_identity(vehicle)
    return {
        "event_type": clean_event.get("event_type") or "fleet_route_changed",
        "event_reason": clean_event.get("event_reason"),
        "vehicle_id": vehicle_id,
        "request_id": clean_event.get("request_id"),
        "route_version": clean_event.get("route_version"),
        "pushed_at": datetime.now().replace(microsecond=0).isoformat(sep=" "),
        "vehicle": vehicle_snapshot(vehicle),
    }


def _post_payload(url, payload, timeout):
    """Post one payload and log failures without raising."""
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return True
    except Exception as exc:
        print(f"[FleetPush] vehicle navigation push failed: {exc}")
        return False


def submit_vehicle_navigation(vehicle, event, url_base=None, timeout=None):
    """Submit one vehicle navigation snapshot asynchronously."""
    vehicle_id = _vehicle_identity(vehicle)
    target_url = _push_url_for_vehicle(vehicle_id, base_url=url_base)
    if vehicle is None or not target_url:
        return False
    payload = build_payload(vehicle, event)
    _executor_instance().submit(
        _post_payload,
        target_url,
        payload,
        DEFAULT_FLEET_PUSH_TIMEOUT_SECONDS if timeout is None else float(timeout),
    )
    return True


def submit_fleet_snapshot(fleet, event, url=None, timeout=None):
    """Compatibility entrypoint: find the target vehicle and push only that vehicle."""
    clean_event = _json_safe(event or {})
    target_vehicle_id = str(clean_event.get("vehicle_id") or "").strip()
    if not target_vehicle_id:
        return False
    for vehicle in fleet or []:
        if str(_vehicle_identity(vehicle) or "").strip() == target_vehicle_id:
            return submit_vehicle_navigation(vehicle, clean_event, url_base=url, timeout=timeout)
    return False
