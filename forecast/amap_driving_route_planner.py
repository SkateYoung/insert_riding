"""高德驾车规划路线生成模块。

该模块只负责把车辆剩余 O/D/IDLE 分段转成高德驾车规划路线，不参与派单、
不计算订单 ETA。调用方仍负责路线版本校验和写回车辆对象。
"""

from __future__ import annotations

import copy
import json
import os
import socket
import ssl
import threading
import time
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from .amap_eta_correct import (
    AMAP_TRAFFIC_RANK,
    DEFAULT_AMAP_HTTP_RETRIES,
    DEFAULT_AMAP_HTTP_RETRY_DELAY_SECONDS,
    DEFAULT_AMAP_KEY,
    coord_text,
    env_flag,
    env_float,
    env_int,
    normalize_points,
    parse_step_polyline,
    polyline_distance,
)

try:
    import certifi
except ImportError:  # pragma: no cover - depends on deployment environment.
    certifi = None


DEFAULT_DRIVING_STRATEGY = "37"
DEFAULT_DRIVING_REQUEST_INTERVAL_MS = 900
DEFAULT_DRIVING_QPS_RETRY_DELAYS_MS = (1500, 3000, 6000)


def _env_retry_delays_ms(name: str, default: tuple[int, ...]) -> list[float]:
    """读取逗号分隔的毫秒退避配置，配置错误时使用默认值。"""
    raw = os.getenv(name)
    if not raw:
        return [float(item) for item in default]
    delays = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            delays.append(max(0.0, float(item)))
        except ValueError:
            return [float(value) for value in default]
    return delays or [float(value) for value in default]


