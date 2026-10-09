"""从琶洲 SHP 生成浏览器 Demo 使用的精简路网数据。"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import shapefile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "shp" / "pazhou_shp_0909" / "pazhou_0909_20m.shp"
OUTPUT = ROOT / "demo" / "pazhou_network_data.js"
EARTH_RADIUS_M = 6_371_000.0


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(value))


def largest_strongly_connected_component(adjacency: list[dict[int, float]]) -> set[int]:
    reverse: list[list[int]] = [[] for _ in adjacency]
    for source, neighbors in enumerate(adjacency):
        for target in neighbors:
            reverse[target].append(source)

    visited: set[int] = set()
    order: list[int] = []
    for start in range(len(adjacency)):
        if start in visited:
            continue
        visited.add(start)
        stack = [(start, 0, list(adjacency[start]))]
        while stack:
            node, index, neighbors = stack[-1]
            if index < len(neighbors):
                target = neighbors[index]
                stack[-1] = (node, index + 1, neighbors)
                if target not in visited:
                    visited.add(target)
                    stack.append((target, 0, list(adjacency[target])))
            else:
                order.append(node)
                stack.pop()

    visited.clear()
    components: list[set[int]] = []
    for start in reversed(order):
        if start in visited:
            continue
        component: set[int] = set()
        visited.add(start)
        stack = [start]
        while stack:
            node = stack.pop()
            component.add(node)
            for target in reverse[node]:
                if target not in visited:
                    visited.add(target)
                    stack.append(target)
        components.append(component)
    return max(components, key=len)


def build_network() -> dict:
    reader = shapefile.Reader(str(SOURCE), encoding="utf-8", encodingErrors="strict")
    coordinates: list[tuple[float, float]] = []
    coordinate_ids: dict[tuple[float, float], int] = {}
    adjacency_maps: list[dict[int, float]] = []
    raw_segments: list[tuple[int, int, str, str]] = []

    def node_id(point) -> int:
        key = (round(float(point[0]), 6), round(float(point[1]), 6))
        existing = coordinate_ids.get(key)
        if existing is not None:
            return existing
        index = len(coordinates)
        coordinate_ids[key] = index
        coordinates.append(key)
        adjacency_maps.append({})
        return index

    for shape_record in reader.shapeRecords():
        points = shape_record.shape.points
        if len(points) < 2:
            continue
        record = shape_record.record.as_dict()
        one_way = str(record.get("Oneway") or "B").strip().upper()
        road_name = str(record.get("name") or "").strip()
        highway = str(record.get("highway") or "").strip()
        for point_a, point_b in zip(points, points[1:]):
            source = node_id(point_a)
            target = node_id(point_b)
            distance = round(haversine_m(coordinates[source], coordinates[target]), 3)
            old_distance = adjacency_maps[source].get(target)
            if old_distance is None or distance < old_distance:
                adjacency_maps[source][target] = distance
            raw_segments.append((source, target, road_name, highway))
            if one_way == "B":
                old_distance = adjacency_maps[target].get(source)
                if old_distance is None or distance < old_distance:
                    adjacency_maps[target][source] = distance

    component = largest_strongly_connected_component(adjacency_maps)
    old_to_new = {old_id: new_id for new_id, old_id in enumerate(sorted(component))}
    nodes = [[coordinates[old_id][0], coordinates[old_id][1]] for old_id in sorted(component)]
    adjacency = []
    for old_id in sorted(component):
        neighbors = [
            [old_to_new[target], distance]
            for target, distance in adjacency_maps[old_id].items()
            if target in component
        ]
        adjacency.append(neighbors)

    seen_segments: set[tuple[int, int]] = set()
    segments = []
    for source, target, road_name, highway in raw_segments:
        if source not in component or target not in component:
            continue
        new_source = old_to_new[source]
        new_target = old_to_new[target]
        undirected_key = tuple(sorted((new_source, new_target)))
        if undirected_key in seen_segments:
            continue
        seen_segments.add(undirected_key)
        segments.append([new_source, new_target, road_name, highway])

    lons = [point[0] for point in nodes]
    lats = [point[1] for point in nodes]
    return {
        "meta": {
            "source": "shp/pazhou_shp_0909/pazhou_0909_20m.shp",
            "shape_records": len(reader),
            "source_nodes": len(coordinates),
            "nodes": len(nodes),
            "directed_edges": sum(len(neighbors) for neighbors in adjacency),
            "segments": len(segments),
            "bounds": [min(lons), min(lats), max(lons), max(lats)],
        },
        "nodes": nodes,
        "adjacency": adjacency,
        "segments": segments,
    }


def main() -> None:
    network = build_network()
    serialized = json.dumps(network, ensure_ascii=False, separators=(",", ":"))
    OUTPUT.write_text(f"window.PAZHOU_NETWORK={serialized};\n", encoding="utf-8")
    meta = network["meta"]
    print(
        "generated",
        OUTPUT,
        f"nodes={meta['nodes']}",
        f"edges={meta['directed_edges']}",
        f"segments={meta['segments']}",
    )


if __name__ == "__main__":
    main()
