# amap_eta_correct.py 使用说明

`amap_eta_correct.py` 是一个独立的 ETA 纠偏模块。它不负责派单、不负责 A* 寻路，只消费上游调度算法已经算好的车辆剩余 A* 轨迹，然后完成：

1. 按 O/D 接送顺序拆成整车相邻停靠段。
2. 调用高德 `v4/grasproad/driving` 做轨迹纠偏。
3. 用纠偏后的轨迹调用高德 `v5/direction/driving` 预测分段 ETA。
4. 按车辆段前缀和输出每个订单的接驾 ETA 和送达 ETA。

当前保底机制不触发：`fallbackDurationSec` 只作为调试字段。只要某段纠偏失败或高德 ETA 失败，该段 `chosenDurationSec` 为 `null`，后续乘客 ETA 也会保持 `null`。

## 推荐输入

推荐上游直接传已分段的 `segments`。每一段表示“当前车位或上一停靠点 -> 下一个 O/D 停靠点”的 A* 轨迹。

```python
payload = {
    "vehicleId": "bus-001",
    "routeVersion": 12,
    "speedMps": 16.6667,
    "vehiclePosition": {"lon": 113.400616, "lat": 23.058379},
    "segments": [
        {
            "index": 0,
            "startNodeId": "current",
            "endNodeId": "node-A-o",
            "endStep": {"type": "O", "orderId": 1001},
            "points": [
                {"lon": 113.400616, "lat": 23.058379},
                {"lon": 113.401000, "lat": 23.058500},
                {"lon": 113.403829, "lat": 23.056820}
            ]
        },
        {
            "index": 1,
            "startNodeId": "node-A-o",
            "endNodeId": "node-A-d",
            "endStep": {"type": "D", "orderId": 1001},
            "points": [
                {"lon": 113.403829, "lat": 23.056820},
                {"lon": 113.404000, "lat": 23.055100},
                {"lon": 113.404325, "lat": 23.051954}
            ]
        }
    ]
}
```

字段说明：

- `vehicleId`: 车辆 ID，原样返回。
- `routeVersion`: 路线版本号，原样返回；建议上游每次路线变化或 5 秒刷新时递增。
- `speedMps`: A* 对照耗时使用的速度，只用于输出 `fallbackDurationSec`，不参与 ETA 采用。
- `vehiclePosition`: 当前车辆经纬度。默认会替换第一个 segment 的第一个点，适合 5 秒刷新时传实时位置。
- `segments[].endStep.type`: `O` 表示上车点/起点，`D` 表示下车点/终点；历史 `P` 输入会被兼容归一为 `O`。
- `segments[].endStep.orderId`: 订单 ID，可以是数字或字符串。
- `segments[].points`: 该段 A* 轨迹点，至少 2 个点，坐标为 GCJ-02 经纬度。
- `segments[].aStarDistanceM`: 可选；不传时模块会按经纬度计算该段距离。

## 同步调用

```python
from amap_eta_correct import build_eta_pipeline_from_astar

result = build_eta_pipeline_from_astar(payload, api_key="your-amap-key")
print(result["passengerEtas"])
```

如果环境变量里已经配置了 `AMAP_API_KEY`，可以不传 `api_key`：

```bash
export AMAP_API_KEY="your-amap-key"
```

## 异步调用

```python
import asyncio
from amap_eta_correct import build_eta_pipeline_from_astar_async

async def main():
    result = await build_eta_pipeline_from_astar_async(payload, api_key="your-amap-key")
    print(result["passengerEtas"])

asyncio.run(main())
```

如果服务端本身已经在 async 框架里，例如 FastAPI、aiohttp，直接 `await build_eta_pipeline_from_astar_async(...)` 即可。

## 复用高德客户端

高频调用时建议复用 `AmapEtaCorrectClient`，这样纠偏和驾车 ETA 的缓存可以复用。

```python
from amap_eta_correct import AmapEtaCorrectClient, build_eta_pipeline_from_astar

amap = AmapEtaCorrectClient(api_key="your-amap-key", timeout_sec=6.0)

result1 = build_eta_pipeline_from_astar(payload1, amap=amap)
result2 = build_eta_pipeline_from_astar(payload2, amap=amap)
```

异步同理：

```python
from amap_eta_correct import AmapEtaCorrectClient, build_eta_pipeline_from_astar_async

amap = AmapEtaCorrectClient(api_key="your-amap-key")
result = await build_eta_pipeline_from_astar_async(payload, amap=amap)
```

## 多车调用

多车入口会逐车复用同一个高德客户端，返回每辆车各自的 pipeline。

```python
from amap_eta_correct import build_fleet_eta_pipelines_from_astar

result = build_fleet_eta_pipelines_from_astar({
    "routeVersion": 20,
    "speedMps": 16.6667,
    "vehicles": [
        {
            "vehicleId": "bus-001",
            "vehiclePosition": {"lon": 113.400616, "lat": 23.058379},
            "segments": [...]
        },
        {
            "vehicleId": "bus-002",
            "vehiclePosition": {"lon": 113.365900, "lat": 23.040212},
            "segments": [...]
        }
    ]
})
```

返回结构：