def _combine_segment_points(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把分段路线拼接成整车路线，并去掉相邻重复点。"""
    combined: list[dict[str, Any]] = []
    for segment in segments or []:
        points = segment.get("points") or segment.get("path") or []
        for point in points:
            normalized = normalize_points([point])
            if not normalized:
                continue
            item = normalized[0]
            if combined and coord_text(combined[-1]) == coord_text(item):
                continue
            combined.append(copy.deepcopy(item))
    return combined


class AmapDrivingRoutePlanner:
    """封装高德 v5 驾车规划接口，用于生成车辆展示路线。"""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_sec: float = 6.0,
        strategy: str | None = None,
        request_interval_ms: float | None = None,
        qps_retry_delays_ms: list[float] | None = None,
    ) -> None:
        """初始化高德驾车规划客户端。"""
        if env_flag("AMAP_DISABLE"):
            self.api_key = ""
        else:
            self.api_key = (api_key or os.getenv("AMAP_API_KEY") or DEFAULT_AMAP_KEY).strip()
        self.timeout_sec = timeout_sec
        self.strategy = str(strategy or os.getenv("AMAP_DRIVING_STRATEGY") or DEFAULT_DRIVING_STRATEGY)
        self.request_interval_sec = (
            float(request_interval_ms)
            if request_interval_ms is not None
            else env_float("AMAP_DRIVING_REQUEST_INTERVAL_MS", DEFAULT_DRIVING_REQUEST_INTERVAL_MS)
        ) / 1000.0
        self.qps_retry_delays_sec = [
            float(value) / 1000.0
            for value in (
                qps_retry_delays_ms
                if qps_retry_delays_ms is not None
                else _env_retry_delays_ms(
                    "AMAP_DRIVING_QPS_RETRY_DELAYS_MS",
                    DEFAULT_DRIVING_QPS_RETRY_DELAYS_MS,
                )
            )
        ]
        self.retry_count = max(1, env_int("AMAP_HTTP_RETRIES", DEFAULT_AMAP_HTTP_RETRIES))
        self.retry_delay_sec = max(0.0, env_float("AMAP_HTTP_RETRY_DELAY_SECONDS", DEFAULT_AMAP_HTTP_RETRY_DELAY_SECONDS))
        self.bypass_proxy = env_flag("AMAP_BYPASS_PROXY", "1")
        self.ssl_verify = not env_flag("AMAP_SSL_NO_VERIFY")
        self._ssl_context = self._build_ssl_context()
        self._opener = self._build_opener()
        self._route_cache: dict[str, dict[str, Any]] = {}
        self._request_lock = threading.Lock()
        self._last_request_monotonic = 0.0

    @property
    def enabled(self) -> bool:
        """返回当前是否具备可用的高德 Key。"""
        return bool(self.api_key)

    def plan_segment_sync(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        """同步规划一个分段，只使用分段起终点，不传 A* 中间点。"""
        if not self.enabled:
            return {"ok": False, "reason": "missing_api_key"}
        normalized = normalize_points(points)
        if len(normalized) < 2:
            return {"ok": False, "reason": "too_few_points"}

        origin = normalized[0]
        destination = normalized[-1]
        if coord_text(origin) == coord_text(destination):
            return {
                "ok": True,
                "duration_sec": 0.0,
                "distance_m": 0.0,
                "polyline": [copy.deepcopy(origin)],
                "traffic_status": "未知",
                "waypoint_count": 0,
                "source": "same_endpoint",
            }

        params = {
            "key": self.api_key,
            "origin": coord_text(origin),
            "destination": coord_text(destination),
            "strategy": self.strategy,
            "ferry": "1",
            "show_fields": "cost,polyline,tmcs",
            "output": "json",
        }
        cache_key = json.dumps(params, sort_keys=True, separators=(",", ":"))
        cached = self._route_cache.get(cache_key)
        if cached:
            result = copy.deepcopy(cached)
            result["cached"] = True
            return result

        result = self._request_driving_with_qps_retry(params)
        result["waypoint_count"] = 0
        result["strategy"] = self.strategy
        result["cached"] = False
        if result.get("ok"):
            self._route_cache[cache_key] = copy.deepcopy(result)
        return result

    def plan_segments_sync(self, segments: list[dict[str, Any]]) -> dict[str, Any]:
        """规划多个 O/D/IDLE 分段，并返回统一的整车路线结构。"""
        if not self.enabled:
            return {
                "ok": False,
                "status": "disabled",
                "segments": [],
                "path": [],
                "reason": "missing_api_key",
            }

        planned_segments: list[dict[str, Any]] = []
        errors: list[str] = []
        for segment in segments or []:
            result = self.plan_segment_sync(segment.get("points") or [])
            if not isinstance(result, dict) or not result.get("ok"):
                reason = "driving_plan_failed"
                if isinstance(result, dict):
                    reason = result.get("error") or result.get("reason") or result.get("info") or reason
                errors.append(f"{segment.get('type')}:{segment.get('request_id')}:{reason}")
                continue

            polyline = result.get("polyline") or []
            if not polyline:
                errors.append(f"{segment.get('type')}:{segment.get('request_id')}:empty_polyline")
                continue

            planned = copy.deepcopy(segment)
            planned["points"] = copy.deepcopy(polyline)
            planned["source"] = result.get("source") or "driving_plan"
            planned["duration_sec"] = result.get("duration_sec")
            planned["distance_m"] = result.get("distance_m") or polyline_distance(polyline)
            planned["traffic_status"] = result.get("traffic_status")
            planned["grasp"] = {
                "ok": True,
                "provider": "amap_driving",
                "strategy": result.get("strategy", self.strategy),
                "distance_m": planned["distance_m"],
                "duration_sec": planned["duration_sec"],
                "traffic_status": planned["traffic_status"],
                "request_points": 2,
                "waypoint_count": result.get("waypoint_count", 0),
                "cached": result.get("cached"),
                "error": None,
            }
            planned_segments.append(planned)

        if errors:
            return {
                "ok": False,
                "status": "error",
                "segments": [],
                "path": [],
                "reason": "; ".join(errors),
            }
        return {
            "ok": True,
            "status": "ready",
            "segments": planned_segments,
            "path": _combine_segment_points(planned_segments),
            "reason": None,
        }

    def _request_driving_with_qps_retry(self, params: dict[str, str]) -> dict[str, Any]:
        """请求高德驾车规划；命中 QPS 限流时按配置退避重试。"""
        attempts = len(self.qps_retry_delays_sec) + 1
        last_result = None
        for attempt_index in range(attempts):
            try:
                self._throttle_request()
                url = f"https://restapi.amap.com/v5/direction/driving?{urlencode(params)}"
                req = Request(url, headers={"User-Agent": "insert-riding-driving-route/1.0"})
                payload = self._urlopen_json(req)
                result = self._parse_driving_response(payload)
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}

            last_result = result
            if result.get("ok"):
                return result
            if not self._is_qps_limit(result) or attempt_index >= attempts - 1:
                return result
            time.sleep(self.qps_retry_delays_sec[attempt_index])
        return last_result or {"ok": False, "reason": "driving_request_failed"}

    def _throttle_request(self) -> None:
        """限制同一进程内高德驾车规划请求间隔，降低触发 CUQPS 的概率。"""
        if self.request_interval_sec <= 0:
            return
        with self._request_lock:
            now = time.monotonic()
            wait_sec = self._last_request_monotonic + self.request_interval_sec - now
            if wait_sec > 0:
                time.sleep(wait_sec)
            self._last_request_monotonic = time.monotonic()

    def _build_ssl_context(self) -> ssl.SSLContext:
        """构建高德 HTTPS 请求使用的 SSL 上下文。"""
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

    def _urlopen_json(self, req: Request) -> dict[str, Any]:
        """执行同步 HTTP JSON 请求。"""
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

    def _parse_driving_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        """解析高德 v5 驾车规划响应。"""
        if str(payload.get("status", "0")) != "1":
            return {
                "ok": False,
                "info": payload.get("info"),
                "infocode": payload.get("infocode"),
                "raw": payload,
            }
        route = payload.get("route") or {}
        paths = route.get("paths") or []
        if not paths:
            return {"ok": False, "reason": "empty_paths", "raw": payload}

        best = paths[0]
        cost = best.get("cost") or {}
        try:
            duration = float(cost.get("duration") or best.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        try:
            distance = float(best.get("distance") or 0)
        except (TypeError, ValueError):
            distance = 0.0

        steps = best.get("steps") or []
        polyline = parse_step_polyline(steps)
        if len(polyline) < 2:
            return {
                "ok": False,
                "reason": "empty_polyline",
                "duration_sec": duration,
                "distance_m": distance,
                "raw": payload,
            }

        traffic_status = "未知"
        for step in steps:
            for tmc in step.get("tmcs") or []:
                status = str(tmc.get("tmc_status") or "未知")
                if AMAP_TRAFFIC_RANK.get(status, 0) > AMAP_TRAFFIC_RANK.get(traffic_status, 0):
                    traffic_status = status

        return {
            "ok": True,
            "duration_sec": duration,
            "distance_m": distance or polyline_distance(polyline),
            "polyline": polyline,
            "traffic_status": traffic_status,
            "raw": payload,
        }

    @staticmethod
    def _is_qps_limit(result: dict[str, Any]) -> bool:
        """识别高德 QPS 限流错误。"""
        values = []
        for key in ("info", "infocode", "reason", "error"):
            value = result.get(key)
            if value is not None:
                values.append(str(value))
        raw = result.get("raw")
        if isinstance(raw, dict):
            for key in ("info", "infocode", "errmsg", "errdetail"):
                value = raw.get(key)
                if value is not None:
                    values.append(str(value))
        signal = " ".join(values).upper()
        return (
            "CUQPS_HAS_EXCEEDED_THE_LIMIT" in signal
            or "QPS_HAS_EXCEEDED" in signal
            or ("QPS" in signal and "LIMIT" in signal)
        )
