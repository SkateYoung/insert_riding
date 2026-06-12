# 高德分段 ETA 函数使用说明

文件：`amap_segment_eta.py`

这个模块给甲方订单返回两类 ETA：

- `pickup_eta`：接取 ETA，车辆当前位置到乘客上车点。
- `dropoff_eta`：送达 ETA。

状态约束：

- `waiting` 订单：`pickup_eta = 当前车辆GPS -> P点`，`dropoff_eta = P点 -> D点`，用于预计上车后的行程时间。
- `riding` 订单：`pickup_eta.status = "completed"`，`dropoff_eta = 当前车辆GPS -> D点`，用于实时送达时间。

它不会自己做 A*。调用方必须先用自己的路网和调度结果算出车辆剩余停靠点顺序，并把每个停靠点之前的 A* 轨迹点传进来。这样函数才能“按自己的轨迹分段”，而不是让高德自由选一条完全不同的路。

分段逻辑与 `demo.html` 的思路一致：先从全局 `planned_route` 截取当前订单对应的连续 A* 子路径，再在这条子路径上切分段。多订单时，子路径里的其他订单 P/D 点会被强制保留为分段端点。例如 A 的路线是 `P(A) -> P(B) -> D(B) -> D(A)`，那么 A 的预计送达 `dropoff_eta` 会沿 `A.P -> B.P -> B.D -> A.D` 分段，不会退化成 `A.P -> A.D` 直连。

## 最小用法

```python
from amap_segment_eta import get_order_segment_eta

payload = {
    "api_key": "你的高德Web服务Key",
    "target_order_id": "O1001",
    "route_version": "V001-route-17",
    "vehicle": {
        "id": "V001",
        "position": {"lon": 113.300000, "lat": 23.100000},
    },
    "order": {
        "id": "O1001",
        "state": "waiting",
        "pickup": {"id": "P1", "lon": 113.301000, "lat": 23.101000},
        "dropoff": {"id": "D1", "lon": 113.305000, "lat": 23.105000},
    },
    "planned_route": [
        {
            "type": "P",
            "order_id": "O1001",
            "point": {"id": "P1", "lon": 113.301000, "lat": 23.101000},
            "path": [
                {"lon": 113.300000, "lat": 23.100000},
                {"lon": 113.300500, "lat": 23.100500},
                {"lon": 113.301000, "lat": 23.101000},
            ],
        },
        {
            "type": "D",
            "order_id": "O1001",
            "point": {"id": "D1", "lon": 113.305000, "lat": 23.105000},
            "path": [
                {"lon": 113.301000, "lat": 23.101000},
                {"lon": 113.303000, "lat": 23.103000},
                {"lon": 113.305000, "lat": 23.105000},
            ],
        },
    ],
    "config": {
        "pickup_segments": 5,
        "dropoff_segments": 10,
        "live_refresh_sec": 5,
    },
}

eta = get_order_segment_eta(payload)
print(eta["pickup_eta"]["eta_seconds"])
print(eta["dropoff_eta"]["eta_seconds"])  # waiting 订单这里是 P点 -> D点预计行程
```

## 线上推荐用法

如果系统会持续接收甲方 5 秒一次的车辆位置，建议复用一个服务实例。

```python
from amap_segment_eta import AmapSegmentEtaService

eta_service = AmapSegmentEtaService(api_key="你的高德Web服务Key")

# 甲方每 5 秒推送一次车位时调用
eta_service.update_vehicle_position(
    "V001",
    {"lon": 113.300600, "lat": 23.100600},
    timestamp=1710000005,
)

# 查询某个订单 ETA。vehicle 里可以不重复传 position，服务会使用最新推送位置。
payload["vehicle"] = {"id": "V001"}
eta = eta_service.get_order_eta(payload)
```

如果你要一次返回当前车辆所有订单的 ETA，使用批量接口：

```python
payload = {
    "vehicle": {"id": "V001"},
    "route_version": "V001-route-18",
    "orders": [order_a, order_b],
    "planned_route": planned_route,
}

result = eta_service.get_vehicle_etas(payload)
eta_a = result["by_order_id"]["A"]
eta_b = result["by_order_id"]["B"]
```

