"""高德 Web 服务封装。

当前覆盖：
1. 驾车 ETA
2. 逆地理编码（坐标 -> adcode）
3. 实况天气（adcode -> weather）
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AMAP_BASE_URL = "https://restapi.amap.com/v5"
AMAP_WEATHER_BASE_URL = "https://restapi.amap.com/v3"
MAX_WAYPOINTS = 16


def _extract_lon_lat(point: Any) -> tuple[float, float]:
    """从 str/dict/object 中统一提取经纬度。"""
    if isinstance(point, str):
        lon_text, lat_text = point.split(",", 1)
        return float(lon_text), float(lat_text)

    if isinstance(point, dict):
        return float(point["lon"]), float(point["lat"])

    return float(point.lon), float(point.lat)


def format_coord(point: Any) -> str:
    """格式化为高德接口要求的 `lon,lat` 字符串。"""
    lon, lat = _extract_lon_lat(point)
    return f"{lon:.6f},{lat:.6f}"


def build_stop_chain_until(
    planned_route: list[dict],
    target_order_id: int | str,
    target_step_type: str,
) -> list[Any]:
    """从车辆剩余计划里截取直到目标订单节点为止的停靠点链。

    例子：
    - 当前车上还有别的单要先下客，那么这些前置停靠点会被放进 waypoints。
    - 对 waiting 订单，目标节点是该订单的 P 点。
    - 对 riding 订单，目标节点是该订单的 D 点。
    """
    stops: list[Any] = []
    prev_text = None

    for step in planned_route:
        order = step["order"]
        step_type = step["type"]
        target_node = order["pNode"] if step_type == "P" else order["dNode"]
        coord_text = format_coord(target_node)

        if coord_text != prev_text:
            stops.append(target_node)
            prev_text = coord_text

        if order["id"] == target_order_id and step_type == target_step_type:
            break

    return stops


def trim_stop_chain(stops: list[Any], max_waypoints: int = MAX_WAYPOINTS) -> tuple[list[Any], bool]:
    """将停靠点链裁剪到高德 waypoints 上限以内。

    返回：
    - 裁剪后的 stop chain（最后一个元素始终是 destination）
    - 是否发生过裁剪
    """
    max_stops = max_waypoints + 1
    if len(stops) <= max_stops:
        return stops, False

    destination = stops[-1]
    intermediates = stops[:-1]
    if max_waypoints <= 0:
        return [destination], True

    if len(intermediates) <= max_waypoints:
        return intermediates + [destination], False

    idxs: list[int] = []
    if max_waypoints == 1:
        idxs = [0]
    else:
        last = len(intermediates) - 1
        for i in range(max_waypoints):
            idx = round(i * last / (max_waypoints - 1))
            if not idxs or idx != idxs[-1]:
                idxs.append(idx)

    selected = [intermediates[i] for i in idxs]
    return selected + [destination], True


class AmapDrivingClient:
    """高德 Web 服务客户端。"""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_sec: float = 5.0,
        cache_ttl_sec: float = 60.0,
        weather_cache_ttl_sec: float = 600.0,
        geocode_cache_ttl_sec: float = 86400.0,
        strategy: int = 0,
        fetcher: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("AMAP_API_KEY") or "").strip()
        self.timeout_sec = timeout_sec
        self.cache_ttl_sec = cache_ttl_sec
        self.weather_cache_ttl_sec = weather_cache_ttl_sec
        self.geocode_cache_ttl_sec = geocode_cache_ttl_sec
        self.strategy = strategy
        self.fetcher = fetcher or self._default_fetcher
        self._cache: dict[str, dict[str, Any]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def estimate_remaining_chain(
        self,
        origin: Any,
        stops: list[Any],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:
        """根据当前点 + 剩余停靠点链，返回高德 ETA。

        注意：
        - 这里的 stops 不是密集轨迹点，而是剩余停靠点序列。
        - 中间停靠点会被编码成高德的 `waypoints`。
        """
        if not stops:
            return {
                "ok": False,
                "provider": "amap",
                "reason": "empty_stop_chain",
                "enabled": self.enabled,
            }

        trimmed_stops, truncated = trim_stop_chain(stops, MAX_WAYPOINTS)
        destination = trimmed_stops[-1]
        waypoints = trimmed_stops[:-1]
        result = self.estimate_leg(origin, destination, waypoints=waypoints, now=now)
        result["stop_count"] = len(trimmed_stops)
        result["truncated_waypoints"] = truncated
        return result

    def estimate_leg(
        self,
        origin: Any,
        destination: Any,
        *,
        waypoints: list[Any] | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        """查询 origin -> destination 的驾车 ETA。"""
        if not self.enabled:
            return {
                "ok": False,
                "provider": "amap",
                "reason": "missing_api_key",
                "enabled": False,
            }

        waypoints = waypoints or []
        origin_text = format_coord(origin)
        dest_text = format_coord(destination)
        waypoint_texts = [format_coord(p) for p in waypoints[:MAX_WAYPOINTS]]
        now_epoch = float(time.time() if now is None else now)

        cache_key = "|".join(
            [
                origin_text,
                dest_text,
                ";".join(waypoint_texts),
                str(self.strategy),
            ]
        )
        cached = self._cache.get(cache_key)
        if cached and (now_epoch - cached["fetched_at_epoch"] <= self.cache_ttl_sec):
            result = dict(cached)
            result["cached"] = True
            return result

        params = {
            "key": self.api_key,
            "origin": origin_text,
            "destination": dest_text,
            "strategy": str(self.strategy),
            "show_fields": "cost,polyline",
            "output": "json",
        }
        if waypoint_texts:
            params["waypoints"] = ";".join(waypoint_texts)

        try:
            payload = self._request_json(
                path="/direction/driving",
                params=params,
                cache_namespace="driving_eta",
                ttl_sec=self.cache_ttl_sec,
                now_epoch=now_epoch,
            )
            status = str(payload.get("status", "0"))
            if status != "1":
                info = payload.get("info") or "unknown_error"
                raise RuntimeError(f"amap status={status} info={info}")

            route = payload.get("route") or {}
            paths = route.get("paths") or []
            if not paths:
                raise RuntimeError("amap route.paths is empty")

            best_path = paths[0]
            # v5: 时长嵌入到 cost.duration; v3: 仍是顶层 duration。这里两种都兼容。
            cost = best_path.get("cost") or {}
            duration_raw = cost.get("duration") if cost.get("duration") is not None else best_path.get("duration", 0)
            duration_sec = int(float(duration_raw or 0))
            distance_m = int(float(best_path.get("distance", 0) or 0))

            # v5: 路径形状(polyline)在每个 step 内, 以 "lon,lat;lon,lat;..." 串联,
            # 这里展开成 [(lon, lat), ...] 列表方便上层渲染。
            polyline_points: list[tuple[float, float]] = []
            for step in (best_path.get("steps") or []):
                raw_polyline = step.get("polyline") or ""
                if not raw_polyline:
                    continue
                for pt in raw_polyline.split(";"):
                    if "," not in pt:
                        continue
                    try:
                        lon_str, lat_str = pt.split(",", 1)
                        polyline_points.append((float(lon_str), float(lat_str)))
                    except (ValueError, TypeError):
                        continue

            result = {
                "ok": True,
                "provider": "amap",
                "enabled": True,
                "cached": False,
                "origin": origin_text,
                "destination": dest_text,
                "waypoint_count": len(waypoint_texts),
                "distance_m": distance_m,
                "duration_sec": duration_sec,
                "polyline": polyline_points,
                "fetched_at_epoch": now_epoch,
                "fetched_at_iso": datetime.fromtimestamp(now_epoch, tz=timezone.utc).isoformat(),
            }
            self._cache[cache_key] = dict(result)
            return result
        except Exception as exc:
            return {
                "ok": False,
                "provider": "amap",
                "enabled": True,
                "origin": origin_text,
                "destination": dest_text,
                "waypoint_count": len(waypoint_texts),
                "error": str(exc),
            }

    def reverse_geocode(self, point: Any, *, now: float | None = None) -> dict[str, Any]:
        """坐标转行政区信息，主要用于拿 adcode。"""
        if not self.enabled:
            return {
                "ok": False,
                "provider": "amap",
                "reason": "missing_api_key",
                "enabled": False,
            }

        location = format_coord(point)
        now_epoch = float(time.time() if now is None else now)
        params = {
            "key": self.api_key,
            "location": location,
            "extensions": "base",
            "output": "json",
        }
        try:
            payload = self._request_json(
                path="/geocode/regeo",
                params=params,
                cache_namespace="regeo",
                ttl_sec=self.geocode_cache_ttl_sec,
                now_epoch=now_epoch,
            )
            status = str(payload.get("status", "0"))
            if status != "1":
                info = payload.get("info") or "unknown_error"
                raise RuntimeError(f"amap status={status} info={info}")

            regeocode = payload.get("regeocode") or {}
            address = regeocode.get("addressComponent") or {}
            adcode = str(address.get("adcode") or "").strip()
            if not adcode:
                raise RuntimeError("amap regeo missing adcode")

            return {
                "ok": True,
                "provider": "amap",
                "enabled": True,
                "location": location,
                "adcode": adcode,
                "city": str(address.get("city") or ""),
                "province": str(address.get("province") or ""),
                "district": str(address.get("district") or ""),
            }
        except Exception as exc:
            return {
                "ok": False,
                "provider": "amap",
                "enabled": True,
                "location": location,
                "error": str(exc),
            }

    def get_live_weather(self, point: Any, *, now: float | None = None) -> dict[str, Any]:
        """通过坐标查高德实况天气。"""
        if not self.enabled:
            return {
                "ok": False,
                "provider": "amap",
                "reason": "missing_api_key",
                "enabled": False,
            }

        now_epoch = float(time.time() if now is None else now)
        regeo = self.reverse_geocode(point, now=now_epoch)
        if not regeo.get("ok"):
            return {
                "ok": False,
                "provider": "amap",
                "enabled": True,
                "error": f"regeo_failed:{regeo.get('error') or regeo.get('reason', 'unknown')}",
            }

        adcode = str(regeo["adcode"])
        params = {
            "key": self.api_key,
            "city": adcode,
            "extensions": "base",
            "output": "json",
        }
        try:
            payload = self._request_json(
                path="/weather/weatherInfo",
                params=params,
                cache_namespace="weather_base",
                ttl_sec=self.weather_cache_ttl_sec,
                now_epoch=now_epoch,
            )
            status = str(payload.get("status", "0"))
            if status != "1":
                info = payload.get("info") or "unknown_error"
                raise RuntimeError(f"amap status={status} info={info}")

            lives = payload.get("lives") or []
            if not lives:
                raise RuntimeError("amap weather missing lives")
            live = lives[0]

            return {
                "ok": True,
                "provider": "amap",
                "enabled": True,
                "adcode": str(live.get("adcode") or adcode),
                "city": str(live.get("city") or regeo.get("city", "")),
                "province": str(live.get("province") or regeo.get("province", "")),
                "weather": str(live.get("weather") or ""),
                "temperature": str(live.get("temperature") or ""),
                "winddirection": str(live.get("winddirection") or ""),
                "windpower": str(live.get("windpower") or ""),
                "humidity": str(live.get("humidity") or ""),
                "reporttime": str(live.get("reporttime") or ""),
            }
        except Exception as exc:
            return {
                "ok": False,
                "provider": "amap",
                "enabled": True,
                "adcode": adcode,
                "city": str(regeo.get("city") or ""),
                "province": str(regeo.get("province") or ""),
                "error": str(exc),
            }

    def _request_json(
        self,
        *,
        path: str,
        params: dict[str, Any],
        cache_namespace: str,
        ttl_sec: float,
        now_epoch: float,
    ) -> dict[str, Any]:
        cache_key = f"{cache_namespace}|{path}|{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
        cached = self._cache.get(cache_key)
        if cached and now_epoch - cached["fetched_at_epoch"] <= ttl_sec:
            payload = dict(cached["payload"])
            payload["_cached"] = True
            return payload

        payload = self.fetcher(
            path=path,
            params=params,
            timeout_sec=self.timeout_sec,
        )
        self._cache[cache_key] = {
            "fetched_at_epoch": now_epoch,
            "payload": dict(payload),
        }
        return payload

    @staticmethod
    def _default_fetcher(path: str, params: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
        """默认 HTTP 拉取器，使用标准库实现，避免额外依赖。"""
        # 驾车路线规划走 v5；其余接口（regeo / weather）仍保留在 v3。
        base_url = AMAP_BASE_URL if path.startswith("/direction/") else AMAP_WEATHER_BASE_URL
        url = f"{base_url}{path}?{urlencode(params)}"
        req = Request(url, headers={"User-Agent": "insert-riding/1.0"})
        try:
            with urlopen(req, timeout=timeout_sec) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"http_{exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"network_error:{exc.reason}") from exc
