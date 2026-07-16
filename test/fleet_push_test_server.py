# -*- coding: utf-8 -*-
"""Local test server for vehicle navigation push callbacks."""

import json
import os
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
from flask import Flask, jsonify, request


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 18080
MAX_SNAPSHOTS = 50
LOG_PATH = Path("runtime_logs") / "fleet_push_snapshots.jsonl"

app = Flask(__name__)
_lock = threading.Lock()
_snapshots = deque(maxlen=MAX_SNAPSHOTS)
_confirmations = {}


def _now_text():
    """Return local time text without microseconds."""
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _write_snapshot_log(snapshot):
    """Append one received payload record to the local JSONL log."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False, default=str) + "\n")


def _vehicle_id_from_snapshot(snapshot):
    """Return the vehicle id carried by one stored push record."""
    if not isinstance(snapshot, dict):
        return ""
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    return str(
        snapshot.get("path_vehicle_id")
        or payload.get("vehicle_id")
        or snapshot.get("vehicle_id")
        or ""
    )


def _confirmation_key(vehicle_id, request_id, route_version=None):
    """Build an in-memory confirmation key."""
    return (
        str(vehicle_id or ""),
        str(request_id or ""),
    )


def _pending_navigation_entries(vehicle_id):
    """Return pending driver confirmation entries for one vehicle."""
    vehicle_id = str(vehicle_id or "").strip()
    pending_by_key = {}
    latest = None
    with _lock:
        snapshots = list(_snapshots)
        confirmations = dict(_confirmations)
    for snapshot in reversed(snapshots):
        if _vehicle_id_from_snapshot(snapshot) != vehicle_id:
            continue
        if latest is None:
            latest = snapshot
        payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
        request_id = str(payload.get("confirmation_request_id") or payload.get("request_id") or "")
        if not request_id or not payload.get("driver_push_confirmation_required"):
            continue
        route_version = str(payload.get("driver_push_route_version") or payload.get("route_version") or "")
        key = _confirmation_key(vehicle_id, request_id)
        if key in pending_by_key:
            continue
        if confirmations.get(key, {}).get("status") in {"confirmed", "rejected"}:
            continue
        pending_by_key[key] = {
            "vehicle_id": vehicle_id,
            "request_id": request_id,
            "route_version": route_version,
            "event_reason": payload.get("event_reason"),
            "event_type": payload.get("event_type"),
            "received_at": snapshot.get("received_at"),
            "platform_message_id": f"{vehicle_id}:{request_id}:{route_version or 'latest'}",
            "vehicle": payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else None,
        }
    return list(pending_by_key.values()), latest


def _find_pending_navigation(vehicle_id, request_id, route_version=None):
    """Find one pending navigation entry by vehicle and request id."""
    entries, latest = _pending_navigation_entries(vehicle_id)
    for entry in entries:
        if str(entry.get("request_id")) != str(request_id):
            continue
        return entry, latest
    return None, latest


def _record_payload(payload, endpoint, path_vehicle_id=None):
    """Store and log one push payload."""
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "request body must be a JSON object"}), 400

    snapshot = {
        "received_at": _now_text(),
        "remote_addr": request.remote_addr,
        "endpoint": endpoint,
        "path_vehicle_id": path_vehicle_id,
        "event_type": payload.get("event_type"),
        "event_reason": payload.get("event_reason"),
        "vehicle_id": payload.get("vehicle_id"),
        "request_id": payload.get("request_id"),
        "route_version": payload.get("route_version"),
        "vehicle_present": isinstance(payload.get("vehicle"), dict),
        "fleet_present": "fleet" in payload,
        "fleet_size": len(payload.get("fleet") or []),
        "payload": payload,
    }
    with _lock:
        _snapshots.append(snapshot)
        count = len(_snapshots)
    _write_snapshot_log(snapshot)
    print(
        "[FleetPushTest] received "
        f"endpoint={endpoint} path_vehicle={path_vehicle_id or '-'} "
        f"payload_vehicle={snapshot['vehicle_id']} reason={snapshot['event_reason']} "
        f"request={snapshot['request_id']} route_version={snapshot['route_version']} "
        f"vehicle_present={snapshot['vehicle_present']} fleet_present={snapshot['fleet_present']}"
    )
    return jsonify({"ok": True, "count": count, "snapshot": snapshot})


@app.after_request
def add_cors_headers(response):
    """Allow direct browser access to the test server."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/", methods=["GET"])