异步服务里使用 async 接口，内部会把同步高德请求放进线程池，不阻塞事件循环：

```python
eta = await eta_service.get_vehicle_etas_async(payload)
single = await eta_service.get_order_eta_async(payload)
```

也可以运行时填写或替换 Key：

```python
eta_service.set_api_key("新的高德Web服务Key")
```

## 输入字段解释

`api_key`：高德 Web 服务 Key。也可以不传，改用环境变量 `AMAP_API_KEY`，或用 `AmapSegmentEtaService(api_key=...)`。

`target_order_id`：要查询 ETA 的订单 ID。如果 payload 直接传了 `order`，这个字段可省略。

`route_version`：当前车辆规划路线版本。只要车辆 `planned_route` 因为新订单插入、订单取消、上客、下客、2-opt 调整等原因发生变化，就应该换一个新的版本号。版本号变化后，函数会重新分段并刷新静态 ETA。

`vehicle`：

```python
{
    "id": "V001",
    "position": {"lon": 113.300000, "lat": 23.100000},
}
```

`position` 是甲方 5 秒一次推过来的车辆实时经纬度，必须是高德 GCJ-02 坐标系。如果使用 `update_vehicle_position`，查询 ETA 时可以只传 `{"id": "V001"}`。

`order`：

```python
{
    "id": "O1001",
    "state": "waiting",
    "pickup": {"id": "P1", "lon": 113.301000, "lat": 23.101000},
    "dropoff": {"id": "D1", "lon": 113.305000, "lat": 23.105000},
}
```

`state` 支持：

- `waiting`：乘客未上车，当前活动 ETA 是 `pickup_eta`。
- `riding`：乘客已上车，当前活动 ETA 是 `dropoff_eta`。
- `matching` / `unassigned` / `done` / `cancelled`：不返回有效 ETA。

`planned_route` 是车辆接下来真实执行的停靠点序列。每个 step 表示车辆下一站去接人或送人：

```python
{
    "type": "P",                # P=接人，D=送人
    "order_id": "O1001",
    "point": {"lon": 113.301, "lat": 23.101},
    "path": [                   # 从上一停靠点到当前 point 的自有 A* 轨迹
        {"lon": 113.300, "lat": 23.100},
        {"lon": 113.301, "lat": 23.101},
    ],
}
```

多订单时，`planned_route` 要体现真实绕行顺序。例如：

```python
[
    {"type": "P", "order_id": "A", "point": A_pickup, "path": path_car_to_Ap},
    {"type": "P", "order_id": "B", "point": B_pickup, "path": path_Ap_to_Bp},
    {"type": "D", "order_id": "A", "point": A_dropoff, "path": path_Bp_to_Ad},
    {"type": "D", "order_id": "B", "point": B_dropoff, "path": path_Ad_to_Bd},
]
```

如果 A、B 都还是 `waiting`，它们会同时返回接驾 ETA 和预计送达 ETA。其中预计送达 ETA 是按当前 `planned_route` 里从本单 P 到本单 D 的连续 A* 子路径分段计算；这段中间经过的其他订单 P/D 点会保留在 `required_stops` 和 `waypoints` 里。等某个订单真正上车后，把该订单 `state` 改成 `riding`，并从 `planned_route` 中移除它的 P 步骤，此时它的 `dropoff_eta` 会改为当前车辆 GPS 到 D 点。

`config`：

```python
{
    "pickup_segments": 5,
    "dropoff_segments": 10,
    "live_refresh_sec": 5,
    "static_retry_sec": 20,
    "advance_distance_m": 40,
    "max_segment_distance_m": 700,
    "shape_waypoints_per_segment": 4,
    "distance_ratio_warn_min": 0.4,
    "distance_ratio_warn_max": 3.0,
    "amap_qps": 2.5,
    "include_polyline": False,
}
```

