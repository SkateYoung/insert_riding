# 前端接口对接文档

本文档面向 Web 前端、地图前端、乘客端和司机端调用方，描述当前 Flask 后端暴露的 HTTP JSON 接口。接口定义以 `api/routes.py` 当前实现为准。

## 1. 接入总则

### 1.1 服务地址

本地默认地址：

```text
http://localhost:5000
```

生产/联调环境地址由部署方提供，前端应通过环境变量或构建配置注入 `BASE_API_URL`，避免在代码中写死。

### 1.2 协议约定

| 项 | 约定 |
| --- | --- |
| 协议 | HTTP |
| 请求体 | JSON |
| 响应体 | JSON |
| 字符集 | UTF-8 |
| 时间时区 | Asia/Shanghai |
| 坐标字段 | `lon` 经度，`lat` 纬度 |
| 坐标顺序 | 所有接口均为 `lon, lat` |
| CORS | 后端允许跨域访问 |
| 认证 | 当前未启用鉴权 |

前端 POST 请求建议统一携带：

```http
Content-Type: application/json
Accept: application/json
```

### 1.3 通用错误格式

多数业务错误返回：

```json
{
  "error": "错误原因"
}
```

部分初始化/导出类接口返回：

```json
{
  "status": "error",
  "message": "错误原因"
}
```

### 1.4 常用 HTTP 状态码

| 状态码 | 含义 | 前端处理建议 |
| --- | --- | --- |
| 200 | 请求成功 | 正常读取响应 |
| 400 | 请求参数错误或系统未初始化 | 提示用户或触发初始化 |
| 404 | 资源不存在，如车辆/订单不存在 | 展示空状态或刷新列表 |
| 409 | 当前业务状态冲突，如订单已上车不可取消、路径不可达 | 展示业务冲突提示 |
| 500 | 服务端异常 | 展示系统错误并记录日志 |

### 1.5 时间字段约定

后端同时返回数值时间戳和文本时间。

| 字段类型 | 示例 | 说明 |
| --- | --- | --- |
| Unix 秒级时间戳 | `1780800000.0` | 适合排序、倒计时、差值计算 |
| 文本时间 | `"2026-06-07 12:00:00"` | 适合直接展示 |

前端展示优先使用后端提供的 `*_text` 字段；如需倒计时，使用时间戳字段。

## 2. 接口目录

| 模块 | 方法 | 路径 | 用途 |
| --- | --- | --- | --- |
| 系统 | GET | `/health` | 健康检查 |
| 系统 | GET | `/time` | 获取统一业务时间 |
| 系统 | POST | `/init` | 初始化路网和车队 |
| 订单 | POST | `/order` | 创建乘客订单 |
| 订单 | GET | `/orders/pool` | 查询待匹配订单池 |
| 订单 | GET | `/orders/<request_id>/eta` | 乘客端查询订单 ETA |
| 订单 | POST | `/orders/<request_id>/cancel` | 乘客端取消未上车订单 |
| 车辆 | GET | `/fleet` | 查询车队列表 |
| 车辆 | GET | `/fleet/<vehicle_id>` | 查询单车状态 |
| 车辆 | POST | `/fleet/<vehicle_id>/path` | GPS 上报并刷新车辆后续路径 |
| 车辆 | POST | `/fleet/<vehicle_id>/rest` | 司机端请求休息/收车 |
| 仿真 | POST | `/tick` | 手动推进运行状态 |
| 系统 | GET | `/status` | 获取系统全量状态 |
| 地图 | POST | `/export` | 导出前端可视化数据文件 |
| 地图 | GET | `/pois` | 获取 POI 上下客点 |
| 地图 | GET | `/map/road-network` | 获取路网节点、边、边界 |

## 3. 公共数据模型

### 3.1 Point

