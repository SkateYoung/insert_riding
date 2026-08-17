"""高德整车 ETA pipeline。

本模块只消费上游已经生成好的 O/D/IDLE 分段路线，不负责派单和寻路。
当前运行链路优先使用分段里已有的高德驾车规划耗时；缺少耗时时才降级请求高德 ETA。
旧轨迹纠偏方法保留为兼容代码，但后台订单 ETA 刷新不再调用纠偏接口。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import socket
import ssl
import threading
import time
# 这个只是用来在前端测试的 如果只调用函数的时候 可以不用
# from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_AMAP_KEY = "00c35fbeab3953e19656422ef6d4107f"
DEFAULT_SPEED_MPS = 16.666666666666668
MAX_GRASP_POINTS = 500
MAX_DRIVING_WAYPOINTS = 16
GRASP_ROAD_POINT_INTERVAL_SECONDS = 5
DEFAULT_AMAP_HTTP_RETRIES = 3
DEFAULT_AMAP_HTTP_RETRY_DELAY_SECONDS = 0.4

try:
    import certifi
except ImportError:  # pragma: no cover - depends on deployment environment.
    certifi = None

AMAP_TRAFFIC_RANK = {
    "unknown": 0,
    "smooth": 1,
    "slow": 2,
    "congested": 3,
    "blocked": 4,
    "未知": 0,
    "畅通": 1,
    "缓行": 2,
    "拥堵": 3,
    "严重拥堵": 4,
}


def env_flag(name: str, default: str = "") -> bool:
    """读取布尔环境变量。"""
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    """读取整数环境变量，格式错误时使用默认值。"""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float) -> float:
    """读取浮点环境变量，格式错误时使用默认值。"""
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def to_float_or_none(value: Any) -> float | None:
    """把可选数值安全转换成 float。"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """计算两个经纬度点之间的大圆距离，单位为米。"""
    radius = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """计算从第一个经纬度点指向第二个点的方位角。"""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def polyline_distance(points: list[dict[str, Any]]) -> float:
    """累计一条经纬度折线的总长度，单位为米。"""
    total = 0.0
    for a, b in zip(points, points[1:]):
        total += haversine(float(a["lon"]), float(a["lat"]), float(b["lon"]), float(b["lat"]))
    return total


def normalize_point(item: Any) -> dict[str, Any] | None:
    """把 dict/object 风格的点统一转成 {lon, lat, id?}。"""
    if item is None:
        return None

    if isinstance(item, dict):
        source = item.get("node") if isinstance(item.get("node"), dict) else item
        lon = source.get("lon", source.get("x"))
        lat = source.get("lat", source.get("y"))
        try:
            point = {"lon": float(lon), "lat": float(lat)}
        except (TypeError, ValueError):
            return None
        point_id = source.get("id") or source.get("nodeId")
        if point_id is not None:
            point["id"] = str(point_id)
        return point

    try:
        lon = getattr(item, "lon")
        lat = getattr(item, "lat")
        point = {"lon": float(lon), "lat": float(lat)}
        point_id = getattr(item, "id", None) or getattr(item, "nodeId", None)
        if point_id is not None:
            point["id"] = str(point_id)
        return point
    except (AttributeError, TypeError, ValueError):
        return None


def normalize_points(points: list[Any]) -> list[dict[str, Any]]:
    """批量归一化轨迹点，并去掉相邻重复点。"""
    out: list[dict[str, Any]] = []
    for item in points or []:
        point = normalize_point(item)
        if point is None:
            continue
        if out and same_point(out[-1], point):
            continue
        out.append(point)
    return out


def same_point(a: dict[str, Any], b: dict[str, Any], *, tol: float = 1e-9) -> bool:
    """判断两个经纬度点是否可视为同一个点。"""
    return abs(float(a["lon"]) - float(b["lon"])) <= tol and abs(float(a["lat"]) - float(b["lat"])) <= tol


def coord_text(point: dict[str, Any]) -> str:
    """把点格式化成高德接口需要的 lon,lat 字符串。"""
    return f"{float(point['lon']):.6f},{float(point['lat']):.6f}"


async def run_blocking_io(func: Any, *args: Any, **kwargs: Any) -> Any:
    """兼容 Python 3.8：在线程池里运行阻塞 I/O。"""
    to_thread = getattr(asyncio, "to_thread", None)
    if to_thread is not None:
        return await to_thread(func, *args, **kwargs)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


def sample_polyline(
    points: list[dict[str, Any]],
    *,
    max_points: int = MAX_GRASP_POINTS,
    spacing_m: float = 85.0,
) -> list[dict[str, Any]]:
    """按距离对 A* 折线重采样，控制高德纠偏请求点数。"""
    if len(points) <= 2:
        return [dict(p) for p in points]

    seg_lens = [haversine(float(a["lon"]), float(a["lat"]), float(b["lon"]), float(b["lat"])) for a, b in zip(points, points[1:])]
    total = sum(seg_lens)
    if total <= 0:
        return [dict(points[0]), dict(points[-1])]

    target_count = min(max_points, max(2, int(total / max(1.0, spacing_m)) + 1))
    distances = [total * i / (target_count - 1) for i in range(target_count)]
    out: list[dict[str, Any]] = []
    seg_idx = 0
    seg_start_dist = 0.0

    for target in distances:
        while seg_idx < len(seg_lens) - 1 and seg_start_dist + seg_lens[seg_idx] < target:
            seg_start_dist += seg_lens[seg_idx]
            seg_idx += 1
        a = points[seg_idx]
        b = points[seg_idx + 1]
        seg_len = max(seg_lens[seg_idx], 1e-9)
        t = max(0.0, min(1.0, (target - seg_start_dist) / seg_len))
        out.append({
            "lon": float(a["lon"]) + (float(b["lon"]) - float(a["lon"])) * t,
            "lat": float(a["lat"]) + (float(b["lat"]) - float(a["lat"])) * t,
        })

    out[0] = dict(points[0])
    out[-1] = dict(points[-1])
    return out


def sample_waypoints(points: list[dict[str, Any]], max_waypoints: int = MAX_DRIVING_WAYPOINTS) -> list[dict[str, Any]]:
    """从纠偏轨迹中抽取高德驾车规划的途经点。"""
    if len(points) <= 2 or max_waypoints <= 0:
        return []
    middle = points[1:-1]
    if len(middle) <= max_waypoints:
        return [dict(p) for p in middle]
    last = len(middle) - 1
    idxs = sorted({round(i * last / (max_waypoints - 1)) for i in range(max_waypoints)})
    return [dict(middle[i]) for i in idxs]


def parse_step_polyline(steps: list[dict[str, Any]]) -> list[dict[str, float]]:
    """解析高德 driving steps 里的 polyline 字符串。"""
    out: list[dict[str, float]] = []
    for step in steps or []:
        raw = step.get("polyline") or ""
        for item in raw.split(";"):
            if "," not in item:
                continue
            lon_s, lat_s = item.split(",", 1)
            try:
                out.append({"lon": float(lon_s), "lat": float(lat_s)})
            except ValueError:
                continue
    return out


class AmapEtaCorrectClient:
    """封装高德纠偏和驾车 ETA 两类接口，并提供简单内存缓存。"""

    def __init__(self, api_key: str | None = None, *, timeout_sec: float = 6.0) -> None:
        """初始化高德客户端；支持 AMAP_DISABLE=1 离线禁用。"""
        if env_flag("AMAP_DISABLE"):
            self.api_key = ""
        else:
            self.api_key = (api_key or os.getenv("AMAP_API_KEY") or DEFAULT_AMAP_KEY).strip()
        self.timeout_sec = timeout_sec
        self.retry_count = max(1, env_int("AMAP_HTTP_RETRIES", DEFAULT_AMAP_HTTP_RETRIES))
        self.retry_delay_sec = max(0.0, env_float("AMAP_HTTP_RETRY_DELAY_SECONDS", DEFAULT_AMAP_HTTP_RETRY_DELAY_SECONDS))
        self.bypass_proxy = env_flag("AMAP_BYPASS_PROXY", "1")
        self.ssl_verify = not env_flag("AMAP_SSL_NO_VERIFY")
        self._ssl_context = self._build_ssl_context()
        self._opener = self._build_opener()
        self._drive_cache: dict[str, dict[str, Any]] = {}
        self._grasp_cache: dict[str, dict[str, Any]] = {}

    @property
    def enabled(self) -> bool:
        """返回当前是否具备可用的高德 Key。"""
        return bool(self.api_key)

    async def grasp_driving(self, points: list[dict[str, Any]], speed_mps: float = DEFAULT_SPEED_MPS) -> dict[str, Any]:
        """调用高德轨迹纠偏接口，把 A* 折线纠正到真实道路形状。"""
        if not self.enabled:
            return {"ok": False, "reason": "missing_api_key"}
        normalized = normalize_points(points)
        if len(normalized) < 2:
            return {"ok": False, "reason": "too_few_points"}

        # 与前端 GraspRoad 调用保持同类输入格式：直接使用原始路径点构造 x/y/ag/tm/sp，
        # 不再按距离重采样，避免纠偏结果因输入点过稀而返回点数过少。

        payload = self._build_grasp_payload(normalized, speed_mps)
        cache_key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        cached = self._grasp_cache.get(cache_key)
        if cached:
            result = dict(cached)
            result["cached"] = True
            return result

        try:
            url = f"https://restapi.amap.com/v4/grasproad/driving?{urlencode({'key': self.api_key})}"
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            response = await run_blocking_io(self._urlopen_json, req)
            result = self._parse_grasp_response(response)
            result["request_points"] = len(payload)
            result["cached"] = False
            if result.get("ok"):
                self._grasp_cache[cache_key] = dict(result)
            return result
        except Exception as exc:
            return {"ok": False, "error": str(exc), "request_points": len(payload)}

    def grasp_driving_sync(self, points: list[dict[str, Any]], speed_mps: float = DEFAULT_SPEED_MPS) -> dict[str, Any]:
        """同步调用高德轨迹纠偏接口，供后台线程使用。"""
        return _run_sync(self.grasp_driving(points, speed_mps))

    def _build_grasp_payload(self, points: list[dict[str, Any]], speed_mps: float) -> list[dict[str, Any]]:
        """把轨迹点转换成高德纠偏接口需要的 x/y/ag/tm/sp 格式。"""
        now_epoch = int(time.time())
        out: list[dict[str, Any]] = []
        for idx, point in enumerate(points):
            prev = points[idx - 1] if idx > 0 else point
            if idx < len(points) - 1:
                nxt = points[idx + 1]
                angle = bearing(float(point["lon"]), float(point["lat"]), float(nxt["lon"]), float(nxt["lat"]))
            else:
                angle = bearing(float(prev["lon"]), float(prev["lat"]), float(point["lon"]), float(point["lat"]))

            if idx == 0:
                tm = now_epoch
                speed_kmh = 20.0
            else:
                distance_from_previous = haversine(
                    float(prev["lon"]),
                    float(prev["lat"]),
                    float(point["lon"]),
                    float(point["lat"]),
                )
                tm = idx * GRASP_ROAD_POINT_INTERVAL_SECONDS
                speed_kmh = max(
                    5.0,
                    min(
                        80.0,
                        distance_from_previous / GRASP_ROAD_POINT_INTERVAL_SECONDS * 3.6,
                    ),
                )

            out.append({
                "x": float(point["lon"]),
                "y": float(point["lat"]),
                "ag": angle or 1.0,
                "tm": tm,
                "sp": round(speed_kmh, 1),
            })
        return out

    def _build_ssl_context(self) -> ssl.SSLContext:
        """构建高德 HTTPS 请求使用的 SSL 上下文。

        部署机证书链不完整时，优先使用 certifi 证书包；仅当显式设置
        AMAP_SSL_NO_VERIFY=1 时才关闭证书校验，便于临时诊断网络问题。
        """
        if not self.ssl_verify:
            return ssl._create_unverified_context()
        cafile = certifi.where() if certifi is not None else None
        return ssl.create_default_context(cafile=cafile)

    def _build_opener(self):
        """构建 urllib opener，默认绕过系统代理避免代理截断高德 TLS。"""
        handlers = [HTTPSHandler(context=self._ssl_context)]
        if self.bypass_proxy:
            handlers.insert(0, ProxyHandler({}))
        return build_opener(*handlers)

    def _parse_grasp_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        """解析高德纠偏响应，提取纠偏后的经纬度轨迹。"""
        errcode = payload.get("errcode")
        if errcode and str(errcode) not in {"0", "10000"}:
            return {
                "ok": False,
                "errcode": errcode,
                "errmsg": payload.get("errmsg"),
                "errdetail": payload.get("errdetail"),
            }
        data = payload.get("data") or {}
        raw_points = data.get("points") if isinstance(data, dict) else None
        if not raw_points:
            return {"ok": False, "reason": "empty_grasp_points", "payload": payload}
        points: list[dict[str, float]] = []
        for item in raw_points:
            try:
                points.append({"lon": float(item["x"]), "lat": float(item["y"])})
            except (KeyError, TypeError, ValueError):
                continue
        if len(points) < 2:
            return {"ok": False, "reason": "invalid_grasp_points"}
        return {
            "ok": True,
            "distance_m": float(data.get("distance") or polyline_distance(points)),
            "points": points,
            "raw": payload,
        }

    async def driving_eta(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        """用纠偏后的轨迹调用高德驾车规划，获取 ETA、距离和路线形状。"""
        if not self.enabled:
            return {"ok": False, "reason": "missing_api_key"}
        normalized = normalize_points(points)
        if len(normalized) < 2:
            return {"ok": False, "reason": "too_few_points"}

        origin = normalized[0]
        destination = normalized[-1]
        waypoints = sample_waypoints(normalized, max_waypoints=MAX_DRIVING_WAYPOINTS)
        params = {
            "key": self.api_key,
            "origin": coord_text(origin),
            "destination": coord_text(destination),
            "strategy": "32",
            "show_fields": "cost,polyline,tmcs",
            "output": "json",
        }
        if waypoints:
            params["waypoints"] = ";".join(coord_text(p) for p in waypoints)
        cache_key = json.dumps(params, sort_keys=True, separators=(",", ":"))
        cached = self._drive_cache.get(cache_key)
        if cached:
            result = dict(cached)
            result["cached"] = True
            return result

        try:
            url = f"https://restapi.amap.com/v5/direction/driving?{urlencode(params)}"
            req = Request(url, headers={"User-Agent": "insert-riding-eta-correct/1.0"})
            payload = await run_blocking_io(self._urlopen_json, req)
            result = self._parse_driving_response(payload)
            result["cached"] = False
            result["waypoint_count"] = len(waypoints)
            if result.get("ok"):
                self._drive_cache[cache_key] = dict(result)
            return result
        except Exception as exc:
            return {"ok": False, "error": str(exc), "waypoint_count": len(waypoints)}

    def driving_eta_sync(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        """同步调用高德驾车规划接口，供后台线程使用。"""
        return _run_sync(self.driving_eta(points))

    def _parse_driving_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        """解析高德驾车规划响应，提取耗时、距离、polyline 和最严重路况。"""
        if str(payload.get("status", "0")) != "1":
            return {
                "ok": False,
                "info": payload.get("info"),
                "infocode": payload.get("infocode"),
            }
        route = payload.get("route") or {}
        paths = route.get("paths") or []
        if not paths:
            return {"ok": False, "reason": "empty_paths"}
        best = paths[0]
        cost = best.get("cost") or {}
        duration = int(float(cost.get("duration") or best.get("duration") or 0))
        distance = int(float(best.get("distance") or 0))
        steps = best.get("steps") or []
        polyline = parse_step_polyline(steps)
        traffic_status = "未知"
        for step in steps:
            for tmc in step.get("tmcs") or []:
                status = str(tmc.get("tmc_status") or "未知")
                if AMAP_TRAFFIC_RANK.get(status, 0) > AMAP_TRAFFIC_RANK.get(traffic_status, 0):
                    traffic_status = status
        return {
            "ok": True,
            "duration_sec": duration,
            "distance_m": distance,
            "polyline": polyline,
            "traffic_status": traffic_status,
            "raw": payload,
        }

    def _urlopen_json(self, req: Request) -> dict[str, Any]:
        """在线程池中执行的同步 HTTP JSON 请求。"""
        last_error = None
        for attempt in range(1, self.retry_count + 1):
            try:
                with self._opener.open(req, timeout=self.timeout_sec) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (ssl.SSLError, socket.timeout, TimeoutError, URLError, OSError) as exc:
                last_error = exc
                if attempt >= self.retry_count:
                    break
                time.sleep(self.retry_delay_sec * attempt)
        raise RuntimeError(self._format_http_error(last_error))

    def _format_http_error(self, exc: BaseException | None) -> str:
        """输出带部署诊断信息的高德网络错误。"""
        if exc is None:
            return "amap_http_error"
        return (
            f"amap_http_error:{exc.__class__.__name__}:{exc};"
            f"retries={self.retry_count};"
            f"bypass_proxy={self.bypass_proxy};"
            f"ssl_verify={self.ssl_verify};"
            f"certifi={'yes' if certifi is not None else 'no'}"
        )


def normalize_stop_type(raw: Any) -> str:
    """统一停靠点类型，业务侧输出 O/D；兼容历史 P 写法。"""
    text = str(raw or "").strip().upper()
    if text in {"O", "P", "PICKUP", "ORIGIN"}:
        return "O"
    if text in {"D", "DROPOFF", "DELIVERY", "DESTINATION"}:
        return "D"
    return text


def normalize_end_step(step: dict[str, Any] | None) -> dict[str, Any]:
    """统一 O/D 停靠动作字段，输出 {type, orderId}。"""
    step = step or {}
    order = step.get("order") if isinstance(step.get("order"), dict) else {}
    order_id = step.get("orderId", step.get("order_id", order.get("id")))
    step_type = normalize_stop_type(step.get("type") or step.get("stepType"))
    return {"type": step_type, "orderId": order_id}


def normalize_order_id_value(order_id: Any) -> Any:
    """订单 ID 能转数字就转数字，否则保留字符串。"""
    if order_id is None:
        return None
    try:
        return int(order_id)
    except (TypeError, ValueError):
        return str(order_id)


def _step_node(step: dict[str, Any]) -> dict[str, Any] | None:
    """从停靠动作或订单对象里提取目标节点。"""
    node = step.get("node") or step.get("targetNode")
    if isinstance(node, dict):
        return node
    order = step.get("order") if isinstance(step.get("order"), dict) else {}
    step_type = normalize_stop_type(step.get("type"))
    if step_type == "O":
        for key in ("oNode", "pNode", "originNode", "pickupNode", "origin", "pickup", "o", "p"):
            if isinstance(order.get(key), dict):
                return order[key]
    if step_type == "D":
        for key in ("dNode", "destinationNode", "dropoffNode", "destination", "dropoff", "d"):
            if isinstance(order.get(key), dict):
                return order[key]
    if "lon" in step and "lat" in step:
        return step
    return None


def _node_id_from_point(point: dict[str, Any] | None) -> str | None:
    """从点对象里提取节点 ID。"""
    if not point:
        return None
    node_id = point.get("id") or point.get("nodeId")
    return str(node_id) if node_id is not None else None


def _with_vehicle_position_start(points: list[dict[str, Any]], vehicle_position: Any) -> list[dict[str, Any]]:
    """用实时车辆位置替换第一段起点，适配 5 秒刷新场景。"""
    current = normalize_point(vehicle_position)
    if current is None:
        return points
    if not points:
        return [current]
    adjusted = [dict(p) for p in points]
    adjusted[0] = current
    if len(adjusted) > 1 and same_point(adjusted[0], adjusted[1]):
        adjusted.pop(1)
    return adjusted


def normalize_input_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """归一化已经分好段的 payload.segments 输入。"""
    vehicle_position = payload.get("vehiclePosition") or payload.get("origin") or payload.get("currentPosition")
    replace_first = bool(payload.get("replaceFirstPointWithVehiclePosition", True))
    segments: list[dict[str, Any]] = []
    for idx, src in enumerate(payload.get("segments") or []):
        raw_points = normalize_points(
            src.get("points")
            or src.get("aStarPolyline")
            or src.get("astarPolyline")
            or src.get("polyline")
            or src.get("path")
            or []
        )
        if idx == 0 and replace_first:
            raw_points = _with_vehicle_position_start(raw_points, vehicle_position)
        if not raw_points:
            continue
        end_step = normalize_end_step(src.get("endStep") or src.get("action") or src)
        segment = {
            "index": src.get("index", len(segments)),
            "startNodeId": src.get("startNodeId") or _node_id_from_point(raw_points[0]),
            "endNodeId": src.get("endNodeId") or _node_id_from_point(raw_points[-1]),
            "endStep": end_step,
            "points": raw_points,
            "aStarDistanceM": float(src.get("aStarDistanceM") or polyline_distance(raw_points)),
            "durationSec": src.get("durationSec", src.get("duration_sec")),
            "distanceM": src.get("distanceM", src.get("distance_m")),
            "trafficStatus": src.get("trafficStatus", src.get("traffic_status")),
            "source": src.get("source"),
        }
        segments.append(segment)
    return segments


def build_segments_from_path_queue(vehicle_position: Any, path_queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从 demo/pathQueue 风格数据按 action 边界切出整车 O/D 段。"""
    start = normalize_point(vehicle_position)
    if start is None:
        return []

    segments: list[dict[str, Any]] = []
    points = [start]
    start_node_id = _node_id_from_point(start)
    for item in path_queue or []:
        node = normalize_point(item.get("node") if isinstance(item, dict) else item)
        if node is None:
            continue
        if not points or not same_point(points[-1], node):
            points.append(node)

        action = item.get("action") if isinstance(item, dict) else None
        if not action:
            continue
        end_step = normalize_end_step(action)
        if len(points) >= 2:
            segments.append({
                "index": len(segments),
                "startNodeId": start_node_id,
                "endNodeId": _node_id_from_point(node),
                "endStep": end_step,
                "points": [dict(p) for p in points],
                "aStarDistanceM": polyline_distance(points),
            })
        start_node_id = _node_id_from_point(node)
        points = [node]
    return segments