def index():
    """Return a minimal page for inspecting the latest push payload."""
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Vehicle Navigation Push Test Server</title>
  <style>
    body { margin: 24px; font-family: Arial, sans-serif; background: #111827; color: #e5e7eb; }
    button { padding: 8px 12px; border: 0; border-radius: 6px; background: #2563eb; color: #fff; cursor: pointer; }
    pre { padding: 12px; border-radius: 8px; background: #020617; overflow: auto; max-height: 70vh; }
    .meta { color: #93c5fd; margin: 12px 0; }
  </style>
</head>
<body>
  <h1>Vehicle Navigation Push Test Server</h1>
  <button onclick="loadLatest()">Refresh Latest</button>
  <button onclick="resetSnapshots()">Reset Memory Records</button>
  <div id="meta" class="meta"></div>
  <pre id="payload">Waiting for push...</pre>
  <script>
    async function loadLatest() {
      const res = await fetch('/latest');
      const data = await res.json();
      document.getElementById('meta').textContent =
        `count=${data.count}, received_at=${data.latest ? data.latest.received_at : '-'}`;
      document.getElementById('payload').textContent = JSON.stringify(data.latest || data, null, 2);
    }
    async function resetSnapshots() {
      await fetch('/reset', { method: 'POST' });
      await loadLatest();
    }
    loadLatest();
    setInterval(loadLatest, 3000);
  </script>
</body>
</html>
"""


@app.route("/health", methods=["GET"])
def health():
    """Health check."""
    with _lock:
        count = len(_snapshots)
    return jsonify({
        "ok": True,
        "service": "fleet_push_test_server",
        "count": count,
        "log_path": str(LOG_PATH),
        "primary_endpoint": "/bus/python-dispatch/internal/fleet/<vehicle_id>/push-navigation",
        "frontend_pending_endpoint": "/platform/fleet/<vehicle_id>/pending-navigation",
    })


@app.route("/bus/python-dispatch/internal/fleet/<path:vehicle_id>/push-navigation", methods=["POST", "OPTIONS"])
def receive_vehicle_navigation(vehicle_id):
    """Receive the new single vehicle navigation payload."""
    if request.method == "OPTIONS":
        return "", 204
    return _record_payload(
        request.get_json(silent=True),
        endpoint="vehicle_navigation",
        path_vehicle_id=vehicle_id,
    )


@app.route("/fleet/snapshot", methods=["POST", "OPTIONS"])
def receive_fleet_snapshot():
    """Compatibility endpoint for older full fleet snapshot pushes."""
    if request.method == "OPTIONS":
        return "", 204
    return _record_payload(
        request.get_json(silent=True),
        endpoint="fleet_snapshot_legacy",
    )


@app.route("/platform/fleet/<path:vehicle_id>/pending-navigation", methods=["GET", "OPTIONS"])
def pending_navigation_for_vehicle(vehicle_id):
    """Return pending driver confirmation entries for the selected vehicle."""
    if request.method == "OPTIONS":
        return "", 204
    entries, latest = _pending_navigation_entries(vehicle_id)
    return jsonify({
        "ok": True,
        "vehicle_id": vehicle_id,
        "count": len(entries),
        "pending": entries,
        "latest": latest,
    })


@app.route(
    "/platform/fleet/<path:vehicle_id>/orders/<path:request_id>/driver-push-confirmation",
    methods=["POST", "OPTIONS"],
)
def confirm_driver_push_from_platform(vehicle_id, request_id):
    """Proxy frontend confirmation/rejection to the dispatch algorithm service."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or {}
    if "received" not in data:
        return jsonify({"ok": False, "error": "received is required"}), 400
    received = data.get("received")
    if not isinstance(received, bool):
        return jsonify({"ok": False, "error": "received must be boolean"}), 400

    pending, latest = _find_pending_navigation(vehicle_id, request_id)
    if pending is None:
        return jsonify({
            "ok": False,
            "error": "pending_navigation_not_found",
            "vehicle_id": vehicle_id,
            "request_id": request_id,
            "route_version": data.get("route_version"),
            "latest": latest,
        }), 404

    dispatch_base_url = (
        str(data.get("dispatch_base_url") or os.getenv("DISPATCH_API_BASE_URL") or "http://127.0.0.1:5000")
        .rstrip("/")
    )
    dispatch_url = f"{dispatch_base_url}/orders/{quote(str(request_id), safe='')}/driver-push-confirmation"
    payload = {
        "vehicle_id": vehicle_id,
        "received": received,
        "reason": data.get("reason") or ("driver_app_ack" if received else "driver_push_unreachable"),
        "platform_message_id": data.get("platform_message_id") or pending.get("platform_message_id"),
        "occurred_at": data.get("occurred_at") or _now_text(),
    }
    try:
        response = requests.post(dispatch_url, json=payload, timeout=float(data.get("timeout") or 5))
        dispatch_payload = response.json() if response.content else {}
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": "dispatch_confirmation_failed",
            "message": str(exc),
            "dispatch_url": dispatch_url,
        }), 502

    if not response.ok:
        return jsonify({
            "ok": False,
            "error": "dispatch_confirmation_rejected",
            "status_code": response.status_code,
            "dispatch_response": dispatch_payload,
            "dispatch_url": dispatch_url,
        }), response.status_code

    key = _confirmation_key(vehicle_id, request_id)
    with _lock:
        _confirmations[key] = {
            "status": "confirmed" if received else "rejected",
            "received": received,
            "reason": payload["reason"],
            "confirmed_at": _now_text(),
            "dispatch_response": dispatch_payload,
        }
    return jsonify({
        "ok": True,
        "status": "confirmed" if received else "rejected",
        "vehicle_id": vehicle_id,
        "request_id": request_id,
        "route_version": pending.get("route_version"),
        "dispatch_response": dispatch_payload,
    })


@app.route("/latest", methods=["GET"])
def latest_snapshot():
    """Return the most recently received push payload."""
    with _lock:
        latest = _snapshots[-1] if _snapshots else None
        count = len(_snapshots)
    return jsonify({"ok": True, "count": count, "latest": latest})


@app.route("/snapshots", methods=["GET"])
def list_snapshots():
    """Return recent push payload records from memory."""
    with _lock:
        snapshots = list(_snapshots)
    return jsonify({"ok": True, "count": len(snapshots), "snapshots": snapshots})


@app.route("/reset", methods=["POST", "OPTIONS"])
def reset_snapshots():
    """Clear in-memory push records without deleting the JSONL log."""
    if request.method == "OPTIONS":
        return "", 204
    with _lock:
        _snapshots.clear()
        _confirmations.clear()
    return jsonify({"ok": True, "count": 0})


if __name__ == "__main__":
    host = os.getenv("FLEET_PUSH_TEST_HOST", DEFAULT_HOST)
    port = int(os.getenv("FLEET_PUSH_TEST_PORT", DEFAULT_PORT))
    print(f"[FleetPushTest] listening on http://127.0.0.1:{port}")
    print("[FleetPushTest] receive endpoint: POST /bus/python-dispatch/internal/fleet/<vehicle_id>/push-navigation")
    print("[FleetPushTest] legacy endpoint: POST /fleet/snapshot")
    app.run(host=host, port=port, debug=False)