```json
{
  "id": "node_1",
  "lon": 113.38,
  "lat": 23.04,
  "name": "站点名称",
  "zone": "A"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string/null | 点 ID |
| `lon` | number | 经度 |
| `lat` | number | 纬度 |
| `name` | string/null | 点名称 |
| `zone` | string/number/null | 分区 |

### 3.2 Vehicle

由 `/fleet`、`/fleet/<vehicle_id>`、`/tick`、`/status` 返回。

```json
{
  "id": "巴士-绿色01",
  "color": "#10b981",
  "zone": "A",
  "capacity": 10,
  "driver_id": "700045866645051565",
  "driver_no": "6800A145",
  "vehicle_id": "72057594546143661",
  "plate_no": "粤A00001",
  "time": 1780800000.0,
  "time_text": "2026-06-07 12:00:00",
  "on_board_count": 2,
  "on_board_orders": ["order_1"],
  "gps": {
    "lon": 113.38,
    "lat": 23.04
  },
  "idle_target": null,
  "idle_forecast": null,
  "planned_route": [
    {
      "type": "O",
      "request_id": "order_1",
      "node_name": "上车点"
    }
  ],
  "planned_route_point": [],
  "last_node": "node_a",
  "next_node": "node_b",
  "progress": 0.3,
  "driving_time": 120.0,
  "is_resting": false,
  "is_rest_requested": false,
  "rest_status": "operating",
  "rest_status_text": "运营中",
  "desired_rest_time": null,
  "desired_rest_time_text": null,
  "rest_duration": 1200,
  "rest_duration_minutes": 20,
  "rest_timer": 0,
  "rest_started_time": null,
  "rest_started_time_text": null,
  "can_accept_order": true
}
```

关键字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 车辆业务 ID，路径参数使用该值 |
| `gps` | object | 最近一次车辆 GPS |
| `planned_route` | array | 后续订单停靠点，`O` 表示上车点，`D` 表示下车点 |
| `planned_route_point` | array | 前端可绘制的后续轨迹点 |
| `last_node` / `next_node` | string | 车辆所在路网边端点 |
| `progress` | number | 在当前边上的进度，范围通常为 0-1 |
| `rest_status` | string | `operating`、`preparing_closure`、`closing`、`resting` |
| `can_accept_order` | boolean | 当前是否允许继续接单 |

### 3.3 PathUpdateResponse

由 `/fleet/<vehicle_id>/path` 返回。

```json
{
  "vehicle": {
    "id": "巴士-绿色01"
  },
  "gps": {
    "lon": 113.38,
    "lat": 23.04
  },
  "snap": {
    "point": {
      "id": "u|v@0.123456",
      "lon": 113.38,
      "lat": 23.04,
      "name": "车辆当前位置",
      "zone": "A",
      "edge_u": "u",
      "edge_v": "v",
      "progress": 0.123456,
      "is_projection": true
    },
    "edge": {
      "u": "u",
      "v": "v"
    },
    "progress": 0.123456,
    "distance_to_gps": 4.2,
    "source": "planned_route",
    "next_node": {
      "id": "v",
      "lon": 113.39,
      "lat": 23.05,
      "name": "节点名",
      "zone": "A"
    }
  },
  "route": {
    "points": [],
    "distance": 1234.5,
    "planned_step_count": 2,
    "segments": []
  },
  "events": [],
  "orders": {
    "on_board": ["order_1"],
    "remaining": []
  },
  "path": [],
  "snapped_point": {}
}
```

说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `gps` | object | 前端上报的原始 GPS |
| `snap` | object | GPS 吸附到路网后的结果 |
| `route.points` | array | 主轨迹点，前端画线优先使用 |
| `route.segments` | array | 按 O/D 目标拆分的路径段 |
| `events` | array | 本次 GPS 上报触发的上车/下车事件 |
| `orders.on_board` | array | 当前车上订单 ID |
| `orders.remaining` | array | 剩余计划步骤 |
| `path` | array | 兼容字段，等于 `route.points` |
| `snapped_point` | object | 兼容字段 |

`/fleet/<vehicle_id>/path` 不返回订单 ETA。订单 ETA 通过 `/orders/<request_id>/eta` 查询。

### 3.4 RouteSegment

```json
{
  "type": "O",
  "request_id": "order_1",
  "target": {
    "id": "node_1",
    "lon": 113.38,
    "lat": 23.04,
    "name": "上车点",
    "zone": "A"
  },
  "distance": 520.4,
  "points": []
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | `O` 上车点，`D` 下车点，`IDLE` 空车停靠 |
| `request_id` | string/null | 订单 ID；空车停靠时为 null |
| `target` | Point | 当前分段目标点 |
| `distance` | number | 分段路网距离，单位米 |
| `points` | array | 当前分段轨迹点 |
| `forecast` | object/null | 空车热点预测信息，仅特定场景出现 |

### 3.5 OrderEtaResponse

由 `/orders/<request_id>/eta` 返回。

```json
{
  "request_id": "order_1",
  "status": "waiting",
  "vehicle": {
    "id": "巴士-绿色01",
    "plate_no": "粤A00001"
  },
  "origin": {
    "name": "上车点",
    "lon": 113.38,
    "lat": 23.04
  },
  "destination": {
    "name": "目的地",
    "lon": 113.39,
    "lat": 23.05
  },
  "eta": {
    "provider": "amap",
    "status": "ready",
    "updated_at": 1780800000,
    "updated_at_text": "2026-06-07 12:00:00",
    "estimated_arrival_time": 1780800300,
    "estimated_arrival_time_text": "2026-06-07 12:05:00",
    "estimated_arrival_eta_seconds": 300,
    "estimated_dropoff_time": 1780801500,
    "estimated_dropoff_time_text": "2026-06-07 12:25:00",
    "estimated_dropoff_eta_seconds": 1500,
    "error": null
  }
}
```

订单状态：

| `status` | 含义 |
| --- | --- |
| `matching` | 订单仍在待匹配池，暂未派车 |
| `waiting` | 已派车，等待上车 |
| `riding` | 乘客已上车，前往目的地 |
| `completed` | 已完成 |
| `cancelled` | 已取消 |

ETA 状态：

| `eta.status` | 含义 | 前端展示建议 |
| --- | --- | --- |
| `ready` | ETA 完整可用 | 展示预计到达/送达时间 |
| `partial` | 部分分段可用 | 展示时间并标注“预估” |
| `loading` | 后台正在刷新 | 展示“计算中”或保留旧值 |
| `disabled` | 未配置高德 API Key | 展示“暂不可用” |
| `error` | 高德调用失败 | 展示“暂不可用”，可稍后重试 |
| `not_assigned` | 订单未派车 | 展示“等待派车” |
| `pending` | 已派车但 ETA 尚未刷新 | 展示“计算中” |
| `completed` | 已完成 | 展示实际完成时间 |
| `cancelled` | 已取消 | 展示取消状态 |

字段语义：

| 字段 | 说明 |
| --- | --- |
| `estimated_arrival_time` | 车辆预计到达上车点时间 |
| `estimated_arrival_eta_seconds` | 从 `updated_at` 到上车点的预计秒数 |
| `estimated_dropoff_time` | 乘客预计到达目的地时间 |
| `estimated_dropoff_eta_seconds` | 从 `updated_at` 到目的地的预计秒数 |

## 4. 接口详情

### 4.1 GET `/health`

健康检查。系统未初始化时也可调用。

响应示例：

```json
{
  "status": "ok",
  "initialized": true
}
```

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 固定为 `ok` |
| `initialized` | boolean | 系统是否已完成初始化 |

### 4.2 GET `/time`

获取后端统一业务时间和后台线程状态。

响应示例：

```json
{
  "mode": "real_time",
  "timezone": "Asia/Shanghai",
  "timestamp": 1780800000.0,
  "time_text": "2026-06-07 12:00:00",
  "clock_interval_seconds": 1.0,
  "clock_running": true,
  "clock_last_dt": 1.0,
  "clock_tick_count": 100,
  "eta_refresh_interval_seconds": 5.0,
  "eta_thread_running": true,
  "eta_last_refresh_timestamp": 1780800000.0,
  "eta_last_refresh_time_text": "2026-06-07 12:00:00"
}
```

前端建议：

- 页面初始化时调用一次，用于校准本地倒计时。
- 监控页可显示 `clock_running` 和 `eta_thread_running`。

### 4.3 POST `/init`

初始化路网、车队、后台匹配线程、真实时钟线程和订单 ETA 线程。

请求体：

```json
{
  "shp_path": "dxc_traffic_shp/dxc_rule.shp"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `shp_path` | string | 否 | 自定义路网 SHP 文件路径。不传时使用后端默认值 |

成功响应：

```json
{
  "status": "initialized",
  "nodes": 1000,
  "pois": 50,
  "edges": 2000,
  "system_time": {}
}
```

如果系统已经初始化：

```json
{
  "status": "already_initialized",
  "nodes": 1000,
  "pois": 50
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 初始化成功或已初始化 |
| 400 | SHP 文件不存在 |
| 500 | 初始化异常 |

### 4.4 POST `/order`

创建乘客订单并进入调度池。后端会把原始起终点坐标吸附到最近合法 POI。

请求体：

```json
{
  "request_id": "order_10001",
  "origin": {
    "lon": 113.38,
    "lat": 23.04
  },
  "destination": {
    "lon": 113.39,
    "lat": 23.05
  },
  "expected_pickup_time": {
    "earliest": "2026-06-07 12:05:00",
    "latest": "2026-06-07 12:20:00"
  },
  "passenger_count": 2
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 前端/业务侧生成的订单唯一 ID |
| `origin.lon` | number | 是 | 起点经度 |
| `origin.lat` | number | 是 | 起点纬度 |
| `destination.lon` | number | 是 | 终点经度 |
| `destination.lat` | number | 是 | 终点纬度 |
| `expected_pickup_time.earliest` | string | 是 | 期望最早上车时间 |
| `expected_pickup_time.latest` | string | 是 | 期望最晚上车时间 |
| `passenger_count` | integer | 是 | 乘客人数，必须大于 0 |

成功响应：

```json
{
  "status": "pooled",
  "request_id": "order_10001",
  "origin_node": "起点POI",
  "origin_coords": {
    "lon": 113.38,
    "lat": 23.04
  },
  "destination_node": "终点POI",
  "destination_coords": {
    "lon": 113.39,
    "lat": 23.05
  },
  "request_time": "2026-06-07 12:00:00",
  "expected_pickup_time": {
    "earliest": "2026-06-07 12:05:00",
    "latest": "2026-06-07 12:20:00"
  },
  "passenger_count": 2,
  "pool_size": 1
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 创建成功 |
| 400 | 未初始化、缺字段、时间格式错误、人数非法 |

前端建议：

- 创建成功后轮询 `/orders/<request_id>/eta` 获取派车状态和 ETA。
- 不要使用前端传入的 `request_time`；后端会统一生成。

### 4.5 GET `/orders/pool`

查询待匹配订单池。

响应示例：

```json
{
  "pool_size": 1,
  "completed_orders_size": 30,
  "orders": [
    {
      "request_id": "order_10001",
      "origin": "起点POI",
      "destination": "终点POI",
      "request_time": "2026-06-07 12:00:00",
      "expected_pickup_time": {
        "earliest": "2026-06-07 12:05:00",
        "latest": "2026-06-07 12:20:00"
      },
      "passenger_count": 2,
      "req_time": 1780800000.0
    }
  ]
}
```

前端建议：

- 调度大屏可按 3-5 秒轮询。
- 乘客端不建议直接依赖该接口判断自身订单状态，应使用 `/orders/<request_id>/eta`。

### 4.6 GET `/orders/<request_id>/eta`

乘客端查询订单状态、车辆信息、预计接驾到达时间和预计送达时间。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `request_id` | string | 订单 ID |

成功响应见 `OrderEtaResponse`。

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 400 | 系统未初始化 |
| 404 | 订单不存在 |

前端建议：

- 创建订单后每 3-5 秒轮询一次。
- 如果 `status=matching` 或 `eta.status=not_assigned`，展示“正在匹配车辆”。
- 如果 `eta.status=loading/pending`，展示“ETA 计算中”。
- 如果 `eta.status=ready/partial`，展示预计到达和预计送达时间。
- 如果 `status=completed/cancelled`，停止轮询。

### 4.7 POST `/orders/<request_id>/cancel`

乘客端取消未上车订单。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `request_id` | string | 订单 ID |

请求体：无。

成功响应，订单仍在待匹配池：

```json
{
  "status": "cancelled",
  "request_id": "order_10001",
  "source": "order_pool",
  "message": "订单仍在待匹配池中，已取消。"
}
```

成功响应，订单已派车但未上车：

```json
{
  "status": "cancelled",
  "request_id": "order_10001",
  "source": "vehicle_route",
  "vehicle_id": "巴士-绿色01",
  "planned_route": [],
  "planned_route_point": [],
  "path_result": {},
  "message": "订单已从车辆计划路径中移除，车辆轨迹已刷新。"
}
```

失败响应，订单已上车：

```json
{
  "status": "rejected",
  "code": "already_on_board",
  "request_id": "order_10001",
  "vehicle_id": "巴士-绿色01",
  "message": "乘客已上车，乘客端取消订单被拒绝。"
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 取消成功 |
| 404 | 订单不存在 |
| 409 | 订单已上车、已完成、已取消或状态不允许取消 |

前端建议：

- 仅在 `status=matching/waiting` 时展示取消按钮。
- 收到 409 时刷新订单状态并禁用取消按钮。

### 4.8 GET `/fleet`

查询全部车辆状态。

响应示例：

```json
{
  "fleet": []
}
```

`fleet[]` 元素结构见 `Vehicle`。

前端建议：

- 调度大屏可 1-5 秒轮询。
- 地图页建议结合 `/fleet/<vehicle_id>/path` 绘制单车实时路径。

### 4.9 GET `/fleet/<vehicle_id>`

查询单辆车状态。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `vehicle_id` | string | 车辆业务 ID，注意 URL 编码中文 |

成功响应：`Vehicle`。

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 400 | 系统未初始化 |
| 404 | 车辆不存在 |

### 4.10 POST `/fleet/<vehicle_id>/path`

车辆 GPS 上报并刷新车辆后续路网轨迹。该接口会执行路网吸附，并在车辆接近当前 O/D 点时触发上车或下车事件。

请求体：

```json
{
  "lon": 113.38,
  "lat": 23.04
}
```

兼容字段：

| 字段 | 说明 |
| --- | --- |
| `lon` / `lng` / `longitude` | 任一字段可作为经度 |
| `lat` / `latitude` | 任一字段可作为纬度 |

成功响应：`PathUpdateResponse`。

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 更新成功 |
| 400 | 未初始化、缺少坐标、坐标不是数字 |
| 404 | 车辆不存在 |
| 409 | 当前订单计划存在不可达路段 |

前端地图绘制建议：

- 车辆当前位置优先使用 `snap.point`，它是吸附到路网后的点。
- 主轨迹优先使用 `route.points`。
- 分段轨迹使用 `route.segments[].points`，可按 `type` 给 O/D 分段上色。
- 上下车弹窗或状态变更使用 `events`。
- `path` 和 `snapped_point` 是兼容字段，新代码优先读取 `route.points` 和 `snap.point`。

### 4.11 POST `/fleet/<vehicle_id>/rest`

司机端请求休息或预约休息。

请求体，立即收车：

```json
{}
```

请求体，预约休息：

```json
{
  "desired_rest_time": "2026-06-07 13:30:00",
  "rest_duration_minutes": 20
}
```

请求体，按相对秒数预约：

```json
{
  "desired_rest_time": 1800,
  "rest_duration_minutes": 20
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `desired_rest_time` | string/number/null | 否 | 为空表示马上收车；数字表示从当前后端时间起多少秒后休息；字符串按业务时间解析 |
| `rest_duration_minutes` | number | 否 | 休息时长，后端限制在 15-30 分钟 |

响应示例：

```json
{
  "vehicle_id": "巴士-绿色01",
  "decision": "close_now",
  "rest_status": "closing",
  "rest_status_text": "收车中",
  "estimated_finish_time": 1780803600.0,
  "estimated_finish_time_text": "2026-06-07 13:00:00",
  "estimated_finish_after_seconds": 3600,
  "vehicle": {}
}
```

`decision` 取值：

| 值 | 说明 |
| --- | --- |
| `close_now` | 立即停止接新单，完成当前任务后休息 |
| `already_resting` | 车辆已经在休息 |
| `prepare_closure` | 接近预约休息时间，进入收车准备 |
| `keep_operating_until_rest_time` | 当前仍可继续运营直到预约时间 |

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 请求成功 |
| 400 | 未初始化或参数格式错误 |
| 404 | 车辆不存在 |

### 4.12 POST `/tick`

手动刷新运行状态。当前实现忽略请求体里的 `dt`，按后端真实 elapsed seconds 推进。

请求体：

```json
{
  "dt": 0.1
}
```

响应示例：

```json
{
  "dt": 1.0,
  "system_time": {},
  "fleet": []
}
```

前端建议：

- 正常页面通常不需要调用，后台时钟线程会自动推进。
- 测试面板或调试工具可手动调用。

### 4.13 GET `/status`

获取系统全量状态快照。

响应示例：

```json
{
  "initialized": true,
  "system_time": {},
  "nodes_count": 1000,
  "pois_count": 50,
  "edges_count": 2000,
  "fleet": [],
  "order_pool_size": 1,
  "completed_orders": 30
}
```

前端建议：

- 管理端首页可使用该接口一次性加载系统状态。
- 高频车辆地图不建议只依赖 `/status`，应按需要调用 `/fleet` 或单车路径接口。

### 4.14 POST `/export`

导出前端可视化数据文件。

请求体：

```json
{
  "file_path": "map_data.js"
}
```

响应：

```json
{
  "status": "ok",
  "file": "map_data.js"
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 导出成功 |
| 400 | 系统未初始化 |
| 500 | 导出失败 |

### 4.15 GET `/pois`

获取所有合法上下客 POI。

响应示例：

```json
{
  "pois": [
    {
      "id": "poi_1",
      "name": "站点A",
      "lon": 113.38,
      "lat": 23.04,
      "zone": "A"
    }
  ]
}
```

前端建议：

- 订单创建页可用于起终点选择、地图点位展示。
- 若前端允许用户任意点选，后端仍会吸附到最近 POI。

### 4.16 GET `/map/road-network`

获取路网节点、道路边、POI ID 列表和地图边界。

响应示例：

```json
{
  "nodes": {
    "node_1": {
      "id": "node_1",
      "lon": 113.38,
      "lat": 23.04,
      "name": "节点A",
      "zone": "A",
      "is_poi": true
    }
  },
  "edges": [],
  "pois": ["node_1"],
  "bounds": {
    "min_lon": 113.1,
    "max_lon": 113.9,
    "min_lat": 22.9,
    "max_lat": 23.5
  }
}
```

前端建议：

- 地图底图或调试路网可使用该接口。
- 路网数据量可能较大，建议页面初始化时拉取一次并缓存。

## 5. 前端典型流程

### 5.1 系统启动流程

1. 调用 `GET /health`。
2. 如果 `initialized=false`，调用 `POST /init`。
3. 调用 `GET /time` 校准后端业务时间。
4. 调用 `GET /pois` 和 `GET /fleet` 初始化页面数据。
5. 地图页按需调用 `GET /map/road-network`。

### 5.2 乘客下单流程

1. 前端采集起点、终点、期望上车时间窗和乘客人数。
2. 调用 `POST /order` 创建订单。
3. 根据返回的 `request_id` 轮询 `GET /orders/<request_id>/eta`。
4. 当 `status=waiting/riding` 且 ETA 可用时展示预计到达和送达。
5. 当 `status=completed/cancelled` 时停止轮询。

### 5.3 乘客取消流程

1. 前端在 `matching/waiting` 状态展示取消按钮。
2. 调用 `POST /orders/<request_id>/cancel`。
3. 成功后展示取消成功并停止 ETA 轮询。
4. 如果返回 409，刷新 `/orders/<request_id>/eta` 并更新 UI 状态。

### 5.4 车辆地图流程

1. 调用 `GET /fleet` 获取车辆列表。
2. 选择车辆后周期性调用 `POST /fleet/<vehicle_id>/path` 上报 GPS。
3. 使用 `snap.point` 绘制车辆吸附位置。
4. 使用 `route.points` 绘制后续路线。
5. 使用 `route.segments` 展示按 O/D 拆分的任务段。
6. 使用 `events` 触发上车/下车 UI 变更。

### 5.5 司机休息流程

1. 司机点击立即休息：调用 `POST /fleet/<vehicle_id>/rest`，请求体 `{}`。
2. 司机预约休息：传 `desired_rest_time` 和可选 `rest_duration_minutes`。
3. 根据 `decision` 和 `rest_status_text` 展示状态。
4. 车辆进入 `closing/resting` 后前端应禁用继续接单相关操作。

## 6. 前端实现建议

### 6.1 轮询频率

| 数据 | 推荐频率 |
| --- | --- |
| `/fleet` | 3-5 秒 |
| `/fleet/<vehicle_id>/path` | 1-5 秒，取决于 GPS 更新频率 |
| `/orders/<request_id>/eta` | 3-5 秒 |
| `/orders/pool` | 5 秒 |
| `/status` | 5-10 秒 |
| `/pois` | 页面初始化一次 |
| `/map/road-network` | 页面初始化一次并缓存 |

### 6.2 URL 编码

车辆 ID 可能包含中文，如 `巴士-绿色01`。前端拼接 URL 时必须编码：

```js
const url = `/fleet/${encodeURIComponent(vehicleId)}`;
```

订单 ID 也建议统一编码：

```js
const url = `/orders/${encodeURIComponent(requestId)}/eta`;
```

### 6.3 坐标与地图

- 后端返回坐标字段均为 `lon/lat`。
- 前端高德地图通常使用 `[lon, lat]` 数组。
- `snap.point` 是吸附后的车辆位置，适合车辆 marker。
- `gps` 是原始上报位置，可用于调试。

### 6.4 ETA 配置说明

高德 ETA 由后端独立线程每 5 秒刷新。后端需要在启动前设置环境变量：

```powershell
$env:AMAP_API_KEY="你的高德Web服务Key"
python main.py
```

如果未配置 Key：

- 业务接口仍可正常运行。
- `/orders/<request_id>/eta` 中 `eta.status` 可能为 `disabled`。
- 前端应展示“ETA 暂不可用”，不要阻塞订单流程。

### 6.5 幂等和重复提交

当前 `/order` 没有显式重复 ID 校验。前端应保证 `request_id` 唯一，避免重复提交同一订单。

建议：

- 点击下单后立即禁用按钮，等待接口返回。
- 失败后允许重试，但重试时复用同一个 `request_id` 前需与后端确认策略。

### 6.6 错误展示建议

| 场景 | 前端文案建议 |
| --- | --- |
| 系统未初始化 | 系统正在启动，请稍后重试 |
| 车辆不存在 | 车辆信息已变化，请刷新列表 |
| 订单不存在 | 未找到订单，请确认订单号 |
| 路径不可达 | 当前路线不可达，请调整任务或联系调度 |
| 已上车不可取消 | 乘客已上车，当前订单不可取消 |
| ETA disabled/error | ETA 暂不可用，请稍后刷新 |

## 7. 接口兼容说明

### 7.1 路径接口兼容字段

`/fleet/<vehicle_id>/path` 当前保留：

- `path`: 等于 `route.points`
- `snapped_point`: 旧版吸附点字段

新前端应优先读取：

- `route.points`
- `route.segments`
- `snap.point`

### 7.2 不再推荐依赖的字段

前端不应依赖以下旧字段：

- 顶层 `planned_route_point`
- 顶层 `snapped_node`
- 顶层 `segments`

### 7.3 ETA 不在路径接口返回

订单 ETA 不通过 `/fleet/<vehicle_id>/path` 返回。请使用：

```http
GET /orders/<request_id>/eta
```

## 8. 最小 TypeScript 类型参考

```ts
export interface Point {
  id?: string | null;
  lon: number;
  lat: number;
  name?: string | null;
  zone?: string | number | null;
}

export interface Vehicle {
  id: string;
  color: string;
  zone: string | number;
  capacity: number;
  driver_id: string;
  driver_no: string;
  vehicle_id: string;
  plate_no: string;
  time: number;
  time_text: string;
  on_board_count: number;
  on_board_orders: string[];
  gps: { lon: number | null; lat: number | null };
  planned_route: Array<{
    type: "O" | "D";
    request_id: string;
    node_name: string;
  }>;
  planned_route_point: Point[];
  last_node: string;
  next_node: string;
  progress: number;
  rest_status: "operating" | "preparing_closure" | "closing" | "resting";
  rest_status_text: string;
  can_accept_order: boolean;
}

export interface PathUpdateResponse {
  vehicle: { id: string };
  gps: { lon: number; lat: number };
  snap: {
    point: Point & {
      edge_u?: string | null;
      edge_v?: string | null;
      progress?: number | null;
      is_projection: boolean;
    };
    edge: { u?: string; v?: string };
    progress?: number | null;
    distance_to_gps?: number | null;
    source?: string | null;
    next_node?: Point | null;
  };
  route: {
    points: Point[];
    distance: number;
    planned_step_count: number;
    segments: RouteSegment[];
  };
  events: Array<{
    action: "pickup" | "dropoff";
    type: "O" | "D";
    request_id: string;
    node: Point;
    distance_to_target?: number;
  }>;
  orders: {
    on_board: string[];
    remaining: Array<{
      type: "O" | "D";
      request_id: string;
      target_node: Point;
    }>;
  };
  path: Point[];
  snapped_point: Record<string, unknown>;
}

export interface RouteSegment {
  type: "O" | "D" | "IDLE";
  request_id: string | null;
  target: Point;
  distance: number;
  points: Point[];
  forecast?: Record<string, unknown>;
}

export interface OrderEtaResponse {
  request_id: string;
  status: "matching" | "waiting" | "riding" | "completed" | "cancelled";
  vehicle: null | {
    id: string;
    plate_no: string;
  };
  origin: {
    name: string | null;
    lon: number | null;
    lat: number | null;
  };
  destination: {
    name: string | null;
    lon: number | null;
    lat: number | null;
  };
  eta: {
    provider: "amap";
    status: string;
    updated_at: number | null;
    updated_at_text: string | null;
    estimated_arrival_time: number | null;
    estimated_arrival_time_text: string | null;
    estimated_arrival_eta_seconds: number | null;
    estimated_dropoff_time: number | null;
    estimated_dropoff_time_text: string | null;
    estimated_dropoff_eta_seconds: number | null;
    error: string | null;
  };
}
```

## 9. 联调检查清单

- 后端是否可访问 `GET /health`。
- 系统是否已初始化，`GET /health.initialized=true`。
- `GET /time.clock_running=true`。
- `GET /time.eta_thread_running=true`。
- 前端是否对中文 `vehicle_id` 做了 URL 编码。
- 前端是否使用 `lon/lat` 顺序调用地图。
- 订单创建后是否改用 `/orders/<request_id>/eta` 查询状态和 ETA。
- 路径绘制是否优先使用 `route.points` 和 `snap.point`。
- 未配置高德 Key 时，前端是否能正确展示 ETA 不可用状态。
