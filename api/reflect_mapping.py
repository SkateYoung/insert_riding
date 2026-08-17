# -*- coding: utf-8 -*-
"""站点与路网节点反射映射工具。

该模块只负责读取 reflect/reflect_station_table.csv，并按站点名、道路名与方向
建立查询索引。调用方拿到映射坐标后，仍需在当前 CityGraph 中查找实际
可用于 A* 的路网节点。
"""

import csv
import math
from pathlib import Path


REFLECT_CSV_PATH = Path(__file__).resolve().parents[1] / "reflect" / "reflect_station_table.csv"
REFLECT_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "gb18030")


def normalize_reflect_text(value):
    """规范化映射表匹配文本。"""
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def reflect_key(station_name, road_name, direction):
    """生成站点名、道路名与方向组合匹配键。"""
    return (
        normalize_reflect_text(station_name),
        normalize_reflect_text(road_name),
        normalize_reflect_text(direction),
    )


def _float_or_none(value):
    """把 CSV 字段转换成有限浮点数。"""
    if value in (None, ""):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _read_rows_with_encoding(path):
    """按常见编码尝试读取 CSV 行。"""
    last_error = None
    for encoding in REFLECT_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle)), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return [], None


def load_reflect_station_index(path=None):
    """读取 reflect_station_table.csv 并建立站点映射索引。

    Returns:
        dict: key 为 ``(STIONNAME, name, Calc_Dir)`` 的规范化组合，
        value 为包含 ``gd_lng``、``gd_lat`` 等字段的映射记录。
    """
    csv_path = Path(path) if path is not None else REFLECT_CSV_PATH
    if not csv_path.exists():
        return {}

    try:
        rows, encoding = _read_rows_with_encoding(csv_path)
    except (OSError, UnicodeDecodeError):
        return {}

    index = {}
    for row_number, row in enumerate(rows, start=2):
        key = reflect_key(row.get("STIONNAME"), row.get("name"), row.get("Calc_Dir"))
        if not key[0] or not key[1] or not key[2]:
            continue

        lon = _float_or_none(row.get("gd_lng"))
        lat = _float_or_none(row.get("gd_lat"))
        if lon is None or lat is None:
            continue

        item = {
            "station_name": normalize_reflect_text(row.get("STIONNAME")),
            "road_name": normalize_reflect_text(row.get("name")),
            "direction": normalize_reflect_text(row.get("Calc_Dir")),
            "gd_lng": lon,
            "gd_lat": lat,
            "row_number": row_number,
            "encoding": encoding,
            "source_file": str(csv_path),
        }
        if key not in index:
            index[key] = item
    return index


def find_reflect_station(index, poi_name, road_name, direction):
    """按 map_poi 站点名、道路名与方向查找映射记录。"""
    if not index:
        return None
    return index.get(reflect_key(poi_name, road_name, direction))