- `pickup_segments`：接驾路线切几段，可按业务调整。
- `dropoff_segments`：送达路线切几段，可按业务调整。
- 这两个字段是目标段数。函数会优先保留本 ETA 子路径里的必经 P/D 停靠点；如果必经停靠点很多，实际返回的 `total_segments` 可能大于目标段数。
- `max_segment_distance_m`：单个高德请求覆盖的 A* 子段最长距离。路线很长时，即使 `pickup_segments=5` / `dropoff_segments=10`，函数也会继续加密分段，避免某个高德段太长后自由绕路。
- `shape_waypoints_per_segment`：每个高德分段请求额外携带多少个 A* 中间形状点。比如某段是 `A -> x1 -> x2 -> B`，请求会尽量变成 `origin=A, destination=B, waypoints=x1;x2`，进一步约束高德贴近自有 A* 轨迹。
- `distance_ratio_warn_min` / `distance_ratio_warn_max`：高德返回距离与 A* 子段距离的合理比例范围。超过范围时，返回里的 `route_match_status` 会是 `suspect`，说明高德路线可能没有贴合自有 A*。
- `live_refresh_sec`：当前活动段调高德的最短间隔。甲方 5 秒推车位时建议设为 5。
- `static_retry_sec`：静态段失败后多久重试。
- `advance_distance_m`：车辆距离分段终点多少米以内时，认为已经跨入下一段。
- `amap_qps`：高德请求限流。普通 Key 建议不超过 3 次/秒，默认 2.5；设为 0 表示不节流。
- `include_polyline`：是否返回高德路径 polyline。只需要 ETA 时建议关闭。

## 输出字段解释

返回结构：

```python
{
    "ok": True,
    "provider": "amap",
    "enabled": True,
    "order_id": "O1001",
    "vehicle_id": "V001",
    "state": "waiting",
    "active_eta_kind": "pickup",
    "is_picked_up": False,
    "pickup_eta": {...},
    "dropoff_eta": {...},
}
```

单个 ETA 结构：

```python
{
    "kind": "pickup",
    "active": True,
    "status": "ready",
    "is_complete": True,
    "eta_seconds": 186,
    "distance_m": 2300,
    "origin_kind": "vehicle_position",
    "current_segment_index": 1,
    "total_segments": 5,
    "requested_segments": 5,
    "required_stops": [
        {"type": "vehicle_position", "order_id": None, "point": {...}, "waypoint_index": 0},
        {"type": "P", "order_id": "A", "point": {...}, "waypoint_index": 5}
    ],
    "route_match_status": "ok",
    "suspicious_segment_count": 0,
    "max_amap_to_astar_distance_ratio": 1.08,
    "waypoints": [
        {"lon": 113.300000, "lat": 23.100000},
        {"lon": 113.300500, "lat": 23.100500}
    ],
    "static_segments": [
        {
            "index": 0,
            "astar_distance_m": 420.5,
            "shape_waypoint_count": 2,
            "amap_to_astar_distance_ratio": 1.08
        }
    ],
    "formula": {
        "dynamic_sec": 36,
        "dynamic_source": "live",
        "following_static_sec": 150,
        "eta_seconds": 186,
        "text": "eta_seconds = dynamic_sec + following_static_sec",
    },
}
```

`origin_kind` 用来区分 ETA 起点：

- `vehicle_position`：从当前车辆 GPS 出发。
- `pickup_point`：从该订单 P 点出发，常见于未上车订单的预计送达 ETA。
- `completed`：该阶段已完成。

`status` 含义：

- `ready`：所有需要的分段都拿到高德结果。
- `partial`：拿到部分分段，`eta_seconds` 是当前可用的临时总和。
- `loading`：还没有可用分段结果。
- `error`：高德调用失败且当前没有可用 ETA。
- `disabled`：没有 API Key。
- `not_available`：订单状态或路线数据不足。
- `completed`：接驾阶段已完成。

## 路线变化如何处理

路线变化时，调用方只要做两件事：

1. 重新传新的 `planned_route`，里面的 `path` 是新 A* 路线。
2. 更换 `route_version`，例如从 `V001-route-17` 改成 `V001-route-18`。

函数检测到版本变化后，会清掉该车该订单旧分段，基于新线路重新分段，然后重新刷新高德静态 ETA。当前活动段仍然会用最新车辆位置调高德。