```python
{
    "ok": True,
    "pipelineKind": "amap_eta_correct_fleet",
    "vehicleCount": 2,
    "vehicles": [
        {"vehicleId": "bus-001", "passengerEtas": [...]},
        {"vehicleId": "bus-002", "passengerEtas": [...]}
    ]
}
```

## 可选输入：pathQueue

如果上游的数据结构类似 `demo_v3.html` 的 `pathQueue`，也可以直接传。`action` 存在的位置会被当成 O/D 停靠点。

```python
payload = {
    "vehicleId": "bus-001",
    "vehiclePosition": {"lon": 113.400616, "lat": 23.058379, "id": "current"},
    "pathQueue": [
        {"node": {"id": "n1", "lon": 113.401000, "lat": 23.058500}},
        {
            "node": {"id": "node-A-o", "lon": 113.403829, "lat": 23.056820},
            "action": {"type": "O", "orderId": 1001}
        },
        {"node": {"id": "n2", "lon": 113.404000, "lat": 23.055100}},
        {
            "node": {"id": "node-A-d", "lon": 113.404325, "lat": 23.051954},
            "action": {"type": "D", "orderId": 1001}
        }
    ]
}
```

## 可选输入：整条 A* path + stopSequence

如果上游只有一条完整 A* 轨迹和接送顺序，可以传：

```python
payload = {
    "vehicleId": "bus-001",
    "vehiclePosition": {"lon": 113.400616, "lat": 23.058379},
    "aStarPath": [
        {"id": "n0", "lon": 113.400616, "lat": 23.058379},
        {"id": "n1", "lon": 113.401000, "lat": 23.058500},
        {"id": "node-A-o", "lon": 113.403829, "lat": 23.056820},
        {"id": "n2", "lon": 113.404000, "lat": 23.055100},
        {"id": "node-A-d", "lon": 113.404325, "lat": 23.051954}
    ],
    "stopSequence": [
        {"type": "O", "orderId": 1001, "nodeId": "node-A-o"},
        {"type": "D", "orderId": 1001, "nodeId": "node-A-d"}
    ]
}
```

`stopSequence` 也支持 `pathIndex`，如果能给出停靠点在 `aStarPath` 里的下标，切段更确定：

```python
"stopSequence": [
    {"type": "O", "orderId": 1001, "pathIndex": 2},
    {"type": "D", "orderId": 1001, "pathIndex": 4}
]
```

## 输出结构

单车入口返回：

```python
{
    "ok": True,
    "pipelineKind": "amap_eta_correct",
    "vehicleId": "bus-001",
    "routeVersion": 12,
    "amapEnabled": True,
    "segmentCount": 2,
    "segments": [...],
    "vehiclePolyline": [...],
    "segmentEndOffsets": [...],
    "passengerEtas": [
        {
            "orderId": 1001,
            "pickupEtaSec": 180.0,
            "dropoffEtaSec": 520.0
        }
    ],
    "totalChosenDurationSec": 520.0,
    "totalMatchedDistanceM": 2400.0
}
```

重要字段：

- `segments[].aStarPolyline`: 输入的原始 A* 轨迹段。
- `segments[].matchedPolyline`: 高德纠偏后的轨迹；纠偏失败时为空。
- `segments[].amapPolyline`: 高德驾车规划返回的路线形状。
- `segments[].grasp.ok`: 该段纠偏是否成功。
- `segments[].amapEta.ok`: 该段 ETA 是否成功。
- `segments[].chosenDurationSec`: 最终采用的段耗时；只采用高德 ETA，失败时为 `null`。
- `segments[].chosenSource`: `amap`、`amap_congested` 或 `amap_unavailable`。
- `segments[].endEtaFromNowSec`: 从当前车位到该段终点的前缀 ETA。
- `passengerEtas[].pickupEtaSec`: 从当前车位到该订单 O 点的 ETA。
- `passengerEtas[].dropoffEtaSec`: 从当前车位到该订单 D 点的 ETA。

## 离线验证

设置 `AMAP_DISABLE=1` 可以验证切段和输出结构，但不会得到有效 ETA：

```bash
AMAP_DISABLE=1 python3 your_test.py
```

此时 `amapEnabled=False`，`chosenDurationSec`、`pickupEtaSec`、`dropoffEtaSec` 会是 `null`。这符合当前“不触发保底 ETA”的规则。

## 启动 demo_v4 页面  --- 注意这个只是本机测试，不需要看下面的内容！！！

`demo_v4.html` 是从 `demo_v3.html` 复制出来的前端验证页。它保留浏览器内的调度、接单、A* 和车辆运动逻辑，但 ETA 请求改为调用 `amap_eta_correct.py` 服务：

```bash
python3 amap_eta_correct.py --host 127.0.0.1 --port 8767
```

打开：

```text
http://127.0.0.1:8767/demo_v4.html
```

页面会调用：

```text
POST /eta_pipeline_from_astar_v4
```

该接口内部直接调用：

```python
build_eta_pipeline_from_astar(payload, amap=HTTP_AMAP)
```

如果要只验证 HTTP 结构、不真实访问高德：

```bash
AMAP_DISABLE=1 python3 amap_eta_correct.py --host 127.0.0.1 --port 8767
```

离线模式下页面能看到请求成功和订单级 `passengerEtas` 结构，但接驾/送达 ETA 会是 `null`。
