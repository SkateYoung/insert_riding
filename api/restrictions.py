# -*- coding: utf-8 -*-
"""运营禁区策略校验与几何判定工具。

本模块集中处理前端传入的禁区 polygon 规范化、高德 avoidpolygons
参数拼装，以及 A* 路网边是否命中禁区的几何判定。
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


MAX_AMAP_POLYGONS = 32
MAX_AMAP_POLYGON_VERTICES = 16
MAX_AMAP_POLYGON_AREA_KM2 = 81.0
EPSILON = 1e-9


class OperationRestrictionError(ValueError):
    """运营禁区策略不符合高德或本地几何规则时抛出的异常。"""


def _as_float(value: Any, field_name: str) -> float:
    """把输入字段解析为有限浮点数。

    Args:
        value (Any): 待解析的原始输入值。
        field_name (str): 字段名，用于错误提示。

    Returns:
        float: 解析后的有限浮点数。

    Raises:
        OperationRestrictionError: 输入不是数字或不是有限数值。
    """
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise OperationRestrictionError(f"{field_name} 必须是数字") from exc
    if not math.isfinite(result):
        raise OperationRestrictionError(f"{field_name} 必须是有限数值")
    return result


def _as_bool(value: Any) -> bool:
    """兼容布尔值、数字和常见字符串开关。

    Args:
        value (Any): 待解析的原始输入值。

    Returns:
        bool: 输入可视为开启时返回 True。
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _point_from_any(raw: Any, index: int) -> dict[str, float]:
    """把前端传入的 dict/list 坐标统一成 lon/lat 字典。

    Args:
        raw (Any): 前端传入的单个坐标点。
        index (int): 坐标点序号，用于错误提示。

    Returns:
        dict[str, float]: 规范化后的 lon/lat 坐标。

    Raises:
        OperationRestrictionError: 坐标结构非法或经纬度超出范围。
    """
    if isinstance(raw, dict):
        lon = raw.get("lon", raw.get("lng", raw.get("longitude", raw.get("x"))))
        lat = raw.get("lat", raw.get("latitude", raw.get("y")))
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        lon, lat = raw[0], raw[1]
    else:
        raise OperationRestrictionError(f"point[{index}] 必须包含 lon/lat")

    lon = _as_float(lon, f"point[{index}].lon")
    lat = _as_float(lat, f"point[{index}].lat")
    if lon < -180.0 or lon > 180.0:
        raise OperationRestrictionError(f"point[{index}].lon 超出范围")
    if lat < -90.0 or lat > 90.0:
        raise OperationRestrictionError(f"point[{index}].lat 超出范围")
    return {"lon": lon, "lat": lat}


def _same_point(a: dict[str, float], b: dict[str, float]) -> bool:
    """判断两个经纬度点是否可视为同一点。

    Args:
        a (dict): 第一个 lon/lat 坐标。
        b (dict): 第二个 lon/lat 坐标。

    Returns:
        bool: 两点距离小于误差阈值时返回 True。
    """
    return abs(a["lon"] - b["lon"]) <= EPSILON and abs(a["lat"] - b["lat"]) <= EPSILON


def _format_coord(value: float) -> str:
    """按高德参数常用精度格式化单个坐标值。

    Args:
        value (float): 待格式化坐标值。

    Returns:
        str: 去掉多余零位后的坐标文本。
    """
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    return text


def coord_to_amap_text(point: dict[str, Any]) -> str:
    """把点坐标序列化成高德要求的 lon,lat 文本。

    Args:
        point (dict): 包含 lon/lat 的坐标点。

    Returns:
        str: 高德 avoidpolygons 使用的 "lon,lat" 文本。
    """
    return f"{_format_coord(float(point['lon']))},{_format_coord(float(point['lat']))}"


def _project_points_km(points: list[dict[str, float]]) -> list[tuple[float, float]]:
    """把经纬度点近似投影到公里平面，用于面积计算。

    Args:
        points (list[dict]): polygon 顶点坐标。

    Returns:
        list[tuple[float, float]]: 近似投影后的公里平面坐标。
    """
    lat0 = math.radians(sum(point["lat"] for point in points) / len(points))
    lon0 = sum(point["lon"] for point in points) / len(points)
    lat_origin = sum(point["lat"] for point in points) / len(points)
    cos_lat = max(0.01, math.cos(lat0))
    projected = []
    for point in points:
        x = (point["lon"] - lon0) * 111.320 * cos_lat
        y = (point["lat"] - lat_origin) * 110.574
        projected.append((x, y))
    return projected


