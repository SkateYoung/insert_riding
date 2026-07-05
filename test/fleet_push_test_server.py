# -*- coding: utf-8 -*-
"""Fleet 推送测试服务端。

用于接收 api.fleet_push 默认发送到 http://127.0.0.1:18080/fleet/snapshot
的完整车队快照，便于本地联调路径变更推送。
"""

import json
import os
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 18080
MAX_SNAPSHOTS = 50
LOG_PATH = Path("runtime_logs") / "fleet_push_snapshots.jsonl"

app = Flask(__name__)
_lock = threading.Lock()
_snapshots = deque(maxlen=MAX_SNAPSHOTS)


def _now_text():
    """返回秒级本地时间字符串。"""
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _write_snapshot_log(snapshot):
    """把收到的 fleet payload 追加写入本地 JSONL 日志。"""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False, default=str) + "\n")


@app.after_request
def add_cors_headers(response):
    """允许浏览器直接访问测试服务。"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/", methods=["GET"])
def index():
    """返回一个极简查看页。"""
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Fleet Push Test Server</title>
  <style>
    body { margin: 24px; font-family: Arial, "Microsoft YaHei", sans-serif; background: #111827; color: #e5e7eb; }
    button { padding: 8px 12px; border: 0; border-radius: 6px; background: #2563eb; color: #fff; cursor: pointer; }
    pre { padding: 12px; border-radius: 8px; background: #020617; overflow: auto; max-height: 70vh; }
    .meta { color: #93c5fd; margin: 12px 0; }
  </style>
</head>
<body>
  <h1>Fleet Push Test Server</h1>
  <button onclick="loadLatest()">刷新最新推送</button>
  <button onclick="resetSnapshots()">清空内存记录</button>
  <div id="meta" class="meta"></div>
  <pre id="payload">等待推送...</pre>
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
    """健康检查。"""
    with _lock:
        count = len(_snapshots)
    return jsonify({
        "ok": True,
        "service": "fleet_push_test_server",
        "count": count,
        "log_path": str(LOG_PATH),
    })


@app.route("/fleet/snapshot", methods=["POST", "OPTIONS"])
def receive_fleet_snapshot():
    """接收主系统推送的完整 fleet 快照。"""
    if request.method == "OPTIONS":
        return "", 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "request body must be a JSON object"}), 400

    snapshot = {
        "received_at": _now_text(),
        "remote_addr": request.remote_addr,
        "event_type": payload.get("event_type"),
        "event_reason": payload.get("event_reason"),
        "vehicle_id": payload.get("vehicle_id"),
        "request_id": payload.get("request_id"),
        "route_version": payload.get("route_version"),
        "fleet_size": len(payload.get("fleet") or []),
        "payload": payload,
    }
    with _lock:
        _snapshots.append(snapshot)
        count = len(_snapshots)
    _write_snapshot_log(snapshot)
    print(
        "[FleetPushTest] received "
        f"reason={snapshot['event_reason']} vehicle={snapshot['vehicle_id']} "
        f"request={snapshot['request_id']} fleet_size={snapshot['fleet_size']}"
    )
    return jsonify({"ok": True, "count": count, "snapshot": snapshot})


@app.route("/latest", methods=["GET"])
def latest_snapshot():
    """查看最近一次收到的推送。"""
    with _lock:
        latest = _snapshots[-1] if _snapshots else None
        count = len(_snapshots)
    return jsonify({"ok": True, "count": count, "latest": latest})


@app.route("/snapshots", methods=["GET"])
def list_snapshots():
    """查看内存中最近的推送列表。"""
    with _lock:
        snapshots = list(_snapshots)
    return jsonify({"ok": True, "count": len(snapshots), "snapshots": snapshots})


@app.route("/reset", methods=["POST", "OPTIONS"])
def reset_snapshots():
    """清空内存中的推送记录，日志文件不删除。"""
    if request.method == "OPTIONS":
        return "", 204
    with _lock:
        _snapshots.clear()
    return jsonify({"ok": True, "count": 0})


if __name__ == "__main__":
    host = os.getenv("FLEET_PUSH_TEST_HOST", DEFAULT_HOST)
    port = int(os.getenv("FLEET_PUSH_TEST_PORT", DEFAULT_PORT))
    print(f"[FleetPushTest] listening on http://127.0.0.1:{port}")
    print("[FleetPushTest] receive endpoint: POST /fleet/snapshot")
    app.run(host=host, port=port, debug=False)