def _stop_to_end_step(stop: dict[str, Any]) -> dict[str, Any]:
    """把 stopSequence 中的停靠点转换成 endStep。"""
    order = stop.get("order") if isinstance(stop.get("order"), dict) else {}
    order_id = stop.get("orderId", stop.get("order_id", order.get("id")))
    step_type = normalize_stop_type(stop.get("type") or stop.get("stepType"))
    return {"type": step_type, "orderId": order_id}


def _stop_to_point(stop: dict[str, Any]) -> dict[str, Any] | None:
    """从 stopSequence 停靠点中提取经纬度。"""
    return normalize_point(_step_node(stop) or stop)


def _find_stop_index(path: list[dict[str, Any]], stop: dict[str, Any], start_idx: int) -> int | None:
    """在整条 A* 轨迹中定位某个 O/D 停靠点的下标。"""
    if stop.get("pathIndex") is not None:
        try:
            idx = int(stop["pathIndex"])
        except (TypeError, ValueError):
            return None
        return idx if start_idx <= idx < len(path) else None

    stop_point = _stop_to_point(stop)
    stop_node_id = stop.get("nodeId") or stop.get("id") or _node_id_from_point(stop_point)
    if stop_node_id is not None:
        stop_node_id = str(stop_node_id)
        for idx in range(start_idx, len(path)):
            if _node_id_from_point(path[idx]) == stop_node_id:
                return idx

    if stop_point is None:
        return None
    best_idx: int | None = None
    best_dist = float("inf")
    for idx in range(start_idx, len(path)):
        point = path[idx]
        dist = haversine(float(point["lon"]), float(point["lat"]), float(stop_point["lon"]), float(stop_point["lat"]))
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