def polygon_area_km2(points: list[dict[str, float]]) -> float:
    """计算 polygon 近似面积。

    Args:
        points (list[dict]): polygon 顶点坐标。

    Returns:
        float: 近似面积，单位为平方公里。
    """
    projected = _project_points_km(points)
    area = 0.0
    for idx, (x1, y1) in enumerate(projected):
        x2, y2 = projected[(idx + 1) % len(projected)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _orientation(a: dict[str, float], b: dict[str, float], c: dict[str, float]) -> float:
    """计算三点方向叉积，用于线段相交判定。

    Args:
        a (dict): 第一个点。
        b (dict): 第二个点。
        c (dict): 第三个点。

    Returns:
        float: 三点方向叉积。
    """
    return (b["lon"] - a["lon"]) * (c["lat"] - a["lat"]) - (b["lat"] - a["lat"]) * (c["lon"] - a["lon"])


def _on_segment(a: dict[str, float], b: dict[str, float], c: dict[str, float]) -> bool:
    """判断点 b 是否位于线段 ac 上。

    Args:
        a (dict): 线段起点。
        b (dict): 待判断点。
        c (dict): 线段终点。

    Returns:
        bool: 点 b 在线段 ac 上时返回 True。
    """
    if abs(_orientation(a, b, c)) > EPSILON:
        return False
    return (
        min(a["lon"], c["lon"]) - EPSILON <= b["lon"] <= max(a["lon"], c["lon"]) + EPSILON
        and min(a["lat"], c["lat"]) - EPSILON <= b["lat"] <= max(a["lat"], c["lat"]) + EPSILON
    )


def segments_intersect(
    a: dict[str, float],
    b: dict[str, float],
    c: dict[str, float],
    d: dict[str, float],
) -> bool:
    """判断两条经纬度线段是否相交或重叠。

    Args:
        a (dict): 第一条线段起点。
        b (dict): 第一条线段终点。
        c (dict): 第二条线段起点。
        d (dict): 第二条线段终点。

    Returns:
        bool: 两条线段相交或重叠时返回 True。
    """
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    if (o1 > EPSILON and o2 < -EPSILON or o1 < -EPSILON and o2 > EPSILON) and (
        o3 > EPSILON and o4 < -EPSILON or o3 < -EPSILON and o4 > EPSILON
    ):
        return True
    if abs(o1) <= EPSILON and _on_segment(a, c, b):
        return True
    if abs(o2) <= EPSILON and _on_segment(a, d, b):
        return True
    if abs(o3) <= EPSILON and _on_segment(c, a, d):
        return True
    if abs(o4) <= EPSILON and _on_segment(c, b, d):
        return True
    return False


def _is_self_intersecting(points: list[dict[str, float]]) -> bool:
    """检测 polygon 是否存在非相邻边自交。

    Args:
        points (list[dict]): polygon 顶点坐标。

    Returns:
        bool: 存在自相交时返回 True。
    """
    count = len(points)
    for i in range(count):
        a1 = points[i]
        a2 = points[(i + 1) % count]
        for j in range(i + 1, count):
            if abs(i - j) <= 1:
                continue
            if i == 0 and j == count - 1:
                continue
            b1 = points[j]
            b2 = points[(j + 1) % count]
            if segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _polygon_bounds(points: list[dict[str, float]]) -> dict[str, float]:
    """计算 polygon 的经纬度包围盒。

    Args:
        points (list[dict]): polygon 顶点坐标。

    Returns:
        dict[str, float]: 包含 min_lon、max_lon、min_lat、max_lat 的包围盒。
    """
    return {
        "min_lon": min(point["lon"] for point in points),
        "max_lon": max(point["lon"] for point in points),
        "min_lat": min(point["lat"] for point in points),
        "max_lat": max(point["lat"] for point in points),
    }


def _normalize_points(raw_points: Any, polygon_index: int) -> list[dict[str, float]]:
    """规范化单个 polygon 顶点并执行高德限制校验。

    Args:
        raw_points (Any): 前端传入的 polygon 顶点列表。
        polygon_index (int): polygon 序号，用于错误提示。

    Returns:
        list[dict[str, float]]: 去重、去闭合重复点后的顶点列表。

    Raises:
        OperationRestrictionError: 顶点数量、面积或几何形态不符合要求。
    """
    if not isinstance(raw_points, list):
        raise OperationRestrictionError(f"polygon[{polygon_index}].points 必须是列表")
    points: list[dict[str, float]] = []
    for idx, raw_point in enumerate(raw_points):
        point = _point_from_any(raw_point, idx)
        if points and _same_point(points[-1], point):
            continue
        points.append(point)

    if len(points) >= 2 and _same_point(points[0], points[-1]):
        points.pop()
    if len(points) < 3:
        raise OperationRestrictionError(f"polygon[{polygon_index}] 至少需要 3 个不重复顶点")
    if len(points) > MAX_AMAP_POLYGON_VERTICES:
        raise OperationRestrictionError(
            f"polygon[{polygon_index}] 顶点数超过 {MAX_AMAP_POLYGON_VERTICES} 个"
        )

    area = polygon_area_km2(points)
    if area <= 1e-8:
        raise OperationRestrictionError(f"polygon[{polygon_index}] 面积为 0")
    if area > MAX_AMAP_POLYGON_AREA_KM2:
        raise OperationRestrictionError(
            f"polygon[{polygon_index}] 面积超过 {MAX_AMAP_POLYGON_AREA_KM2:g} 平方公里"
        )
    if _is_self_intersecting(points):
        raise OperationRestrictionError(f"polygon[{polygon_index}] 存在自相交")
    return points


def _raw_polygons_from_payload(payload: dict[str, Any]) -> list[Any]:
    """从 API 请求体中读取 polygons 或 polygons_json 字段。

    Args:
        payload (dict): 前端传入的策略请求体。

    Returns:
        list[Any]: 原始 polygon 列表。

    Raises:
        OperationRestrictionError: polygons_json 不是合法 JSON 或 polygons 不是列表。
    """
    raw = payload.get("polygons", payload.get("polygons_json", []))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OperationRestrictionError("polygons_json 必须是合法 JSON") from exc
    if isinstance(raw, dict) and "polygons" in raw:
        raw = raw["polygons"]
    if not isinstance(raw, list):
        raise OperationRestrictionError("polygons 必须是列表")
    return raw


def normalize_policy_payload(payload: dict[str, Any], *, require_identity: bool = True) -> dict[str, Any]:
    """校验并规范化运营禁区策略。

    Args:
        payload (dict): 前端传入的策略请求体。
        require_identity (bool): 是否强制要求 policy_code/policy_name。

    Returns:
        dict: 已规范化、可落库并可直接传给 A* 和高德规划的策略快照。

    Raises:
        OperationRestrictionError: 策略身份、polygon 数量或 polygon 几何校验失败。
    """
    if not isinstance(payload, dict):
        raise OperationRestrictionError("策略数据必须是对象")

    raw_polygons = _raw_polygons_from_payload(payload)
    if not raw_polygons:
        raise OperationRestrictionError("至少需要一个 polygon")
    if len(raw_polygons) > MAX_AMAP_POLYGONS:
        raise OperationRestrictionError(f"最多支持 {MAX_AMAP_POLYGONS} 个 polygon")

    policy_code = str(payload.get("policy_code") or payload.get("code") or "").strip()
    policy_name = str(payload.get("policy_name") or payload.get("name") or policy_code).strip()
    if require_identity and not policy_code:
        raise OperationRestrictionError("policy_code 不能为空")
    if require_identity and not policy_name:
        raise OperationRestrictionError("policy_name 不能为空")

    polygons = []
    total_vertices = 0
    total_area = 0.0
    for polygon_index, raw_polygon in enumerate(raw_polygons):
        if isinstance(raw_polygon, dict):
            raw_points = raw_polygon.get("points", raw_polygon.get("path"))
            polygon_name = raw_polygon.get("name")
        else:
            raw_points = raw_polygon
            polygon_name = None
        points = _normalize_points(raw_points, polygon_index)
        area = polygon_area_km2(points)
        total_vertices += len(points)
        total_area += area
        polygons.append({
            "index": polygon_index,
            "name": str(polygon_name).strip() if polygon_name not in (None, "") else f"polygon-{polygon_index + 1}",
            "points": points,
            "area_km2": round(area, 6),
            "bounds": _polygon_bounds(points),
        })

    amap_avoidpolygons = "|".join(
        ";".join(coord_to_amap_text(point) for point in polygon["points"])
        for polygon in polygons
    )
    normalized = {
        "policy_code": policy_code,
        "policy_name": policy_name,
        "description": payload.get("description"),
        "polygons": polygons,
        "polygons_json": polygons,
        "amap_avoidpolygons": amap_avoidpolygons,
        "polygon_count": len(polygons),
        "vertex_count": total_vertices,
        "total_area_km2": round(total_area, 6),
        "status": str(payload.get("status") or "enabled").strip() or "enabled",
        "is_active": _as_bool(payload.get("is_active", False)),
    }
    normalized["policy_signature"] = restriction_signature(normalized)
    return normalized


def restriction_signature(policy: dict[str, Any] | None) -> str:
    """生成禁区策略签名，用于 A* 缓存和路线版本隔离。

    Args:
        policy (dict | None): 运营禁区策略快照。

    Returns:
        str: 稳定策略签名；无策略时返回 "none"。
    """
    if not policy:
        return "none"
    avoid = str(policy.get("amap_avoidpolygons") or "")
    if not avoid and policy.get("polygons"):
        avoid = "|".join(
            ";".join(coord_to_amap_text(point) for point in polygon.get("points", []))
            for polygon in policy.get("polygons", [])
        )
    if not avoid:
        return "none"
    digest = hashlib.sha1(avoid.encode("utf-8")).hexdigest()[:16]
    code = str(policy.get("policy_code") or "adhoc").strip() or "adhoc"
    return f"{code}:{digest}"


def point_in_polygon(point: dict[str, float], polygon: dict[str, Any]) -> bool:
    """判断点是否位于禁区 polygon 内部或边界上。

    Args:
        point (dict): 待判断 lon/lat 坐标。
        polygon (dict): 规范化后的禁区 polygon。

    Returns:
        bool: 点在 polygon 内部或边界上时返回 True。
    """
    points = polygon.get("points") or []
    if len(points) < 3:
        return False
    for idx, a in enumerate(points):
        b = points[(idx + 1) % len(points)]
        if _on_segment(a, point, b):
            return True

    inside = False
    x = point["lon"]
    y = point["lat"]
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]["lon"], points[i]["lat"]
        xj, yj = points[j]["lon"], points[j]["lat"]
        crosses = (yi > y) != (yj > y)
        if crosses:
            x_intersect = (xj - xi) * (y - yi) / ((yj - yi) or EPSILON) + xi
            if x <= x_intersect + EPSILON:
                inside = not inside
        j = i
    return inside


