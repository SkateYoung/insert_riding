from __future__ import annotations

import random
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.models import CityGraph, SPEED_MPS
try:
    from .od_forecast_module import export_hex_lookup_rows, orders_from_insert_riding, predict_od_flows_v6
except ImportError:
    from od_forecast_module import export_hex_lookup_rows, orders_from_insert_riding, predict_od_flows_v6


def build_demo_orders(city: CityGraph) -> list[dict]:
    """生成一批用于接入测试的订单。

    这里不是正式订单生成器，只是为了证明 OD 模块可以接 insert_riding 的 POI/路网。
    时间上故意加入 0-899 秒随机扰动，避免订单全部卡在 00/15/30/45 分。
    """
    rng = random.Random(20260512)
    base = datetime(2026, 5, 1, 0, 0, 0)
    pois = city.pois
    left = pois[:10]
    middle = pois[10:20]
    right = pois[20:]
    orders: list[dict] = []
    order_id = 1

    for day in range(12):
        day_base = base + timedelta(days=day)
        for slot in range(96):
            if 28 <= slot <= 36:
                volume = rng.randint(5, 9)
                origins, dests = left, middle + right
            elif 46 <= slot <= 50:
                volume = rng.randint(3, 6)
                origins, dests = middle, right
            elif 68 <= slot <= 76:
                volume = rng.randint(5, 8)
                origins, dests = middle + right, left
            elif 84 <= slot <= 88:
                volume = rng.randint(2, 5)
                origins, dests = right, middle
            else:
                volume = rng.randint(0, 1)
                origins, dests = pois, pois

            for _ in range(volume):
                # 真实订单一般不会刚好发生在 15 分钟边界。
                # 模型内部会自动归入 15 分钟窗口，但这里保留原始秒级时间。
                current = day_base + timedelta(minutes=slot * 15, seconds=rng.randint(0, 899))
                p = rng.choice(origins)
                d = rng.choice(dests)
                if p.id == d.id:
                    continue
                orders.append({"id": order_id, "req_time": current, "p_node": p, "d_node": d})
                order_id += 1
    return orders


def main() -> None:
    print("=== OD预测模块接入测试 ===")
    shp_path = "dxc_traffic_mars_shp/dxc_rule_tran.shp"
    city = CityGraph(shp_path)
    raw_orders = build_demo_orders(city)
    clean_orders = orders_from_insert_riding(raw_orders, city_map=city, speed_mps=SPEED_MPS)
    forecast_start_time = datetime(2026, 5, 13, 8, 0, 0)
    predictions, lookup, metrics = predict_od_flows_v6(clean_orders, forecast_start_time=forecast_start_time, top_k=50)
    hex_rows = export_hex_lookup_rows(lookup)

    print("\n[输入模块]")
    print(f"city_map: {shp_path}")
    print(f"poi_count: {len(city.pois)}")
    print(f"raw_order_count: {len(raw_orders)}")
    print("raw_order_fields: id, req_time, p_node, d_node")
    print("raw_order_time_sample:", [o["req_time"].isoformat(sep=" ") for o in raw_orders[:8]])
    sample = clean_orders[0]
    print(
        "clean_order_sample:",
        {
            "request_id": sample.request_id,
            "request_time": sample.request_time.isoformat(sep=" "),
            "o_poi_id": sample.o_poi_id,
            "d_poi_id": sample.d_poi_id,
            "network_dist_m": round(sample.network_dist_m or 0.0, 2),
            "travel_time_min": round(sample.travel_time_min or 0.0, 2),
        },
    )

    print("\n[内部映射]")
    print(f"hex_count: {len(hex_rows)}")
    print("hex_lookup_columns: hex_label, h3_hex_id, center_lon, center_lat, sample_count, resolution")
    print("hex_lookup_sample:", hex_rows[:5])

    print("\n[输出模块]")
    print(
        "prediction_columns: forecast_start_time, forecast_end_time, horizon_min, "
        "o_center_lon, o_center_lat, d_center_lon, d_center_lat, pred_count"
    )
    print("v6_eval_metrics:", metrics)
    for horizon in (15, 30, 60):
        print(f"\nT+{horizon}min Top5:")
        for row in [r for r in predictions if r["horizon_min"] == horizon][:5]:
            print(row)

    with open("od_forecast_v6_compact_output.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(predictions[0].keys()))
        writer.writeheader()
        writer.writerows(predictions)

    hex_cols = ["hex_label", "h3_hex_id", "center_lon", "center_lat", "sample_count", "resolution", "coord_system"]
    with open("od_hex_lookup_output.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=hex_cols)
        writer.writeheader()
        writer.writerows({c: row.get(c, "") for c in hex_cols} for row in hex_rows)

    print("\n[文件输出]")
    print("od_forecast_v6_compact_output.csv")
    print("od_hex_lookup_output.csv")


if __name__ == "__main__":
    main()
