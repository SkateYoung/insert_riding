from __future__ import annotations

"""OD 预测模块。

这个文件只负责一件事：把订单对象转换成OD预测结果。
外部调度系统不需要知道内部的 slot_idx、H3 编码、训练特征等细节，只需要拿到：

forecast_start_time, forecast_end_time,
o_center_lon, o_center_lat, d_center_lon, d_center_lat, pred_count等字段数据

注意：
1. 输出只保留 pred_count > 0 的 OD，预测为 0 的 OD 不输出。
2. 经纬度中心点使用 insert_riding 路网/POI 的坐标体系，不直接复用 new_hex_precision 的旧坐标。
3. 订单可以是 Python 对象，也可以是 dict，只要能提供 o_node/d_node 和 req_time。
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

import numpy as np

try:
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
except Exception:  # pragma: no cover - optional runtime dependency
    HistGradientBoostingClassifier = None
    HistGradientBoostingRegressor = None


H3_RESOLUTION = 9
SLOT_MINUTES = 15
HORIZONS_MIN = (15, 30, 60)
DEFAULT_BASE_DATETIME = datetime(2026, 1, 1, 0, 0, 0)

try:
    import h3  # type: ignore
except Exception:  # pragma: no cover - fallback keeps the module runnable without h3.
    h3 = None


# ============================================================
# 功能一：预测模块内部标准订单结构
# 相关类型：CleanOrder
# ============================================================

@dataclass(frozen=True)
class CleanOrder:
    """统一后的干净订单格式。

    为了后面训练稳定，先统一成这个格式：
    - request_time: 真实时间或由仿真秒数换算后的时间
    - o/d_lon/lat: 上下车 POI 节点经纬度
    - network_dist_m/travel_time_min: 可选，用于后续扩展特征
    """

    request_id: str
    request_time: datetime
    o_lon: float
    o_lat: float
    d_lon: float
    d_lat: float
    o_poi_id: str
    d_poi_id: str
    network_dist_m: float | None = None
    travel_time_min: float | None = None


# ============================================================
# 功能二：外部订单输入适配与时间标准化
# 相关方法：_node_id、_node_lon_lat、_read_order_value、
#          normalize_request_time、orders_from_insert_riding
# ============================================================

def _node_id(node: Any) -> str:
    """读取节点 ID，兼容 dict 和对象两种输入。

    Args:
        node (Any): 路网节点 dict 或具有 id 属性的对象。

    Returns:
        str: 节点 ID；缺失时返回空字符串。
    """
    if isinstance(node, dict):
        return str(node.get("id", ""))
    return str(getattr(node, "id", ""))


def _node_lon_lat(node: Any) -> tuple[float, float]:
    """读取节点经纬度，兼容 dict 和对象两种输入。

    Args:
        node (Any): 包含 lon/lat 的 dict 或对象。

    Returns:
        tuple[float, float]: (lon, lat)。
    """
    if isinstance(node, dict):
        return float(node["lon"]), float(node["lat"])
    return float(getattr(node, "lon")), float(getattr(node, "lat"))


def _read_order_value(order: Any, attr: str, key: str | None = None, default: Any = None) -> Any:
    """读取订单字段，兼容 dict 和对象。

    Args:
        order (Any): 订单 dict 或 Order 对象。
        attr (str): 对象属性名。
        key (str | None): dict 键名；为空时使用 attr。
        default (Any): 字段缺失时返回的默认值。

    Returns:
        Any: 读取到的字段值或默认值。
    """
    if isinstance(order, dict):
        return order.get(key or attr, default)
    return getattr(order, attr, default)


def normalize_request_time(value: Any, base_datetime: datetime | None = None) -> datetime:
    """把各种时间输入统一成 datetime。

    insert_riding 有两种常见时间：
    - req_time 是仿真秒数，例如 3600.0，表示从 base_datetime 起过了 1 小时
    - req_time/request_time 已经是真实 datetime 或字符串

    模型内部会再把 datetime 归入 15 分钟窗口，但原始订单时间不会被强行改成整点。

    Args:
        value (Any): 时间输入，支持 datetime、秒数、ISO 字符串。
        base_datetime (datetime | None): 秒数型时间的基准时间。

    Returns:
        datetime: 去掉微秒后的标准 datetime。
    """
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    if isinstance(value, (int, float)):
        base = base_datetime or DEFAULT_BASE_DATETIME
        return (base + timedelta(seconds=float(value))).replace(microsecond=0)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("/", "-")).replace(microsecond=0)
    raise TypeError(f"unsupported request_time: {value!r}")


def orders_from_insert_riding(
    orders: Iterable[Any],
    city_map: Any | None = None,
    base_datetime: datetime | None = None,
    speed_mps: float | None = None,
) -> list[CleanOrder]:
    """把 insert_riding 订单转成 CleanOrder。

    支持两类输入：
    - 后端 Order 对象：order.request_id/order.request_time/order.o_node/order.d_node
    - 前端/API dict：request_id/request_time/oNode/dNode 或 o_node/d_node

    如果传入 city_map，会用真实路网 get_path 计算 network_dist_m；
    如果再传入 speed_mps，会进一步计算 travel_time_min。

    Args:
        orders (Iterable[Any]): 原始订单对象或字典。
        city_map (Any | None): 可选路网对象，用于计算 OD 路网距离。
        base_datetime (datetime | None): 仿真秒数转换为 datetime 的基准时间。
        speed_mps (float | None): 车辆速度，用于估算行程分钟数。

    Returns:
        list[CleanOrder]: 预测模型使用的标准化订单列表。
    """
    clean: list[CleanOrder] = []
    for idx, order in enumerate(orders, 1):
        request_id = str(_read_order_value(order, "request_id", default=idx))
        raw_time = _read_order_value(order, "request_time", key="request_time")
        if raw_time is None:
            raw_time = _read_order_value(order, "req_time", key="req_time", default=0.0)

        o_node = _read_order_value(order, "o_node", key="o_node")
        d_node = _read_order_value(order, "d_node", key="d_node")
        if o_node is None:
            o_node = _read_order_value(order, "oNode", key="oNode")
        if d_node is None:
            d_node = _read_order_value(order, "dNode", key="dNode")
        if o_node is None or d_node is None:
            raise ValueError("each order must provide o_node/d_node or oNode/dNode")

        o_lon, o_lat = _node_lon_lat(o_node)
        d_lon, d_lat = _node_lon_lat(d_node)
        dist = _read_order_value(order, "network_dist_m", key="network_dist_m")
        if dist is None and city_map is not None:
            dist, _ = city_map.get_path(o_node, d_node)
        travel_min = None
        if dist is not None and speed_mps and speed_mps > 0:
            travel_min = float(dist) / speed_mps / 60.0

        clean.append(
            CleanOrder(
                request_id=request_id,
                request_time=normalize_request_time(raw_time, base_datetime),
                o_lon=o_lon,
                o_lat=o_lat,
                d_lon=d_lon,
                d_lat=d_lat,
                o_poi_id=_node_id(o_node),
                d_poi_id=_node_id(d_node),
                network_dist_m=None if dist is None else float(dist),
                travel_time_min=travel_min,
            )
        )
    return clean


# ============================================================
# 功能三：OD 网格编码、中心点反查与预测结果地理映射
# 相关方法：_fallback_cell、_cell_for、_cell_center、build_hex_lookup
# ============================================================

def _fallback_cell(lon: float, lat: float, cell_m: float = 180.0) -> str:
    """没有 h3 库时的兜底网格。

    正常情况下会优先用 h3。这个兜底只是为了让模块在没有 h3 的环境也能跑通，
    不是最终科研口径的标准 hex。
    """
    lat_m = lat * 111_320.0
    lon_m = lon * 111_320.0 * math.cos(math.radians(lat))
    q = int(round(lon_m / cell_m))
    r = int(round((lat_m - (q % 2) * cell_m * 0.5) / (cell_m * 0.8660254)))
    return f"fallback_{q}_{r}"


def _cell_for(lon: float, lat: float, resolution: int) -> str:
    """把一个经纬度点映射到 hex 单元。

    Args:
        lon (float): 经度。
        lat (float): 纬度。
        resolution (int): H3 分辨率。

    Returns:
        str: H3 单元 ID；h3 不可用时返回 fallback 网格 ID。
    """
    if h3 is not None:
        if hasattr(h3, "latlng_to_cell"):
            return str(h3.latlng_to_cell(lat, lon, resolution))
        if hasattr(h3, "geo_to_h3"):
            return str(h3.geo_to_h3(lat, lon, resolution))
    return _fallback_cell(lon, lat)


def _cell_center(cell: str, samples: list[tuple[float, float]]) -> tuple[float, float]:
    """返回该网格的标准几何中心坐标。
    
    由于系统传入 h3 库的经纬度本身就是 GCJ-02（火星坐标），
    所以 h3 返回的中心点也天然是 GCJ-02 坐标，可以直接在火星底图上使用，
    无需再做 WGS84 -> GCJ-02 的转化。

    Args:
        cell (str): H3 或 fallback 网格 ID。
        samples (list[tuple[float, float]]): 落入该网格的样本点。

    Returns:
        tuple[float, float]: 网格中心经纬度。
    """
    if h3 is not None and not cell.startswith("fallback"):
        if hasattr(h3, "cell_to_latlng"):
            lat, lon = h3.cell_to_latlng(cell)
        else:
            lat, lon = h3.h3_to_geo(cell)
        return float(lon), float(lat)
        
    # 如果环境没有 h3 导致使用了 fallback 兜底网格，则退化回样本均值中心
    lon = sum(p[0] for p in samples) / max(len(samples), 1)
    lat = sum(p[1] for p in samples) / max(len(samples), 1)
    return lon, lat


def build_hex_lookup(clean_orders: Iterable[CleanOrder], resolution: int = H3_RESOLUTION) -> dict[str, dict[str, Any]]:
    """根据订单动态生成 hex 映射表。

    不写死 POI，也不复用 new_hex_precision 的旧 hex_lookup。
    换一套路网/POI，只要订单里有经纬度，这里就会重新生成 H001、H002 这种简单标签。

    Args:
        clean_orders (Iterable[CleanOrder]): 标准化订单。
        resolution (int): H3 分辨率。

    Returns:
        dict[str, dict[str, Any]]: 原始 cell ID 到展示标签和中心坐标的映射。
    """
    cell_points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for order in clean_orders:
        o_cell = _cell_for(order.o_lon, order.o_lat, resolution)
        d_cell = _cell_for(order.d_lon, order.d_lat, resolution)
        cell_points[o_cell].append((order.o_lon, order.o_lat))
        cell_points[d_cell].append((order.d_lon, order.d_lat))

    rows: list[tuple[str, float, float, list[tuple[float, float]]]] = []
    for cell, points in cell_points.items():
        center_lon, center_lat = _cell_center(cell, points)
        rows.append((cell, center_lon, center_lat, points))
    rows.sort(key=lambda x: (x[2], x[1], x[0]))

    lookup: dict[str, dict[str, Any]] = {}
    for i, (cell, center_lon, center_lat, points) in enumerate(rows, 1):
        lookup[cell] = {
            "hex_label": f"H{i:03d}",
            "h3_hex_id": cell,
            "center_lon": center_lon,
            "center_lat": center_lat,
            "sample_count": len(points),
            "resolution": resolution,
            "coord_system": "same_as_insert_riding_map",
        }
    return lookup


# ============================================================
# 功能四：轻量历史统计 OD 预测
# 相关方法：_slot_floor、_slot_index、_label_order、_compact_row、
#          _positive_rows、predict_od_flows
# ============================================================

def _slot_floor(dt: datetime) -> datetime:
    """归入 15 分钟窗口起点，例如 08:07:23 -> 08:00:00。"""
    minute = (dt.minute // SLOT_MINUTES) * SLOT_MINUTES
    return dt.replace(minute=minute, second=0, microsecond=0)


def _slot_index(dt: datetime) -> int:
    """内部时间片编号，一天 96 个；只用于训练，不对外输出。"""
    return dt.hour * 4 + dt.minute // SLOT_MINUTES


def _label_order(order: CleanOrder, lookup: dict[str, dict[str, Any]], resolution: int = H3_RESOLUTION) -> tuple[str, str]:
    """把订单 OD 经纬度转换为内部 hex 展示标签。

    Args:
        order (CleanOrder): 标准化订单。
        lookup (dict): build_hex_lookup 生成的 cell 映射表。
        resolution (int): H3 分辨率。

    Returns:
        tuple[str, str]: (上车 hex_label, 下车 hex_label)。
    """
    o_cell = _cell_for(order.o_lon, order.o_lat, resolution)
    d_cell = _cell_for(order.d_lon, order.d_lat, resolution)
    return lookup[o_cell]["hex_label"], lookup[d_cell]["hex_label"]


def _compact_row(
    forecast_start_time: datetime,
    horizon: int,
    o_hex: dict[str, Any],
    d_hex: dict[str, Any],
    pred_count: int,
) -> dict[str, Any]:
    """最终交付给调度模块的一行结果。

    对外只保留窗口时间、起终点中心坐标、预测单数。
    不输出内部 hex_label、score、slot_idx，避免对接方误用内部调试字段。
    """
    return {
        "forecast_start_time": forecast_start_time.isoformat(sep=" "),
        "forecast_end_time": (forecast_start_time + timedelta(minutes=horizon)).isoformat(sep=" "),
        "horizon_min": int(horizon),
        "o_center_lon": round(float(o_hex["center_lon"]), 8),
        "o_center_lat": round(float(o_hex["center_lat"]), 8),
        "d_center_lon": round(float(d_hex["center_lon"]), 8),
        "d_center_lat": round(float(d_hex["center_lat"]), 8),
        "pred_count": int(pred_count),
    }


def _positive_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """统一过滤输出：只保留预测单数大于 0 的 OD。

    Args:
        rows (Iterable[dict[str, Any]]): 原始预测结果。

    Returns:
        list[dict[str, Any]]: pred_count 为正数的预测结果。
    """
    return [row for row in rows if int(row.get("pred_count", 0)) > 0]


def predict_od_flows(
    clean_orders: Iterable[CleanOrder],
    forecast_time: datetime | None = None,
    horizons_min: Iterable[int] = HORIZONS_MIN,
    top_k: int = 20,
    resolution: int = H3_RESOLUTION,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """轻量历史统计版本，作为 sklearn 不可用时的兜底模型。

    这个函数不是主力 v6 模型，只用于快速跑通：
    - 同一时间段历史需求
    - 最近两小时需求
    - pair 总体基线
    三者加权得到 pred_count。

    Args:
        clean_orders (Iterable[CleanOrder]): 标准化订单样本。
        forecast_time (datetime | None): 预测窗口起点；为空时使用最后一单后的下一个窗口。
        horizons_min (Iterable[int]): 预测时间跨度，单位分钟。
        top_k (int): 参与预测的高频 OD 数量。
        resolution (int): H3 分辨率。

    Returns:
        tuple: (预测结果行列表, hex 映射表)。
    """
    orders = sorted(list(clean_orders), key=lambda x: x.request_time)
    if not orders:
        return [], {}

    lookup = build_hex_lookup(orders, resolution=resolution)
    labeled: list[tuple[datetime, int, str, str]] = []
    for order in orders:
        o_label, d_label = _label_order(order, lookup, resolution)
        labeled.append((_slot_floor(order.request_time), _slot_index(order.request_time), o_label, d_label))

    if forecast_time is None:
        forecast_time = _slot_floor(orders[-1].request_time + timedelta(minutes=SLOT_MINUTES))
    else:
        forecast_time = _slot_floor(forecast_time)

    hist = [(t, s, o, d) for t, s, o, d in labeled if t < forecast_time and o != d]
    if not hist:
        return [], lookup

    all_pairs = Counter((o, d) for _, _, o, d in hist)
    candidate_pairs = [pair for pair, _ in all_pairs.most_common(top_k)]
    label_lookup = {row["hex_label"]: row for row in lookup.values()}
    slot = _slot_index(forecast_time)
    recent_start = forecast_time - timedelta(hours=2)
    recent_counts = Counter((o, d) for t, _, o, d in hist if recent_start <= t < forecast_time)
    same_slot_counts = Counter((o, d) for _, s, o, d in hist if s == slot)
    days = max(1.0, (forecast_time.date() - hist[0][0].date()).days + 1)
    recent_slots = 8.0

    rows: list[dict[str, Any]] = []
    for horizon in horizons_min:
        steps = max(1, int(round(horizon / SLOT_MINUTES)))
        for o_label, d_label in candidate_pairs:
            o_hex = label_lookup[o_label]
            d_hex = label_lookup[d_label]
            base_rate = all_pairs[(o_label, d_label)] / days / 96.0
            same_slot_rate = same_slot_counts[(o_label, d_label)] / days
            recent_rate = recent_counts[(o_label, d_label)] / recent_slots
            pred = steps * (0.50 * same_slot_rate + 0.35 * recent_rate + 0.15 * base_rate)
            pred_count = int(max(0, round(pred)))
            if pred_count == 0 and (same_slot_counts[(o_label, d_label)] > 0 or recent_counts[(o_label, d_label)] > 0):
                pred_count = 1
            if pred_count > 0:
                rows.append(_compact_row(forecast_time, horizon, o_hex, d_hex, pred_count))

    rows = _positive_rows(rows)
    rows.sort(
        key=lambda r: (
            r["horizon_min"],
            -r["pred_count"],
            r["o_center_lon"],
            r["o_center_lat"],
            r["d_center_lon"],
            r["d_center_lat"],
        )
    )
    return rows, lookup


# ============================================================
# 功能五：预测结果导出辅助
# 相关方法：export_hex_lookup_rows
# ============================================================

def export_hex_lookup_rows(lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """导出 hex_label 到地图中心坐标的映射表，供可视化或排查使用。

    Args:
        lookup (dict): build_hex_lookup 生成的映射表。

    Returns:
        list[dict[str, Any]]: 按 hex_label 排序后的映射行。
    """
    return sorted(lookup.values(), key=lambda r: r["hex_label"])


# ============================================================
# 功能六：v6 特征工程、模型预测与评估指标
# 相关方法：_time_range、_dist_proxy、_build_count_series、_features_for、
#          _future_sum、_allocate_integer_budget、_mae、_wape、predict_od_flows_v6
# ============================================================

def _time_range(start: datetime, end: datetime) -> list[datetime]:
    """生成 15 分钟粒度的闭区间时间序列。

    Args:
        start (datetime): 起始窗口。
        end (datetime): 结束窗口。

    Returns:
        list[datetime]: 从 start 到 end 的 15 分钟窗口列表。
    """
    out: list[datetime] = []
    t = start
    while t <= end:
        out.append(t)
        t += timedelta(minutes=SLOT_MINUTES)
    return out


def _dist_proxy(a: dict[str, Any], b: dict[str, Any]) -> float:
    """根据两个 hex 展示中心估算距离，作为模型静态特征。

    Args:
        a (dict): 起点 hex 映射行。
        b (dict): 终点 hex 映射行。

    Returns:
        float: 两个中心点之间的近似平面距离，单位米。
    """
    lon_scale = 111_320.0 * math.cos(math.radians((float(a["center_lat"]) + float(b["center_lat"])) / 2.0))
    dx = (float(a["center_lon"]) - float(b["center_lon"])) * lon_scale
    dy = (float(a["center_lat"]) - float(b["center_lat"])) * 111_320.0
    return math.hypot(dx, dy)


def _build_count_series(
    clean_orders: list[CleanOrder],
    lookup: dict[str, dict[str, Any]],
    forecast_start_time: datetime,
    top_k: int,
    resolution: int,
):
    """构造训练用的 OD-时间序列。

    这里会先筛选历史最活跃的跨区 OD pair，减少稀疏噪声。
    每个 pair 得到一条 15 分钟粒度的计数序列。

    Args:
        clean_orders (list[CleanOrder]): 标准化订单。
        lookup (dict): hex 映射表。
        forecast_start_time (datetime): 预测窗口起点。
        top_k (int): 参与训练的高频 OD 数量。
        resolution (int): H3 分辨率。

    Returns:
        tuple: slots、OD pair 列表、计数 Counter、hex label 反查表。
    """
    labeled: list[tuple[datetime, str, str]] = []
    for order in clean_orders:
        t = _slot_floor(order.request_time)
        if t >= forecast_start_time:
            continue
        o_label, d_label = _label_order(order, lookup, resolution)
        if o_label != d_label:
            labeled.append((t, o_label, d_label))

    if not labeled:
        return [], [], {}, {}

    pair_counts = Counter((o, d) for _, o, d in labeled)
    pairs = [pair for pair, _ in pair_counts.most_common(top_k)]
    count_map = Counter((t, o, d) for t, o, d in labeled if (o, d) in set(pairs))
    start = min(t for t, _, _ in labeled)
    end = max(t for t, _, _ in labeled)
    slots = _time_range(start, forecast_start_time)
    label_lookup = {row["hex_label"]: row for row in lookup.values()}
    return slots, pairs, count_map, label_lookup


def _features_for(
    slot_i: int,
    pair: tuple[str, str],
    slots: list[datetime],
    series: list[int],
    pair_total: int,
    label_lookup: dict[str, dict[str, Any]],
) -> list[float]:
    """构造一条训练/预测特征。

    特征含义：
    - lag_1/2/4/8/96：前 15/30/60/120 分钟、昨天同时间的订单数
    - rolling mean：最近 1/2 小时、昨天附近水平
    - pair_total：这个 OD 历史活跃度
    - dist_km：起终点空间距离
    - sin/cos：一天内时间周期
    - weekend：是否周末

    Args:
        slot_i (int): 当前时间片索引。
        pair (tuple[str, str]): OD hex_label。
        slots (list[datetime]): 时间片列表。
        series (list[int]): 当前 OD 的历史计数序列。
        pair_total (int): 当前 OD 的历史累计单量。
        label_lookup (dict): hex_label 到中心坐标的映射。

    Returns:
        list[float]: 模型训练和预测使用的特征向量。
    """
    t = slots[slot_i]
    lags = []
    for lag in (1, 2, 4, 8, 96):
        lags.append(float(series[slot_i - lag]) if slot_i - lag >= 0 else 0.0)
    rolls = []
    for width in (4, 8, 96):
        start = max(0, slot_i - width)
        rolls.append(float(np.mean(series[start:slot_i])) if slot_i > start else 0.0)

    o_hex = label_lookup[pair[0]]
    d_hex = label_lookup[pair[1]]
    dist_km = _dist_proxy(o_hex, d_hex) / 1000.0
    slot_idx = _slot_index(t)
    return [
        *lags,
        *rolls,
        math.log1p(pair_total),
        dist_km,
        math.sin(2.0 * math.pi * slot_idx / 96.0),
        math.cos(2.0 * math.pi * slot_idx / 96.0),
        1.0 if t.weekday() >= 5 else 0.0,
    ]


def _future_sum(series: list[int], slot_i: int, steps: int) -> int | None:
    """累计未来窗口目标，例如 steps=4 表示未来 60 分钟累计单数。

    Args:
        series (list[int]): 单个 OD 的时间序列。
        slot_i (int): 当前时间片索引。
        steps (int): 需要累计的未来窗口数量。

    Returns:
        int | None: 未来窗口累计订单数；越界时返回 None。
    """
    end = slot_i + steps
    if end > len(series):
        return None
    return int(sum(series[slot_i:end]))


def _allocate_integer_budget(scores: np.ndarray) -> np.ndarray:
    """把模型连续分数压缩成整数单数。

    v6 的核心思想之一是：模型先给每个 OD 一个连续强度分数，
    然后按总预算分配成 0、1、2... 这种可解释的订单数。

    Args:
        scores (np.ndarray): 每个 OD 的连续预测强度。

    Returns:
        np.ndarray: 与 scores 等长的整数预测单数。
    """
    scores = np.clip(scores.astype(float), 0.0, None)
    budget = int(round(float(scores.sum())))
    pred = np.zeros(len(scores), dtype=int)
    if budget <= 0 or len(scores) == 0:
        return pred
    order = np.argsort(-scores)
    if budget <= len(scores):
        pred[order[:budget]] = 1
        return pred
    raw = scores / max(float(scores.sum()), 1e-9) * budget
    base = np.floor(raw).astype(int)
    remainder = budget - int(base.sum())
    if remainder > 0:
        frac_order = np.argsort(-(raw - base))
        base[frac_order[:remainder]] += 1
    return base


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """计算平均绝对误差。

    Args:
        y_true (np.ndarray): 真实值。
        y_pred (np.ndarray): 预测值。

    Returns:
        float: MAE 指标。
    """
    return float(np.mean(np.abs(y_true - y_pred))) if len(y_true) else 0.0


def _wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """计算加权绝对百分比误差。

    Args:
        y_true (np.ndarray): 真实值。
        y_pred (np.ndarray): 预测值。

    Returns:
        float: WAPE 指标。
    """
    return float(np.abs(y_true - y_pred).sum() / max(float(y_true.sum()), 1.0))


def predict_od_flows_v6(
    clean_orders: Iterable[CleanOrder],
    forecast_start_time: datetime,
    horizons_min: Iterable[int] = HORIZONS_MIN,
    top_k: int = 50,
    resolution: int = H3_RESOLUTION,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """在 insert_riding 订单上训练一个 v6-style OD 预测模型。

    流程：
    1. 把订单按 15 分钟窗口聚合成 OD 计数序列。
    2. 选 top_k 个活跃跨区 OD，避免大量全 0 pair 干扰训练。
    3. 用 lag/rolling/time/距离等特征训练 HistGradientBoostingRegressor。
    4. 对 15/30/60 分钟分别预测未来累计单数。
    5. 用整数预算压缩成 pred_count，并且只输出 pred_count > 0 的结果。

    Args:
        clean_orders (Iterable[CleanOrder]): 标准化订单样本。
        forecast_start_time (datetime): 预测窗口起点。
        horizons_min (Iterable[int]): 预测时间跨度，单位分钟。
        top_k (int): 参与训练的高频 OD 数量。
        resolution (int): H3 分辨率。

    Returns:
        tuple: (预测结果行列表, hex 映射表, 训练评估指标列表)。
    """
    if HistGradientBoostingRegressor is None:
        predictions, lookup = predict_od_flows(
            clean_orders,
            forecast_time=forecast_start_time,
            horizons_min=horizons_min,
            top_k=top_k,
            resolution=resolution,
        )
        return predictions, lookup, [{"model": "fallback_history_count", "reason": "sklearn unavailable"}]

    orders = sorted(list(clean_orders), key=lambda x: x.request_time)
    forecast_start_time = _slot_floor(forecast_start_time)
    lookup = build_hex_lookup(orders, resolution=resolution)
    slots, pairs, count_map, label_lookup = _build_count_series(orders, lookup, forecast_start_time, top_k, resolution)
    if not slots or not pairs:
        return [], lookup, []

    pair_series: dict[tuple[str, str], list[int]] = {}
    for pair in pairs:
        o_label, d_label = pair
        pair_series[pair] = [int(count_map[(slot, o_label, d_label)]) for slot in slots]

    forecast_i = slots.index(forecast_start_time)
    metrics: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    holdout_start = max(100, forecast_i - 96 * 3)

    for horizon in horizons_min:
        steps = max(1, int(round(horizon / SLOT_MINUTES)))
        x_all: list[list[float]] = []
        y_all: list[int] = []
        slot_index_all: list[int] = []
        for pair in pairs:
            series = pair_series[pair]
            pair_total = int(sum(series[:forecast_i]))
            for i in range(96, forecast_i):
                target = _future_sum(series, i, steps)
                if target is None:
                    continue
                x_all.append(_features_for(i, pair, slots, series, pair_total, label_lookup))
                y_all.append(target)
                slot_index_all.append(i)

        x = np.asarray(x_all, dtype=float)
        y = np.asarray(y_all, dtype=float)
        slot_arr = np.asarray(slot_index_all, dtype=int)
        train_mask = slot_arr < holdout_start
        test_mask = slot_arr >= holdout_start
        if train_mask.sum() < 20 or test_mask.sum() == 0:
            train_mask = np.ones(len(y), dtype=bool)
            test_mask = np.zeros(len(y), dtype=bool)

        clf = HistGradientBoostingClassifier(
            learning_rate=0.045,
            max_iter=180,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            l2_regularization=0.10,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=10,
            random_state=42,
        )
        reg = HistGradientBoostingRegressor(
            loss="poisson",
            learning_rate=0.045,
            max_iter=180,
            max_leaf_nodes=15,
            min_samples_leaf=10,
            l2_regularization=0.08,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=10,
            random_state=42,
        )

        y_train = y[train_mask]
        x_train = x[train_mask]
        y_train_binary = (y_train > 0).astype(int)
        
        has_both_classes = y_train_binary.sum() > 0 and (1 - y_train_binary).sum() > 0
        if has_both_classes:
            clf.fit(x_train, y_train_binary)
            
        pos_mask = y_train > 0
        has_pos_samples = pos_mask.sum() > 5
        if has_pos_samples:
            reg.fit(x_train[pos_mask], y_train[pos_mask])

        if test_mask.any():
            x_test = x[test_mask]
            if has_both_classes:
                prob = clf.predict_proba(x_test)[:, 1]
            else:
                prob = np.ones(len(x_test)) if y_train_binary.sum() > 0 else np.zeros(len(x_test))
                
            if has_pos_samples:
                pos_mean = np.clip(reg.predict(x_test), 0.0, None)
            else:
                pos_mean = np.zeros(len(x_test))
                
            eval_mean = prob * pos_mean
            eval_count = _allocate_integer_budget(eval_mean)
            y_eval = y[test_mask].astype(int)
            metrics.append(
                {
                    "horizon_min": int(horizon),
                    "model": "v6_two_stage_calibrated",
                    "eval_rows": int(test_mask.sum()),
                    "mae": round(_mae(y_eval, eval_count), 4),
                    "wape": round(_wape(y_eval, eval_count), 4),
                    "target_sum": int(y_eval.sum()),
                    "pred_sum": int(eval_count.sum()),
                }
            )

        # Refit on all usable history before producing the online forecast.
        y_full_binary = (y > 0).astype(int)
        has_both_classes_full = y_full_binary.sum() > 0 and (1 - y_full_binary).sum() > 0
        if has_both_classes_full:
            clf.fit(x, y_full_binary)
            
        pos_mask_full = y > 0
        has_pos_samples_full = pos_mask_full.sum() > 5
        if has_pos_samples_full:
            reg.fit(x[pos_mask_full], y[pos_mask_full])

        pred_features = []
        pred_pairs = []
        for pair in pairs:
            series = pair_series[pair]
            pair_total = int(sum(series[:forecast_i]))
            pred_features.append(_features_for(forecast_i, pair, slots, series, pair_total, label_lookup))
            pred_pairs.append(pair)
            
        x_pred = np.asarray(pred_features, dtype=float)
        if has_both_classes_full:
            pred_prob = clf.predict_proba(x_pred)[:, 1]
        else:
            pred_prob = np.ones(len(x_pred)) if y_full_binary.sum() > 0 else np.zeros(len(x_pred))
            
        if has_pos_samples_full:
            pred_pos_mean = np.clip(reg.predict(x_pred), 0.0, None)
        else:
            pred_pos_mean = np.zeros(len(x_pred))
            
        pred_mean = pred_prob * pred_pos_mean
        pred_count = _allocate_integer_budget(pred_mean)
        for pair, count, score in sorted(zip(pred_pairs, pred_count, pred_mean), key=lambda x: (-x[1], -x[2])):
            if int(count) <= 0:
                continue
            o_hex = label_lookup[pair[0]]
            d_hex = label_lookup[pair[1]]
            output_rows.append(_compact_row(forecast_start_time, int(horizon), o_hex, d_hex, int(count)))

    output_rows = _positive_rows(output_rows)
    output_rows.sort(
        key=lambda r: (
            r["horizon_min"],
            -r["pred_count"],
            r["o_center_lon"],
            r["o_center_lat"],
            r["d_center_lon"],
            r["d_center_lat"],
        )
    )
    return output_rows, lookup, metrics