def segment_intersects_polygon(a: dict[str, float], b: dict[str, float], polygon: dict[str, Any]) -> bool:
    """判断路网边线段是否进入或穿过禁区 polygon。

    Args:
        a (dict): 路网边起点。
        b (dict): 路网边终点。
        polygon (dict): 规范化后的禁区 polygon。

    Returns:
        bool: 线段端点在禁区内或线段穿过禁区边界时返回 True。
    """
    points = polygon.get("points") or []
    if len(points) < 3:
        return False
    if point_in_polygon(a, polygon) or point_in_polygon(b, polygon):
        return True
    for idx, c in enumerate(points):
        d = points[(idx + 1) % len(points)]
        if segments_intersect(a, b, c, d):
            return True
    return False


def edge_is_restricted(policy: dict[str, Any] | None, start_node: Any, end_node: Any) -> bool:
    """判断 A* 的一条有向边是否被当前禁区策略禁止通行。

    Args:
        policy (dict | None): 当前运营禁区策略快照。
        start_node (Node): 有向边起点。
        end_node (Node): 有向边终点。

    Returns:
        bool: 有向边命中禁区时返回 True。
    """
    if not policy:
        return False
    polygons = policy.get("polygons") or policy.get("polygons_json") or []
    if not polygons:
        return False
    a = {"lon": float(start_node.lon), "lat": float(start_node.lat)}
    b = {"lon": float(end_node.lon), "lat": float(end_node.lat)}
    for polygon in polygons:
        points = polygon.get("points") or []
        if len(points) < 3:
            continue
        bounds = polygon.get("bounds") or _polygon_bounds(points)
        if (
            max(a["lon"], b["lon"]) < bounds["min_lon"] - EPSILON
            or min(a["lon"], b["lon"]) > bounds["max_lon"] + EPSILON
            or max(a["lat"], b["lat"]) < bounds["min_lat"] - EPSILON
            or min(a["lat"], b["lat"]) > bounds["max_lat"] + EPSILON
        ):
            continue
        if segment_intersects_polygon(a, b, polygon):
            return True
    return False


def policy_to_response(policy: dict[str, Any] | None) -> dict[str, Any] | None:
    """把内部策略快照整理成 API 可返回的结构。

    Args:
        policy (dict | None): 内部策略快照。

    Returns:
        dict | None: API 响应结构；无策略时返回 None。
    """
    if not policy:
        return None
    result = dict(policy)
    if "polygons_json" in result and "polygons" not in result:
        result["polygons"] = result["polygons_json"]
    result["policy_signature"] = restriction_signature(result)
    return result