def build_segments_from_astar_path(
    vehicle_position: Any,
    astar_path: list[Any],
    stop_sequence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """从完整 A* 轨迹和 O/D 顺序切出相邻停靠段。"""
    current = normalize_point(vehicle_position)
    path = normalize_points(astar_path)
    if current is not None:
        if path and same_point(path[0], current):
            path[0] = current
        else:
            path = [current] + path
    if len(path) < 2:
        return []

    segments: list[dict[str, Any]] = []
    start_idx = 0
    start_node_id = _node_id_from_point(path[0])
    for stop in stop_sequence or []:
        stop_idx = _find_stop_index(path, stop, start_idx + 1)
        if stop_idx is None or stop_idx <= start_idx:
            continue
        points = [dict(p) for p in path[start_idx:stop_idx + 1]]
        end_step = _stop_to_end_step(stop)
        segments.append({
            "index": len(segments),
            "startNodeId": start_node_id,
            "endNodeId": stop.get("nodeId") or _node_id_from_point(path[stop_idx]),
            "endStep": end_step,
            "points": points,
            "aStarDistanceM": polyline_distance(points),
        })
        start_idx = stop_idx
        start_node_id = _node_id_from_point(path[stop_idx])
    return segments


def extract_input_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """根据 payload 形态选择 segments、pathQueue 或 aStarPath 切段入口。"""
    if payload.get("segments"):
        return normalize_input_segments(payload)

    vehicle_position = payload.get("vehiclePosition") or payload.get("origin") or payload.get("currentPosition")
    if payload.get("pathQueue"):
        return build_segments_from_path_queue(vehicle_position, payload.get("pathQueue") or [])

    astar_path = payload.get("aStarPath") or payload.get("astarPath") or payload.get("path")
    stop_sequence = payload.get("stopSequence") or payload.get("plannedRoute") or []
    if astar_path and stop_sequence:
        return build_segments_from_astar_path(vehicle_position, astar_path, stop_sequence)

    return []


def choose_amap_eta(eta: dict[str, Any]) -> dict[str, Any]:
    """选择最终 ETA 来源；当前只采用高德结果，不启用 A* 保底。"""
    if not eta.get("ok"):
        return {"chosenDurationSec": None, "chosenSource": "amap_unavailable"}

    amap_duration = float(eta.get("duration_sec") or 0.0)
    traffic = str(eta.get("traffic_status") or "未知")
    if amap_duration <= 0:
        return {"chosenDurationSec": None, "chosenSource": "amap_unavailable"}
    if traffic in {"拥堵", "严重拥堵", "congested", "blocked"}:
        return {"chosenDurationSec": amap_duration, "chosenSource": "amap_congested"}
    return {"chosenDurationSec": amap_duration, "chosenSource": "amap"}


def advance_eta_prefix(current: float | None, segment_duration: float | None) -> float | None:
    """推进整车段前缀 ETA；任一前置段未知则后续保持未知。"""
    if current is None or segment_duration is None:
        return None
    return current + segment_duration


def sum_known_durations(segments: list[dict[str, Any]]) -> float | None:
    """汇总所有已知段耗时；存在未知段时返回 None。"""
    total = 0.0
    for segment in segments:
        duration = segment.get("chosenDurationSec")
        if duration is None:
            return None
        total += float(duration)
    return round(total, 1)


async def build_eta_pipeline_from_astar_async(
    payload: dict[str, Any],
    *,
    amap: AmapEtaCorrectClient | None = None,
    api_key: str | None = None,
    timeout_sec: float = 6.0,
) -> dict[str, Any]:
    """异步构建单车 ETA pipeline，并按订单输出接驾/送达 ETA。

    调用方传入的 segments[].points 应为已规划路线；本函数不再执行轨迹纠偏。
    """
    client = amap or AmapEtaCorrectClient(api_key=api_key, timeout_sec=timeout_sec)
    vehicle_id = str(payload.get("vehicleId") or payload.get("vehicle_id") or "")
    route_version = payload.get("routeVersion")
    if route_version is None:
        route_version = payload.get("route_version", 0)
    speed_mps = float(payload.get("speedMps") or payload.get("speed_mps") or DEFAULT_SPEED_MPS)
    input_segments = extract_input_segments(payload)

    segments: list[dict[str, Any]] = []
    vehicle_polyline: list[dict[str, Any]] = []
    segment_offsets: list[dict[str, Any]] = []
    eta_by_order: dict[str, dict[str, Any]] = {}
    idle_eta_sec: float | None = None
    idle_eta_distance_m: float | None = None
    cumulative_distance = 0.0
    cumulative_eta: float | None = 0.0

    for idx, src in enumerate(input_segments):
        raw_points = normalize_points(src.get("points") or [])
        if not raw_points:
            continue

        end_step = normalize_end_step(src.get("endStep") or {})
        order_id = end_step.get("orderId")
        step_type = normalize_stop_type(end_step.get("type"))
        fallback_dist = float(src.get("aStarDistanceM") or polyline_distance(raw_points))
        fallback_eta = fallback_dist / max(speed_mps, 1.0)
        planned_duration = to_float_or_none(src.get("durationSec", src.get("duration_sec")))
        planned_distance = to_float_or_none(src.get("distanceM", src.get("distance_m")))

        if len(raw_points) < 2:
            # 零长度 O/D 分段表示两个停靠点吸附到同一节点；不请求高德，ETA 沿用当前累计值。
            eta = {"ok": False, "reason": "zero_length_segment", "polyline": raw_points}
            chosen = {"chosenDurationSec": 0.0, "chosenSource": "zero_length_segment"}
        elif planned_duration is not None:
            # 路线规划阶段已经调用过高德驾车规划；ETA 直接消费该分段耗时，避免重复请求高德。
            eta = {
                "ok": True,
                "duration_sec": planned_duration,
                "distance_m": planned_distance if planned_distance is not None else polyline_distance(raw_points),
                "polyline": raw_points,
                "traffic_status": src.get("trafficStatus") or src.get("traffic_status") or "未知",
                "waypoint_count": 0,
                "source": src.get("source") or "preplanned_driving_segment",
            }
            chosen = {"chosenDurationSec": planned_duration, "chosenSource": eta["source"]}
        else:
            eta = await client.driving_eta(raw_points)
            chosen = choose_amap_eta(eta)
        chosen_source = chosen["chosenSource"]

        display_points = eta.get("polyline") or raw_points
        segment_distance = polyline_distance(display_points)
        cumulative_distance += segment_distance
        cumulative_eta = advance_eta_prefix(cumulative_eta, chosen["chosenDurationSec"])
        end_eta = round(cumulative_eta, 1) if cumulative_eta is not None else None

        segment = {
            "index": len(segments),
            "clientIndex": src.get("index", idx),
            "startNodeId": src.get("startNodeId"),
            "endNodeId": src.get("endNodeId"),
            "endStep": {
                "type": step_type,
                "orderId": order_id,
            },
            "aStarPolyline": raw_points,
            "aStarDistanceM": round(fallback_dist, 1),
            "fallbackDurationSec": round(fallback_eta, 1),
            "amapEta": {
                "ok": bool(eta.get("ok")),
                "durationSec": eta.get("duration_sec"),
                "distanceM": eta.get("distance_m"),
                "trafficStatus": eta.get("traffic_status") or "未知",
                "waypointCount": eta.get("waypoint_count"),
                "source": eta.get("source") or "grasped_segment",
                "error": eta.get("error") or eta.get("reason") or eta.get("info"),
            },
            "chosenDurationSec": round(chosen["chosenDurationSec"], 1) if chosen["chosenDurationSec"] is not None else None,
            "chosenSource": chosen_source,
            "matchedPolyline": display_points,
            "amapPolyline": eta.get("polyline") or [],
            "endEtaFromNowSec": end_eta,
            "endDistanceFromNowM": round(cumulative_distance, 1),
        }
        segments.append(segment)

        if vehicle_polyline and display_points:
            vehicle_polyline.extend(display_points[1:])
        else:
            vehicle_polyline.extend(display_points)
        segment_offsets.append({
            "segmentIndex": segment["index"],
            "offsetM": round(cumulative_distance, 1),
            "endStep": segment["endStep"],
        })

        if order_id is not None:
            order_eta = eta_by_order.setdefault(str(order_id), {
                "orderId": normalize_order_id_value(order_id),
                "pickupEtaSec": None,
                "dropoffEtaSec": None,
            })
            if step_type == "O":
                order_eta["pickupEtaSec"] = end_eta
            elif step_type == "D":
                order_eta["dropoffEtaSec"] = end_eta
        elif step_type == "IDLE":
            idle_eta_sec = end_eta
            idle_eta_distance_m = round(cumulative_distance, 1)

    return {
        "ok": True,
        "pipelineKind": "amap_eta_correct",
        "vehicleId": vehicle_id,
        "routeVersion": route_version,
        "builtAtEpoch": time.time(),
        "builtAtIso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "amapEnabled": client.enabled,
        "segmentCount": len(segments),
        "segments": segments,
        "vehiclePolyline": vehicle_polyline,
        "segmentEndOffsets": segment_offsets,
        "passengerEtas": list(eta_by_order.values()),
        "idleEtaSec": idle_eta_sec,
        "idleEtaDistanceM": idle_eta_distance_m,
        "totalChosenDurationSec": sum_known_durations(segments),
        "totalMatchedDistanceM": round(polyline_distance(vehicle_polyline), 1),
    }


async def build_fleet_eta_pipelines_from_astar_async(
    payload: dict[str, Any],
    *,
    amap: AmapEtaCorrectClient | None = None,
    api_key: str | None = None,
    timeout_sec: float = 6.0,
) -> dict[str, Any]:
    """异步构建多车 ETA pipeline，复用同一个高德客户端缓存。"""
    client = amap or AmapEtaCorrectClient(api_key=api_key, timeout_sec=timeout_sec)
    vehicles = payload.get("vehicles") or []
    shared = {k: v for k, v in payload.items() if k != "vehicles"}
    results = []
    for vehicle in vehicles:
        vehicle_payload = dict(shared)
        vehicle_payload.update(vehicle)
        results.append(await build_eta_pipeline_from_astar_async(vehicle_payload, amap=client))
    return {
        "ok": True,
        "pipelineKind": "amap_eta_correct_fleet",
        "builtAtEpoch": time.time(),
        "builtAtIso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "vehicleCount": len(results),
        "vehicles": results,
    }


def _run_sync(coro: Any) -> Any:
    """把异步入口包装成同步调用；已有事件循环时放到临时线程执行。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: dict[str, Any] = {}

    def runner() -> None:
        """在线程里运行协程，避免嵌套事件循环报错。"""
        try:
            box["result"] = asyncio.run(coro)
        except BaseException as exc:
            box["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("result")


def build_eta_pipeline_from_astar(
    payload: dict[str, Any],
    *,
    amap: AmapEtaCorrectClient | None = None,
    api_key: str | None = None,
    timeout_sec: float = 6.0,
) -> dict[str, Any]:
    """同步构建单车 ETA pipeline，便于普通脚本或 HTTP Handler 调用。"""
    return _run_sync(build_eta_pipeline_from_astar_async(payload, amap=amap, api_key=api_key, timeout_sec=timeout_sec))


def build_fleet_eta_pipelines_from_astar(
    payload: dict[str, Any],
    *,
    amap: AmapEtaCorrectClient | None = None,
    api_key: str | None = None,
    timeout_sec: float = 6.0,
) -> dict[str, Any]:
    """同步构建多车 ETA pipeline。"""
    return _run_sync(build_fleet_eta_pipelines_from_astar_async(payload, amap=amap, api_key=api_key, timeout_sec=timeout_sec))


amap_eta_correct_async = build_eta_pipeline_from_astar_async
amap_eta_correct = build_eta_pipeline_from_astar

# # 以下是我自己用来本地测试的  
# class AmapEtaCorrectHttpHandler(BaseHTTPRequestHandler):
#     """demo_v4 使用的极薄 HTTP 服务层。"""

#     server_version = "AmapEtaCorrect/0.1"

#     def do_OPTIONS(self) -> None:
#         """处理浏览器 CORS 预检请求。"""
#         self.send_response(204)
#         self._send_cors_headers()
#         self.end_headers()

#     def do_GET(self) -> None:
#         """提供 demo_v4 页面、地图数据和健康检查。"""
#         parsed = urlparse(self.path)
#         if parsed.path in {"/", "/demo_v4.html"}:
#             self._send_file(ROOT_DIR / "demo_v4.html", "text/html; charset=utf-8")
#             return
#         if parsed.path == "/map_data_v3.js":
#             self._send_file(ROOT_DIR / "map_data_v3.js", "application/javascript; charset=utf-8")
#             return
#         if parsed.path == "/health":
#             self._send_json({"ok": True, "service": "amap_eta_correct", "amapEnabled": HTTP_AMAP.enabled})
#             return
#         self._send_json({"ok": False, "error": "not_found"}, status=404)

#     def do_POST(self) -> None:
#         """接收前端 A* 段 payload，并调用 ETA pipeline。"""
#         parsed = urlparse(self.path)
#         body = self._read_json()
#         if parsed.path == "/eta_pipeline_from_astar_v4":
#             try:
#                 self._send_json(build_eta_pipeline_from_astar(body, amap=HTTP_AMAP))
#             except Exception as exc:
#                 self._send_json({"ok": False, "error": str(exc)}, status=500)
#             return
#         if parsed.path == "/fleet_eta_pipeline_from_astar_v4":
#             try:
#                 self._send_json(build_fleet_eta_pipelines_from_astar(body, amap=HTTP_AMAP))
#             except Exception as exc:
#                 self._send_json({"ok": False, "error": str(exc)}, status=500)
#             return
#         self._send_json({"ok": False, "error": "not_found"}, status=404)

#     def _read_json(self) -> dict[str, Any]:
#         """读取并解析 JSON 请求体。"""
#         length = int(self.headers.get("Content-Length") or "0")
#         if length <= 0:
#             return {}
#         raw = self.rfile.read(length).decode("utf-8")
#         try:
#             payload = json.loads(raw)
#         except json.JSONDecodeError:
#             return {}
#         return payload if isinstance(payload, dict) else {}

#     def _send_cors_headers(self) -> None:
#         """输出允许本地 demo 跨源访问的 CORS 响应头。"""
#         self.send_header("Access-Control-Allow-Origin", "*")
#         self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
#         self.send_header("Access-Control-Allow-Headers", "Content-Type")

#     def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
#         """发送 JSON 响应。"""
#         data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
#         self.send_response(status)
#         self._send_cors_headers()
#         self.send_header("Content-Type", "application/json; charset=utf-8")
#         self.send_header("Content-Length", str(len(data)))
#         self.send_header("Cache-Control", "no-store")
#         self.end_headers()
#         self.wfile.write(data)

#     def _send_file(self, path: Path, content_type: str) -> None:
#         """发送静态文件响应。"""
#         if not path.exists():
#             self._send_json({"ok": False, "error": "file_not_found"}, status=404)
#             return
#         data = path.read_bytes()
#         self.send_response(200)
#         self._send_cors_headers()
#         self.send_header("Content-Type", content_type)
#         self.send_header("Content-Length", str(len(data)))
#         self.end_headers()
#         self.wfile.write(data)

#     def log_message(self, fmt: str, *args: Any) -> None:
#         """统一 demo 服务访问日志前缀。"""
#         print(f"[amap_eta_correct] {self.address_string()} - {fmt % args}")


# HTTP_AMAP = AmapEtaCorrectClient()


# def serve_demo_v4(host: str = "127.0.0.1", port: int = 8767) -> None:
#     """启动 demo_v4 的本地 HTTP 服务。"""
#     server = ThreadingHTTPServer((host, port), AmapEtaCorrectHttpHandler)
#     print(f"amap_eta_correct ready: http://{host}:{port}/demo_v4.html")
#     print(f"endpoint: POST http://{host}:{port}/eta_pipeline_from_astar_v4")
#     print(f"amap enabled: {HTTP_AMAP.enabled}")
#     server.serve_forever()


# def main() -> None:
#     """命令行入口。"""
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--host", default="127.0.0.1")
#     parser.add_argument("--port", type=int, default=8767)
#     args = parser.parse_args()
#     serve_demo_v4(args.host, args.port)


# if __name__ == "__main__":
#     main()
