"""按自有规划轨迹分段调用高德 ETA。

这个模块不依赖 demo.html。调用方需要先完成自己的调度和 A* 路径规划，
再把车辆当前位置、目标订单、车辆剩余停靠点序列和每段 A* 轨迹传进来。

核心输出：
- pickup_eta：接驾 ETA，车辆当前位置到目标订单上车点。
- dropoff_eta：送达 ETA。
  - 订单未上车时：预计上车后行程 ETA，即该订单 P 点 -> 该订单 D 点。
  - 订单已上车时：实时送达 ETA，即当前车辆 GPS -> 该订单 D 点。

ETA 计算方式：
- pickup_eta 只对 waiting 订单有效。
- dropoff_eta 对 waiting/riding 订单都可返回，但 origin_kind 不同。
- 有效 ETA 都沿 planned_route 中的连续 A* 子路径分段。
- 分段端点会强制包含该 ETA 子路径里经过的订单 P/D 停靠点。
- 当前活动段使用车辆实时位置调用高德，得到 dynamic_sec。
- 后续未到达分段使用固定起终点调用高德，得到 static_sec。
- eta_seconds = dynamic_sec + static_sec。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping

try:
    from .amap_eta import AmapDrivingClient, format_coord
except ImportError:
    from forecast.amap_eta import AmapDrivingClient, format_coord


Point = Dict[str, Any]
Fetcher = Callable[..., Dict[str, Any]]


async def _run_blocking_io(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """兼容 Python 3.8：在线程池里运行阻塞 I/O。"""
    to_thread = getattr(asyncio, "to_thread", None)
    if to_thread is not None:
        return await to_thread(func, *args, **kwargs)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


@dataclass(frozen=True)
class SegmentEtaConfig:
    """分段 ETA 的可调参数。

    pickup_segments:
        接驾腿切成几段。车辆到乘客上车点通常较短，默认 5 段。
    dropoff_segments:
        送达腿切成几段。送达腿可能包含其他订单停靠点，默认 10 段。
    live_refresh_sec:
        当前活动段重新调用高德的最短间隔。甲方 5 秒推一次车位时可设为 5。
    static_retry_sec:
        静态段失败后的重试间隔。
    advance_distance_m:
        车辆距离分段终点多少米以内，认为已经进入下一段。
    max_segment_distance_m:
        单个高德请求对应的 A* 子段最长距离。路线很长或订单很多时，
        函数会在 5/10 目标段数之外自动加密分段。设为 0 表示不按距离加密。
    shape_waypoints_per_segment:
        每个高德分段请求额外携带多少个 A* 中间形状点作为 waypoints。
        高德单次驾车请求 waypoints 有上限，建议 2~8；设为 0 表示只传起终点。
    distance_ratio_warn_min / distance_ratio_warn_max:
        高德返回距离与 A* 子段距离的合理比例范围。超过范围时返回
        route_match_status=suspect，提示高德路线可能没有贴合 A*。
    amap_cache_ttl_sec:
        高德客户端缓存 TTL。静态段起终点不变时会复用缓存。
    amap_qps:
        高德请求限流。普通 Key 建议不超过 3 次/秒；设为 0 表示不节流。
    strategy:
        高德驾车策略参数，默认 0。
    include_polyline:
        是否在返回值中带上高德 polyline。只要 ETA 时建议保持 False。
    """

    pickup_segments: int = 5
    dropoff_segments: int = 10
    live_refresh_sec: float = 5.0
    static_retry_sec: float = 20.0
    advance_distance_m: float = 40.0
    max_segment_distance_m: float = 700.0
    shape_waypoints_per_segment: int = 4
    distance_ratio_warn_min: float = 0.4
    distance_ratio_warn_max: float = 3.0
    amap_cache_ttl_sec: float = 60.0
    amap_qps: float = 2.5
    strategy: int = 0
    include_polyline: bool = False


def _merge_config(base: SegmentEtaConfig, raw: Mapping[str, Any] | None) -> SegmentEtaConfig:
    if not raw:
        return base

    pickup_segments = raw.get("pickup_segments", raw.get("pickupSegments", base.pickup_segments))
    dropoff_segments = raw.get(
        "dropoff_segments",
        raw.get("dropoffSegments", raw.get("delivery_segments", raw.get("deliverySegments", base.dropoff_segments))),
    )
    live_refresh_sec = raw.get("live_refresh_sec", raw.get("liveRefreshSec", base.live_refresh_sec))

    return SegmentEtaConfig(
        pickup_segments=max(1, int(pickup_segments)),
        dropoff_segments=max(1, int(dropoff_segments)),
        live_refresh_sec=max(0.0, float(live_refresh_sec)),
        static_retry_sec=float(raw.get("static_retry_sec", raw.get("staticRetrySec", base.static_retry_sec))),
        advance_distance_m=float(raw.get("advance_distance_m", raw.get("advanceDistanceM", base.advance_distance_m))),
        max_segment_distance_m=float(
            raw.get("max_segment_distance_m", raw.get("maxSegmentDistanceM", base.max_segment_distance_m))
        ),
        shape_waypoints_per_segment=max(
            0,
            int(
                raw.get(
                    "shape_waypoints_per_segment",
                    raw.get("shapeWaypointsPerSegment", base.shape_waypoints_per_segment),
                )
            ),
        ),
        distance_ratio_warn_min=float(
            raw.get("distance_ratio_warn_min", raw.get("distanceRatioWarnMin", base.distance_ratio_warn_min))
        ),
        distance_ratio_warn_max=float(
            raw.get("distance_ratio_warn_max", raw.get("distanceRatioWarnMax", base.distance_ratio_warn_max))
        ),
        amap_cache_ttl_sec=float(raw.get("amap_cache_ttl_sec", raw.get("amapCacheTtlSec", base.amap_cache_ttl_sec))),
        amap_qps=float(raw.get("amap_qps", raw.get("amapQps", base.amap_qps))),
        strategy=int(raw.get("strategy", base.strategy)),
        include_polyline=bool(raw.get("include_polyline", raw.get("includePolyline", base.include_polyline))),
    )


def _point(raw: Any) -> Point:
    """把 dict/object 统一成 {'lon': float, 'lat': float, ...}。"""
    if raw is None:
        raise ValueError("point is required")

    if isinstance(raw, str):
        lon_text, lat_text = raw.split(",", 1)
        return {"lon": float(lon_text), "lat": float(lat_text)}

    if isinstance(raw, Mapping):
        src = raw.get("position") if isinstance(raw.get("position"), Mapping) else raw
        lon = src.get("lon", src.get("lng"))
        lat = src.get("lat")
        if lon is None or lat is None:
            raise ValueError(f"point missing lon/lat: {raw!r}")

        out: Point = {"lon": float(lon), "lat": float(lat)}
        for key in ("id", "node_id", "name", "timestamp", "time"):
            if key in src:
                out[key] = src[key]
        if "node_id" in out and "id" not in out:
            out["id"] = out["node_id"]
        return out

    lon = getattr(raw, "lon", getattr(raw, "lng", None))
    lat = getattr(raw, "lat", None)
    if lon is None or lat is None:
        raise ValueError(f"point missing lon/lat: {raw!r}")
    return {"lon": float(lon), "lat": float(lat)}


def _point_key(point: Any) -> str:
    p = _point(point)
    return f"{p['lon']:.6f},{p['lat']:.6f}"


def _same_point(a: Any, b: Any) -> bool:
    return _point_key(a) == _point_key(b)


def _haversine_m(a: Any, b: Any) -> float:
    p1 = _point(a)
    p2 = _point(b)
    radius = 6371000.0
    rad = math.pi / 180.0
    lat1 = p1["lat"] * rad
    lat2 = p2["lat"] * rad
    dlat = (p2["lat"] - p1["lat"]) * rad
    dlon = (p2["lon"] - p1["lon"]) * rad
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def _normalize_step_type(raw: Any) -> str:
    text = str(raw or "").strip().upper()
    if text in {"P", "PICKUP", "ORIGIN", "O"}:
        return "P"
    if text in {"D", "DROPOFF", "DELIVERY", "DESTINATION"}:
        return "D"
    raise ValueError(f"unknown planned route step type: {raw!r}")


def _order_id(order: Mapping[str, Any]) -> str:
    oid = order.get("id", order.get("order_id", order.get("orderId")))
    if oid is None:
        raise ValueError("order missing id/order_id")
    return str(oid)


def _step_order_id(step: Mapping[str, Any]) -> str:
    oid = step.get("order_id", step.get("orderId"))
    if oid is not None:
        return str(oid)
    order = step.get("order")
    if isinstance(order, Mapping):
        return _order_id(order)
    raise ValueError(f"planned route step missing order_id: {step!r}")


def _order_point(order: Mapping[str, Any], kind: str) -> Point:
    if kind == "pickup":
        for key in ("pickup", "pNode", "origin", "p"):
            if key in order:
                return _point(order[key])
    else:
        for key in ("dropoff", "dNode", "destination", "d"):
            if key in order:
                return _point(order[key])
    raise ValueError(f"order {_order_id(order)} missing {kind} point")


def _step_point(step: Mapping[str, Any]) -> Point:
    if "point" in step:
        return _point(step["point"])
    if "node" in step:
        return _point(step["node"])

    order = step.get("order")
    if isinstance(order, Mapping):
        step_type = _normalize_step_type(step.get("type"))
        return _order_point(order, "pickup" if step_type == "P" else "dropoff")

    raise ValueError(f"planned route step missing point/node/order: {step!r}")


def _vehicle_id(vehicle: Mapping[str, Any]) -> str:
    vid = vehicle.get("id", vehicle.get("vehicle_id", vehicle.get("vehicleId")))
    if vid is None:
        raise ValueError("vehicle missing id/vehicle_id")
    return str(vid)


def _vehicle_position(vehicle: Mapping[str, Any], fallback: Mapping[str, Point]) -> Point:
    vid = _vehicle_id(vehicle)
    if "position" in vehicle:
        return _point(vehicle["position"])
    if "lon" in vehicle or "lng" in vehicle:
        return _point(vehicle)
    if vid in fallback:
        return dict(fallback[vid])
    raise ValueError(f"vehicle {vid} missing position")


def _find_step_idx(planned_route: list[Mapping[str, Any]], order_id: str, step_type: str) -> int:
    for idx, step in enumerate(planned_route):
        if _step_order_id(step) == order_id and _normalize_step_type(step.get("type")) == step_type:
            return idx
    return -1


def _step_path(prev_point: Point, step: Mapping[str, Any]) -> list[Point]:
    raw = (
        step.get("path")
        or step.get("trajectory")
        or step.get("a_star_path")
        or step.get("astar_path")
        or step.get("polyline")
    )
    target = _step_point(step)

    if not raw:
        return [prev_point, target]

    points = [_point(p) for p in raw]
    if not points:
        return [prev_point, target]
    if not _same_point(points[0], prev_point):
        points.insert(0, prev_point)
    if not _same_point(points[-1], target):
        points.append(target)
    return points


def _append_path(base: list[Point], sub: list[Point]) -> None:
    for p in sub:
        if not base or not _same_point(base[-1], p):
            base.append(p)


def _concat_route_path(
    planned_route: list[Mapping[str, Any]],
    start_idx: int,
    end_idx: int,
    start_point: Point,
) -> list[Point]:
    if start_idx > end_idx or start_idx < 0 or end_idx >= len(planned_route):
        return []

    out: list[Point] = []
    current = start_point
    for idx in range(start_idx, end_idx + 1):
        sub = _step_path(current, planned_route[idx])
        _append_path(out, sub)
        current = _step_point(planned_route[idx])
    return out


def _concat_route_leg(
    planned_route: list[Mapping[str, Any]],
    start_idx: int,
    end_idx: int,
    start_point: Point,
    *,
    start_label: str,
) -> tuple[list[Point], list[dict[str, Any]]]:
    """串联 planned_route 的连续 A* 子路径，并记录必须经过的停靠点。

    这个函数是 Python 版对齐 demo.html `buildPathThroughSteps(...)` 的核心：
    单订单时就是 current->P 或 P->D；多订单时会把中间订单的 P/D 步骤
    按 planned_route 顺序拼进同一条路径。
    """
    path = _concat_route_path(planned_route, start_idx, end_idx, start_point)
    if not path:
        return [], []

    required_stops: list[dict[str, Any]] = [
        {
            "type": start_label,
            "order_id": None,
            "point": start_point,
        }
    ]
    for idx in range(start_idx, end_idx + 1):
        step = planned_route[idx]
        required_stops.append(
            {
                "type": _normalize_step_type(step.get("type")),
                "order_id": _step_order_id(step),
                "point": _step_point(step),
            }
        )

    return path, required_stops


def _cum_distances(path: list[Point]) -> list[float]:
    cums = [0.0]
    for idx in range(1, len(path)):
        cums.append(cums[-1] + _haversine_m(path[idx - 1], path[idx]))
    return cums


def _required_waypoint_indexes(path: list[Point], required_points: list[Point]) -> list[int]:
    """把必须经过的停靠点映射到 A* path 上的节点下标。

    required_points 通常是当前 ETA 子路径的起点和 planned_route 中经过的
    P/D 停靠点。按顺序向后查找，避免一条路径绕回同一节点时匹配到更早
    的重复节点。
    """
    if not path:
        return []

    indexes: list[int] = []
    cursor = 0
    for required in required_points:
        found = -1
        for idx in range(cursor, len(path)):
            if _same_point(path[idx], required):
                found = idx
                break

        # 正常情况下 _step_path 会把 step.point 追加到 path 中。这里保留
        # 最近点兜底，避免上游传入的 path 少了目标点时整个 ETA 失效。
        if found < 0:
            found = min(range(cursor, len(path)), key=lambda i: _haversine_m(path[i], required))

        if not indexes or indexes[-1] != found:
            indexes.append(found)
        cursor = found

    return indexes


def _sample_waypoints(
    path: list[Point],
    segment_count: int,
    max_segment_distance_m: float,
    required_points: list[Point] | None = None,
) -> tuple[list[Point], list[float], list[Point], list[int]]:
    """沿自有 A* 轨迹取分段端点，并强制包含业务停靠点。

    segment_count 是目标段数。若一条多订单路径里的强制 P/D 停靠点数量
    已经超过目标段数，或路径太长需要按 max_segment_distance_m 加密，
    函数会优先保留这些约束，实际段数可能增加。
    """
    if len(path) < 2:
        return path, [0.0] * len(path), path, list(range(len(path)))

    cums = _cum_distances(path)
    total = cums[-1]
    if total <= 0:
        return [path[0], path[-1]], [0.0, 0.0], [path[0], path[-1]], [0, len(path) - 1]

    selected: set[int] = {0, len(path) - 1}
    required_indexes = _required_waypoint_indexes(path, required_points or [])
    selected.update(required_indexes)

    # 在强制停靠点之外，再按累计里程补足等距分段端点。
    adaptive_segments = max(1, segment_count)
    if max_segment_distance_m > 0:
        adaptive_segments = max(adaptive_segments, int(math.ceil(total / max_segment_distance_m)))

    target_endpoint_count = max(2, adaptive_segments + 1)
    for cut in range(1, adaptive_segments):
        if len(selected) >= target_endpoint_count:
            break
        target = total * cut / adaptive_segments
        best_idx = min(range(len(cums)), key=lambda i: abs(cums[i] - target))
        selected.add(best_idx)

    indexes = sorted(selected)
    points: list[Point] = []
    point_cums: list[float] = []
    point_indexes: list[int] = []
    for idx in indexes:
        if points and _same_point(points[-1], path[idx]):
            continue
        points.append(path[idx])
        point_cums.append(cums[idx])
        point_indexes.append(idx)

    required_waypoints: list[Point] = []
    for idx in required_indexes:
        if not required_waypoints or not _same_point(required_waypoints[-1], path[idx]):
            required_waypoints.append(path[idx])

    return points, point_cums, required_waypoints, point_indexes


def _route_signature(
    *,
    vehicle_id: str,
    order_id: str,
    leg_type: str,
    route_version: Any,
    path: list[Point],
    segment_count: int,
    max_segment_distance_m: float,
    shape_waypoints_per_segment: int,
    active_leg: bool,
) -> str:
    """生成路线签名；签名变了就说明需要重新分段并刷新静态 ETA。"""
    # active_leg 的第一个点通常是 5 秒一变的车辆实时位置，不能让它触发重切。
    # 但 route_version 之外仍保留稳定路径签名，防止调用方忘记更新版本号时
    # 复用旧的 P/D 停靠点分段。
    stable_path = path[1:] if active_leg and len(path) > 1 else path
    raw: Any = {
        "vehicle_id": vehicle_id,
        "order_id": order_id,
        "leg_type": leg_type,
        "route_version": None if route_version is None else str(route_version),
        "segment_count": segment_count,
        "max_segment_distance_m": round(float(max_segment_distance_m), 3),
        "shape_waypoints_per_segment": int(shape_waypoints_per_segment),
        "path": [_point_key(p) for p in stable_path],
    }

    text = json.dumps(raw, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _xy(point: Point, ref: Point) -> tuple[float, float]:
    radius = 6371000.0
    rad = math.pi / 180.0
    x = (point["lon"] - ref["lon"]) * rad * radius * math.cos(ref["lat"] * rad)
    y = (point["lat"] - ref["lat"]) * rad * radius
    return x, y


def _project_progress_m(path: list[Point], position: Point) -> float:
    """把车辆实时位置投影到自有轨迹上，估计已经走过的里程。"""
    if len(path) < 2:
        return 0.0

    ref = path[0]
    pos_x, pos_y = _xy(position, ref)
    best_dist_sq = float("inf")
    best_progress = 0.0
    walked = 0.0

    for idx in range(1, len(path)):
        a = path[idx - 1]
        b = path[idx]
        ax, ay = _xy(a, ref)
        bx, by = _xy(b, ref)
        vx = bx - ax
        vy = by - ay
        seg_len_sq = vx * vx + vy * vy
        seg_len = math.sqrt(seg_len_sq)
        if seg_len <= 0:
            continue

        t = ((pos_x - ax) * vx + (pos_y - ay) * vy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        proj_x = ax + t * vx
        proj_y = ay + t * vy
        dist_sq = (pos_x - proj_x) ** 2 + (pos_y - proj_y) ** 2
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_progress = walked + t * seg_len
        walked += seg_len

    return best_progress


def _sample_inner_points(path: list[Point], start_idx: int, end_idx: int, max_count: int) -> list[Point]:
    """从 A* 子段中抽取少量内部节点，作为高德 waypoints 约束形状。"""
    if max_count <= 0 or end_idx - start_idx <= 1:
        return []

    inner_indexes = list(range(start_idx + 1, end_idx))
    if len(inner_indexes) <= max_count:
        return [path[idx] for idx in inner_indexes]

    picked: list[int] = []
    last = len(inner_indexes) - 1
    for k in range(max_count):
        idx = inner_indexes[round((k + 1) * last / (max_count + 1))]
        if idx not in picked:
            picked.append(idx)

    return [path[idx] for idx in picked]


def _sample_inner_points_after_progress(
    path: list[Point],
    cums: list[float],
    start_idx: int,
    end_idx: int,
    progress_m: float,
    max_count: int,
) -> list[Point]:
    """为 live 段抽取车辆当前位置之后的 A* 中间点。"""
    if max_count <= 0 or end_idx - start_idx <= 1:
        return []

    inner_indexes = [
        idx for idx in range(start_idx + 1, end_idx) if idx < len(cums) and cums[idx] > progress_m
    ]
    if len(inner_indexes) <= max_count:
        return [path[idx] for idx in inner_indexes]

    picked: list[int] = []
    last = len(inner_indexes) - 1
    for k in range(max_count):
        idx = inner_indexes[round((k + 1) * last / (max_count + 1))]
        if idx not in picked:
            picked.append(idx)

    return [path[idx] for idx in picked]


def _result_ok(result: Mapping[str, Any] | None) -> bool:
    return bool(result and result.get("ok"))


def _brief_result(result: Mapping[str, Any] | None, include_polyline: bool) -> dict[str, Any] | None:
    if not result:
        return None
    out: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "duration_sec": result.get("duration_sec"),
        "distance_m": result.get("distance_m"),
        "waypoint_count": result.get("waypoint_count"),
        "cached": bool(result.get("cached", False)),
        "error": result.get("error"),
    }
    if include_polyline and result.get("polyline") is not None:
        out["polyline"] = result.get("polyline")
    return out


class AmapSegmentEtaService:
    """可复用的分段 ETA 服务。

    线上建议创建一个服务实例并长期复用：
    - 静态分段结果会留在实例缓存里。
    - 车辆每 5 秒上报位置时，可先调用 update_vehicle_position。
    - planned_route 或 route_version 改变时，get_order_eta 会自动重切分段。
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        config: SegmentEtaConfig | None = None,
        fetcher: Fetcher | None = None,
    ) -> None:
        self.config = config or SegmentEtaConfig()
        self.client = AmapDrivingClient(
            api_key=api_key,
            cache_ttl_sec=self.config.amap_cache_ttl_sec,
            strategy=self.config.strategy,
            fetcher=fetcher,
        )
        self._legs: dict[str, dict[str, Any]] = {}
        self._vehicle_positions: dict[str, Point] = {}
        self._last_amap_request_at = 0.0

    def set_api_key(self, api_key: str) -> None:
        """运行时填写或替换高德 Web 服务 Key。"""
        self.client.api_key = (api_key or "").strip()

    def update_vehicle_position(
        self,
        vehicle_id: str,
        position: Mapping[str, Any],
        *,
        timestamp: float | None = None,
    ) -> None:
        """接收甲方 5 秒一次的车辆位置推送。"""
        pos = _point(position)
        pos["timestamp"] = float(time.time() if timestamp is None else timestamp)
        self._vehicle_positions[str(vehicle_id)] = pos

    def get_order_eta(self, payload: Mapping[str, Any], *, now: float | None = None) -> dict[str, Any]:
        """返回目标订单的接驾 ETA 和送达 ETA。

        payload 详见 AMAP_SEGMENT_ETA_USAGE.md。最关键的是：
        - order / target_order_id
        - vehicle
        - planned_route，且每个 step 最好带 path，即你们 A* 的真实轨迹。
        """
        now_epoch = float(time.time() if now is None else now)
        if payload.get("api_key") is not None:
            self.set_api_key(str(payload.get("api_key") or ""))

        cfg = _merge_config(self.config, payload.get("config") if isinstance(payload.get("config"), Mapping) else None)
        if cfg.amap_cache_ttl_sec != self.client.cache_ttl_sec or cfg.strategy != self.client.strategy:
            self.client.cache_ttl_sec = cfg.amap_cache_ttl_sec
            self.client.strategy = cfg.strategy

        vehicle = payload.get("vehicle")
        if not isinstance(vehicle, Mapping):
            raise ValueError("payload.vehicle is required")
        vid = _vehicle_id(vehicle)
        vehicle_pos = _vehicle_position(vehicle, self._vehicle_positions)

        order = self._resolve_order(payload)
        oid = _order_id(order)
        planned_route = list(payload.get("planned_route", payload.get("plannedRoute", [])) or [])
        route_version = payload.get("route_version", payload.get("routeVersion"))

        base = {
            "provider": "amap",
            "enabled": self.client.enabled,
            "order_id": oid,
            "vehicle_id": vid,
            "route_version": route_version,
            "vehicle_position": vehicle_pos,
            "updated_at_epoch": now_epoch,
        }

        if not self.client.enabled:
            return {
                **base,
                "ok": False,
                "reason": "missing_api_key",
                "active_eta_kind": None,
                "pickup_eta": self._disabled_eta("pickup", "missing_api_key"),
                "dropoff_eta": self._disabled_eta("dropoff", "missing_api_key"),
            }

        state = self._normalize_order_state(order, vehicle)
        if state not in {"waiting", "riding"}:
            return {
                **base,
                "ok": False,
                "reason": f"order_state_{state}",
                "active_eta_kind": None,
                "pickup_eta": self._unavailable_eta("pickup", f"order_state_{state}"),
                "dropoff_eta": self._unavailable_eta("dropoff", f"order_state_{state}"),
            }

        p_idx = _find_step_idx(planned_route, oid, "P")
        d_idx = _find_step_idx(planned_route, oid, "D")

        pickup_leg = None
        dropoff_leg = None
        is_picked_up = state == "riding" or (p_idx < 0 and d_idx >= 0)
        dropoff_origin_kind = None

        # pickup_eta 语义：未上车订单，当前车辆 GPS -> 目标订单 P 点。
        if not is_picked_up and p_idx >= 0:
            pickup_path, pickup_required_stops = _concat_route_leg(
                planned_route,
                0,
                p_idx,
                vehicle_pos,
                start_label="vehicle_position",
            )
            pickup_leg = self._ensure_leg(
                vehicle_id=vid,
                order_id=oid,
                leg_type="pickup",
                path=pickup_path,
                required_stops=pickup_required_stops,
                segment_count=cfg.pickup_segments,
                max_segment_distance_m=cfg.max_segment_distance_m,
                shape_waypoints_per_segment=cfg.shape_waypoints_per_segment,
                route_version=route_version,
                active_leg=True,
            )

        # dropoff_eta 语义：
        # - 未上车：该订单 P 点 -> 该订单 D 点，用于预计上车后的行程时间。
        # - 已上车：当前车辆 GPS -> 该订单 D 点，用于实时送达时间。
        if d_idx >= 0:
            if is_picked_up:
                dropoff_path, dropoff_required_stops = _concat_route_leg(
                    planned_route,
                    0,
                    d_idx,
                    vehicle_pos,
                    start_label="vehicle_position",
                )
                dropoff_active = True
                dropoff_origin_kind = "vehicle_position"
            elif p_idx >= 0 and p_idx < d_idx:
                dropoff_path, dropoff_required_stops = _concat_route_leg(
                    planned_route,
                    p_idx + 1,
                    d_idx,
                    _order_point(order, "pickup"),
                    start_label="P",
                )
                dropoff_active = False
                dropoff_origin_kind = "pickup_point"
            else:
                dropoff_path = []
                dropoff_required_stops = []
                dropoff_active = False

            if dropoff_path:
                dropoff_leg = self._ensure_leg(
                    vehicle_id=vid,
                    order_id=oid,
                    leg_type="dropoff",
                    path=dropoff_path,
                    required_stops=dropoff_required_stops,
                    segment_count=cfg.dropoff_segments,
                    max_segment_distance_m=cfg.max_segment_distance_m,
                    shape_waypoints_per_segment=cfg.shape_waypoints_per_segment,
                    route_version=route_version,
                    active_leg=dropoff_active,
                )

        if pickup_leg:
            self._refresh_static_segments(pickup_leg, cfg, now_epoch)
            self._advance_current_segment(pickup_leg, vehicle_pos, cfg)
            self._refresh_live_segment(pickup_leg, vehicle_pos, cfg, now_epoch)

        if dropoff_leg:
            self._refresh_static_segments(dropoff_leg, cfg, now_epoch)
            if is_picked_up:
                self._advance_current_segment(dropoff_leg, vehicle_pos, cfg)
                self._refresh_live_segment(dropoff_leg, vehicle_pos, cfg, now_epoch)

        if is_picked_up:
            pickup_eta = self._completed_eta("pickup")
            dropoff_eta = self._eta_snapshot(dropoff_leg, "dropoff", active=True, cfg=cfg)
            active_eta_kind = "dropoff"
        else:
            pickup_eta = self._eta_snapshot(pickup_leg, "pickup", active=True, cfg=cfg)
            dropoff_eta = self._eta_snapshot(dropoff_leg, "dropoff", active=False, cfg=cfg)
            active_eta_kind = "pickup"

        if pickup_eta:
            pickup_eta["origin_kind"] = "vehicle_position" if not is_picked_up else "completed"
        if dropoff_eta:
            dropoff_eta["origin_kind"] = dropoff_origin_kind or ("vehicle_position" if is_picked_up else "pickup_point")

        return {
            **base,
            "ok": True,
            "state": state,
            "is_picked_up": is_picked_up,
            "active_eta_kind": active_eta_kind,
            "eta_semantics": "waiting: pickup=current GPS->P, dropoff=P->D; riding: dropoff=current GPS->D",
            "pickup_eta": pickup_eta,
            "dropoff_eta": dropoff_eta,
        }

    async def get_order_eta_async(self, payload: Mapping[str, Any], *, now: float | None = None) -> dict[str, Any]:
        """异步版单订单 ETA。

        内部把同步 urllib 高德请求放进线程池执行，不阻塞 asyncio 事件循环。
        适合 FastAPI / aiohttp / 异步调度服务直接 await。
        """
        return await _run_blocking_io(self.get_order_eta, payload, now=now)

    def get_vehicle_etas(self, payload: Mapping[str, Any], *, now: float | None = None) -> dict[str, Any]:
        """批量返回当前车辆 planned_route 中所有订单的 ETA。

        输入仍是一辆车的一条 planned_route。函数会按订单拆开，分别返回：
        - waiting 订单：pickup_eta = 当前车辆 GPS -> P，dropoff_eta = P -> D 预计行程。
        - riding 订单：pickup_eta = completed，dropoff_eta = 当前车辆 GPS -> D。

        返回里同时给出 orders 列表和 by_order_id 字典，方便业务侧按需读取。
        """
        now_epoch = float(time.time() if now is None else now)
        if payload.get("api_key") is not None:
            self.set_api_key(str(payload.get("api_key") or ""))

        vehicle = payload.get("vehicle")
        if not isinstance(vehicle, Mapping):
            raise ValueError("payload.vehicle is required")
        vid = _vehicle_id(vehicle)
        vehicle_pos = _vehicle_position(vehicle, self._vehicle_positions)
        planned_route = list(payload.get("planned_route", payload.get("plannedRoute", [])) or [])
        route_version = payload.get("route_version", payload.get("routeVersion"))

        orders = self._collect_orders_for_route(payload, planned_route)
        results = []
        by_order_id: dict[str, dict[str, Any]] = {}

        for oid, order in orders:
            child_payload = dict(payload)
            child_payload["target_order_id"] = oid
            child_payload["order"] = order
            result = self.get_order_eta(child_payload, now=now_epoch)
            results.append(result)
            by_order_id[oid] = result

        return {
            "ok": True,
            "provider": "amap",
            "enabled": self.client.enabled,
            "vehicle_id": vid,
            "route_version": route_version,
            "vehicle_position": vehicle_pos,
            "updated_at_epoch": now_epoch,
            "eta_semantics": "waiting: pickup=current GPS->P, dropoff=P->D; riding: dropoff=current GPS->D",
            "orders": results,
            "by_order_id": by_order_id,
        }

    async def get_vehicle_etas_async(self, payload: Mapping[str, Any], *, now: float | None = None) -> dict[str, Any]:
        """异步版批量 ETA。"""
        return await _run_blocking_io(self.get_vehicle_etas, payload, now=now)

    def _collect_orders_for_route(
        self,
        payload: Mapping[str, Any],
        planned_route: list[Mapping[str, Any]],
    ) -> list[tuple[str, Mapping[str, Any]]]:
        raw_orders = payload.get("orders")
        provided: dict[str, Mapping[str, Any]] = {}
        if isinstance(raw_orders, Mapping):
            for key, value in raw_orders.items():
                if isinstance(value, Mapping):
                    provided[str(key)] = value
                    try:
                        provided[_order_id(value)] = value
                    except ValueError:
                        pass
        elif isinstance(raw_orders, list):
            for value in raw_orders:
                if isinstance(value, Mapping):
                    provided[_order_id(value)] = value

        route_points: dict[str, dict[str, Point]] = {}
        order_ids: list[str] = []
        seen: set[str] = set()
        for step in planned_route:
            oid = _step_order_id(step)
            if oid not in seen:
                seen.add(oid)
                order_ids.append(oid)
            step_type = _normalize_step_type(step.get("type"))
            route_points.setdefault(oid, {})["pickup" if step_type == "P" else "dropoff"] = _step_point(step)
            embedded = step.get("order")
            if isinstance(embedded, Mapping):
                provided.setdefault(oid, embedded)

        out: list[tuple[str, Mapping[str, Any]]] = []
        for oid in order_ids:
            base = dict(provided.get(oid, {}))
            base.setdefault("id", oid)
            pts = route_points.get(oid, {})
            if "pickup" not in base and "pNode" not in base and "pickup" in pts:
                base["pickup"] = pts["pickup"]
            if "dropoff" not in base and "dNode" not in base and "dropoff" in pts:
                base["dropoff"] = pts["dropoff"]
            if "state" not in base:
                base["state"] = "waiting" if "pickup" in pts else "riding"
            out.append((oid, base))

        return out

    def _resolve_order(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        order = payload.get("order")
        if isinstance(order, Mapping):
            return order

        target_order_id = payload.get("target_order_id", payload.get("targetOrderId"))
        orders = payload.get("orders")
        if target_order_id is not None and isinstance(orders, Mapping):
            found = orders.get(str(target_order_id), orders.get(target_order_id))
            if isinstance(found, Mapping):
                return found
        if target_order_id is not None and isinstance(orders, list):
            for found in orders:
                if isinstance(found, Mapping) and _order_id(found) == str(target_order_id):
                    return found

        raise ValueError("payload.order or payload.orders[target_order_id] is required")

    def _normalize_order_state(self, order: Mapping[str, Any], vehicle: Mapping[str, Any]) -> str:
        state = str(order.get("state", order.get("status", "")) or "").strip().lower()
        if state in {"waiting", "assigned", "accepted", "pending_pickup", "to_pickup"}:
            return "waiting"
        if state in {"riding", "running", "onboard", "on_board", "to_dropoff"}:
            return "riding"
        if state in {"matching", "unassigned", "created", "done", "completed", "cancelled", "canceled"}:
            return state

        oid = _order_id(order)
        onboard_ids = vehicle.get("on_board_order_ids", vehicle.get("onBoardOrderIds", [])) or []
        if str(oid) in {str(x) for x in onboard_ids}:
            return "riding"
        return "waiting"

    def _ensure_leg(
        self,
        *,
        vehicle_id: str,
        order_id: str,
        leg_type: str,
        path: list[Point],
        required_stops: list[dict[str, Any]],
        segment_count: int,
        max_segment_distance_m: float,
        shape_waypoints_per_segment: int,
        route_version: Any,
        active_leg: bool,
    ) -> dict[str, Any] | None:
        if len(path) < 2:
            return None

        signature = _route_signature(
            vehicle_id=vehicle_id,
            order_id=order_id,
            leg_type=leg_type,
            route_version=route_version,
            path=path,
            segment_count=segment_count,
            max_segment_distance_m=max_segment_distance_m,
            shape_waypoints_per_segment=shape_waypoints_per_segment,
            active_leg=active_leg,
        )
        cache_key = f"{vehicle_id}|{order_id}|{leg_type}"
        cached = self._legs.get(cache_key)
        if cached and cached.get("signature") == signature:
            return cached

        required_points = [stop["point"] for stop in required_stops]
        waypoints, waypoint_cums, required_waypoints, waypoint_path_indexes = _sample_waypoints(
            path,
            segment_count,
            max_segment_distance_m,
            required_points,
        )
        path_cums = _cum_distances(path)
        segments = []
        for idx in range(len(waypoints) - 1):
            start_path_idx = waypoint_path_indexes[idx]
            end_path_idx = waypoint_path_indexes[idx + 1]
            shape_waypoints = _sample_inner_points(
                path,
                start_path_idx,
                end_path_idx,
                shape_waypoints_per_segment,
            )
            segments.append(
                {
                    "index": idx,
                    "start": waypoints[idx],
                    "end": waypoints[idx + 1],
                    "start_cum_m": waypoint_cums[idx],
                    "end_cum_m": waypoint_cums[idx + 1],
                    "astar_distance_m": max(0.0, waypoint_cums[idx + 1] - waypoint_cums[idx]),
                    "start_path_idx": start_path_idx,
                    "end_path_idx": end_path_idx,
                    "shape_waypoints": shape_waypoints,
                    "static": None,
                    "static_error": None,
                    "static_last_try": 0.0,
                    "live": None,
                    "live_error": None,
                    "live_fetched_at": 0.0,
                }
            )

        materialized_stops = []
        for stop in required_stops:
            waypoint_index = None
            for idx, waypoint in enumerate(waypoints):
                if _same_point(waypoint, stop["point"]):
                    waypoint_index = idx
                    break
            materialized_stops.append(
                {
                    "type": stop.get("type"),
                    "order_id": stop.get("order_id"),
                    "point": stop["point"],
                    "waypoint_index": waypoint_index,
                }
            )

        leg = {
            "signature": signature,
            "vehicle_id": vehicle_id,
            "order_id": order_id,
            "leg_type": leg_type,
            "path": path,
            "path_cums": path_cums,
            "waypoints": waypoints,
            "waypoint_cums": waypoint_cums,
            "waypoint_path_indexes": waypoint_path_indexes,
            "required_waypoints": required_waypoints,
            "required_stops": materialized_stops,
            "segments": segments,
            "current_idx": 0,
            "segment_count_requested": segment_count,
            "max_segment_distance_m": max_segment_distance_m,
            "shape_waypoints_per_segment": shape_waypoints_per_segment,
        }
        self._legs[cache_key] = leg
        return leg

    def _refresh_static_segments(self, leg: dict[str, Any], cfg: SegmentEtaConfig, now_epoch: float) -> None:
        for segment in leg["segments"]:
            if _result_ok(segment.get("static")):
                continue
            if segment["static_last_try"] and now_epoch - segment["static_last_try"] < cfg.static_retry_sec:
                continue

            segment["static_last_try"] = now_epoch
            self._throttle_amap_request(cfg)
            result = self.client.estimate_leg(
                segment["start"],
                segment["end"],
                waypoints=segment.get("shape_waypoints") or [],
                now=now_epoch,
            )
            if result.get("ok"):
                segment["static"] = result
                segment["static_error"] = None
            else:
                segment["static_error"] = result.get("error") or result.get("reason") or "amap_static_failed"

    def _advance_current_segment(self, leg: dict[str, Any], vehicle_pos: Point, cfg: SegmentEtaConfig) -> None:
        if not leg["segments"]:
            return

        progress = _project_progress_m(leg["path"], vehicle_pos)
        current_idx = int(leg.get("current_idx", 0))
        last_idx = len(leg["segments"]) - 1

        while current_idx < last_idx:
            end_cum = float(leg["segments"][current_idx]["end_cum_m"])
            if progress < end_cum - cfg.advance_distance_m:
                break
            current_idx += 1

        leg["current_idx"] = max(0, min(current_idx, last_idx))

    def _refresh_live_segment(
        self,
        leg: dict[str, Any],
        vehicle_pos: Point,
        cfg: SegmentEtaConfig,
        now_epoch: float,
    ) -> None:
        segment = leg["segments"][leg["current_idx"]]
        if segment["live_fetched_at"] and now_epoch - segment["live_fetched_at"] < cfg.live_refresh_sec:
            return

        segment["live_fetched_at"] = now_epoch
        self._throttle_amap_request(cfg)
        progress = _project_progress_m(leg["path"], vehicle_pos)
        live_shape_waypoints = _sample_inner_points_after_progress(
            leg["path"],
            leg.get("path_cums") or _cum_distances(leg["path"]),
            int(segment.get("start_path_idx", 0)),
            int(segment.get("end_path_idx", 0)),
            progress,
            cfg.shape_waypoints_per_segment,
        )
        result = self.client.estimate_leg(
            vehicle_pos,
            segment["end"],
            waypoints=live_shape_waypoints,
            now=now_epoch,
        )
        if result.get("ok"):
            segment["live"] = result
            segment["live_shape_waypoints"] = live_shape_waypoints
            segment["live_error"] = None
        else:
            segment["live_error"] = result.get("error") or result.get("reason") or "amap_live_failed"

    def _throttle_amap_request(self, cfg: SegmentEtaConfig) -> None:
        """简单同步限流，避免静态分段批量请求打爆高德 QPS。"""
        if cfg.amap_qps <= 0:
            return
        min_gap = 1.0 / cfg.amap_qps
        now_mono = time.monotonic()
        wait_sec = self._last_amap_request_at + min_gap - now_mono
        if wait_sec > 0:
            time.sleep(wait_sec)
            now_mono = time.monotonic()
        self._last_amap_request_at = now_mono

    def _eta_snapshot(
        self,
        leg: dict[str, Any] | None,
        kind: str,
        *,
        active: bool,
        cfg: SegmentEtaConfig,
    ) -> dict[str, Any]:
        if not leg or not leg.get("segments"):
            return self._unavailable_eta(kind, "empty_leg")

        segments = leg["segments"]
        current_idx = int(leg.get("current_idx", 0)) if active else 0

        dynamic_sec = None
        dynamic_dist_m = None
        dynamic_source = None
        dynamic_segment = None
        missing_count = 0
        error_count = 0
        distance_ratios: list[float] = []

        if active:
            current = segments[current_idx]
            live = current.get("live")
            static = current.get("static")
            if _result_ok(live):
                dynamic_source = "live"
                dynamic_sec = int(live["duration_sec"])
                dynamic_dist_m = int(live.get("distance_m") or 0)
                dynamic_segment = _brief_result(live, cfg.include_polyline)
                if dynamic_segment is not None:
                    astar_distance_m = float(current.get("astar_distance_m") or 0.0)
                    dynamic_segment["astar_distance_m"] = astar_distance_m
                    dynamic_segment["shape_waypoints"] = current.get("live_shape_waypoints", [])
                    dynamic_segment["shape_waypoint_count"] = len(current.get("live_shape_waypoints", []))
                    dynamic_segment["amap_to_astar_distance_ratio"] = (
                        dynamic_dist_m / astar_distance_m if astar_distance_m > 0 else None
                    )
                    if dynamic_segment["amap_to_astar_distance_ratio"] is not None:
                        distance_ratios.append(float(dynamic_segment["amap_to_astar_distance_ratio"]))
            elif _result_ok(static):
                dynamic_source = "static_fallback"
                dynamic_sec = int(static["duration_sec"])
                dynamic_dist_m = int(static.get("distance_m") or 0)
                dynamic_segment = _brief_result(static, cfg.include_polyline)
                if dynamic_segment is not None:
                    astar_distance_m = float(current.get("astar_distance_m") or 0.0)
                    dynamic_segment["astar_distance_m"] = astar_distance_m
                    dynamic_segment["shape_waypoints"] = current.get("shape_waypoints", [])
                    dynamic_segment["shape_waypoint_count"] = len(current.get("shape_waypoints", []))
                    dynamic_segment["amap_to_astar_distance_ratio"] = (
                        dynamic_dist_m / astar_distance_m if astar_distance_m > 0 else None
                    )
                    if dynamic_segment["amap_to_astar_distance_ratio"] is not None:
                        distance_ratios.append(float(dynamic_segment["amap_to_astar_distance_ratio"]))
            else:
                missing_count += 1
                if current.get("live_error") or current.get("static_error"):
                    error_count += 1

        static_sec = 0
        static_dist_m = 0
        static_loaded = 0
        static_total = 0
        start_idx = current_idx + 1 if active else 0
        segment_rows = []

        for idx in range(start_idx, len(segments)):
            segment = segments[idx]
            static_total += 1
            static = segment.get("static")
            amap_distance_m = int(static.get("distance_m") or 0) if _result_ok(static) else None
            astar_distance_m = float(segment.get("astar_distance_m") or 0.0)
            distance_ratio = None
            if amap_distance_m is not None and astar_distance_m > 0:
                distance_ratio = amap_distance_m / astar_distance_m
                distance_ratios.append(float(distance_ratio))
            row = {
                "index": idx,
                "start": segment["start"],
                "end": segment["end"],
                "astar_distance_m": astar_distance_m,
                "shape_waypoints": segment.get("shape_waypoints", []),
                "shape_waypoint_count": len(segment.get("shape_waypoints", [])),
                "static": _brief_result(static, cfg.include_polyline),
                "amap_to_astar_distance_ratio": distance_ratio,
                "static_error": segment.get("static_error"),
            }
            if _result_ok(static):
                static_loaded += 1
                static_sec += int(static["duration_sec"])
                static_dist_m += int(static.get("distance_m") or 0)
            else:
                missing_count += 1
                if segment.get("static_error"):
                    error_count += 1
            segment_rows.append(row)

        eta_seconds = (dynamic_sec or 0) + static_sec if active else static_sec
        eta_distance_m = (dynamic_dist_m or 0) + static_dist_m if active else static_dist_m
        is_complete = missing_count == 0
        suspicious_ratios = [
            ratio
            for ratio in distance_ratios
            if ratio < cfg.distance_ratio_warn_min or ratio > cfg.distance_ratio_warn_max
        ]
        route_match_status = "suspect" if suspicious_ratios else "ok"

        if is_complete:
            status = "ready"
        elif eta_seconds > 0:
            status = "partial"
        elif error_count > 0:
            status = "error"
        else:
            status = "loading"

        return {
            "kind": kind,
            "active": active,
            "status": status,
            "is_complete": is_complete,
            "eta_seconds": eta_seconds if eta_seconds > 0 else None,
            "distance_m": eta_distance_m if eta_distance_m > 0 else None,
            "route_signature": leg["signature"],
            "current_segment_index": current_idx if active else None,
            "requested_segments": leg.get("segment_count_requested"),
            "total_segments": len(segments),
            "waypoints": leg.get("waypoints", []),
            "required_stops": leg.get("required_stops", []),
            "required_stop_count": len(leg.get("required_stops", [])),
            "loaded_static_segments": static_loaded,
            "total_static_segments": static_total,
            "missing_segment_count": missing_count,
            "route_match_status": route_match_status,
            "suspicious_segment_count": len(suspicious_ratios),
            "max_amap_to_astar_distance_ratio": max(distance_ratios) if distance_ratios else None,
            "distance_ratio_warn_range": [cfg.distance_ratio_warn_min, cfg.distance_ratio_warn_max],
            "formula": {
                "dynamic_sec": dynamic_sec,
                "dynamic_source": dynamic_source,
                "following_static_sec": static_sec,
                "eta_seconds": eta_seconds if eta_seconds > 0 else None,
                "text": "eta_seconds = dynamic_sec + following_static_sec" if active else "eta_seconds = static_sec",
            },
            "dynamic_segment": dynamic_segment,
            "static_segments": segment_rows,
        }

    def _disabled_eta(self, kind: str, reason: str) -> dict[str, Any]:
        return {"kind": kind, "active": False, "status": "disabled", "reason": reason, "eta_seconds": None}

    def _unavailable_eta(self, kind: str, reason: str) -> dict[str, Any]:
        return {"kind": kind, "active": False, "status": "not_available", "reason": reason, "eta_seconds": None}

    def _completed_eta(self, kind: str) -> dict[str, Any]:
        return {"kind": kind, "active": False, "status": "completed", "eta_seconds": 0}


_DEFAULT_SERVICES: dict[str, AmapSegmentEtaService] = {}


def _default_service_for_payload(payload: Mapping[str, Any]) -> AmapSegmentEtaService:
    api_key = str(payload.get("api_key") or os.getenv("AMAP_API_KEY") or "")
    if api_key not in _DEFAULT_SERVICES:
        _DEFAULT_SERVICES[api_key] = AmapSegmentEtaService(api_key=api_key)
    return _DEFAULT_SERVICES[api_key]


def get_order_segment_eta(
    payload: Mapping[str, Any],
    *,
    service: AmapSegmentEtaService | None = None,
    fetcher: Fetcher | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """便捷函数：输入 payload，返回对应订单的分段 ETA。

    如果线上要连续接收车辆 5 秒位置推送，建议自己创建并复用 service；
    如果只是脚本临时调用，可以直接用这个函数。
    """
    if service is not None:
        return service.get_order_eta(payload, now=now)

    api_key = str(payload.get("api_key") or os.getenv("AMAP_API_KEY") or "")
    if fetcher is not None:
        temp_service = AmapSegmentEtaService(api_key=api_key, fetcher=fetcher)
        return temp_service.get_order_eta(payload, now=now)

    return _default_service_for_payload(payload).get_order_eta(payload, now=now)


async def get_order_segment_eta_async(
    payload: Mapping[str, Any],
    *,
    service: AmapSegmentEtaService | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """异步便捷函数：单订单 ETA。"""
    svc = service or _default_service_for_payload(payload)
    return await svc.get_order_eta_async(payload, now=now)


def get_vehicle_segment_etas(
    payload: Mapping[str, Any],
    *,
    service: AmapSegmentEtaService | None = None,
    fetcher: Fetcher | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """便捷函数：批量返回当前车辆 planned_route 中所有订单的 ETA。"""
    if service is not None:
        return service.get_vehicle_etas(payload, now=now)

    api_key = str(payload.get("api_key") or os.getenv("AMAP_API_KEY") or "")
    if fetcher is not None:
        temp_service = AmapSegmentEtaService(api_key=api_key, fetcher=fetcher)
        return temp_service.get_vehicle_etas(payload, now=now)

    return _default_service_for_payload(payload).get_vehicle_etas(payload, now=now)


async def get_vehicle_segment_etas_async(
    payload: Mapping[str, Any],
    *,
    service: AmapSegmentEtaService | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """异步便捷函数：批量返回当前车辆 planned_route 中所有订单的 ETA。"""
    svc = service or _default_service_for_payload(payload)
    return await svc.get_vehicle_etas_async(payload, now=now)
