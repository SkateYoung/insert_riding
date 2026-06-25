# 前端接口对接文档

本文档面向前端调用方，描述当前 Flask 后端暴露的 HTTP JSON 接口。接口定义以 `api/routes.py` 当前实现为准。

## 1. 接入总则

### 1.1 服务地址

本地默认地址：

```text
http://localhost:5000
```

生产/联调环境地址由部署方提供。

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
| 车辆 | GET | `/fleet` | 查询车队列表信息 |
| 车辆 | GET | `/fleet/<vehicle_id>` | 查询单车信息 |
| 车辆 | POST | `/fleet/<vehicle_id>/path` | GPS 上报并刷新车辆后续路径 |
| 车辆 | POST | `/fleet/<vehicle_id>/rest` | 司机端请求休息/收车 |
| 系统 | GET  | `/status`                     | 获取系统全量状态           |

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
| `id` | string/null | 路点 ID |
| `lon` | number | 经度 |
| `lat` | number | 纬度 |
| `name` | string/null | 点名称 |
| `zone` | string/number/null | 分区 |

### 3.2 Vehicle车辆信息

由 `/fleet`、`/fleet/<vehicle_id>` 返回。（`/fleet`返回整个车队的车辆信息，`/fleet/<vehicle_id>`返回单个车辆信息）

```json
{
    "can_accept_order": true,		# 车辆是否可以接单
    "capacity": 10,					# 车辆目前容量
    "color": "#10b981",
    "desired_rest_time": null,		
    "desired_rest_time_text": null,
    "driver_id": "700045866645051565",	# 司机id号（后续也可以用身份证号代替）
    "driver_no": "6800A145",			# 司机工号
    "driving_time": 0.0,
    "gps": {						# 车辆上传的GPS信息
        "lat": 23.058379377458202,
        "lon": 113.40061589134783
    },
    "id": "巴士-绿色01",
    "idle_forecast": {				# 空车预测热点信息
        "assigned_hotspot_count": 3,
        "assignment_rank": 1,
        "assignment_strategy": "demand_first_dispersion",
        "forecast_end_time": "2026-06-18 13:30:00",
        "forecast_generated_at": 1781759533.104466,
        "forecast_generated_at_text": "2026-06-18 13:12:13",
        "forecast_start_time": "2026-06-18 13:15:00",
        "horizon_min": 15,
        "metrics": [],
        "pred_count": 1
    },
    "idle_target": {				# 空车预测热点位置信息
        "lat": 23.05579616,
        "lon": 113.40506673,
        "node_id": "113.404991_23.055733",
        "node_lat": 23.055732784329244,
        "node_lon": 113.40499086804854,
        "node_name": "普通路点 113.404991_23.055733",
        "snap_distance_to_node": 10.483536685764294
    },
    "idle_target_eta_error": null,
    "idle_target_eta_seconds": 292.0,
    "idle_target_eta_status": "ready",
    "idle_target_eta_time": 1781759843.54087,
    "idle_target_eta_time_text": "2026-06-18 13:17:23",  # 空车预测ETA时间
    "is_rest_requested": false,
    "is_resting": false,
    "last_node": "113.400616_23.058379",
    "next_node": "113.400616_23.058379",
    "on_board_count": 0,   # 车上乘客数量
    "on_board_orders": [],  # 已经上车的订单
    "planned_route": [   # 车辆任务简要信息
        {
            "node_name": "大学城南门",
            "request_id": "REQ-1781761465166-1-68790",
            "type": "O"
        },
        {
            "node_name": "体育馆南门",
            "request_id": "REQ-1781761465166-1-68790",
            "type": "D"
        }
    ],
    "planned_route_grasp_error": null,
    "planned_route_grasp_route_version": "巴士-绿色01|IDLE:113.404991_23.055733:None",
    "planned_route_grasp_status": "ready",
    "planned_route_grasped_point": [		# 用于高德导航的路径点（只需要读lat和lon就可以了）
        {
            "distance_to_gps": 0.13862600199786357,
            "id": "vehicle_gps",
            "is_grasp_projection": true,
            "lat": 23.058379932233322,
            "lon": 113.40061467795104
        },
        {
            "lat": 23.057915555555553,
            "lon": 113.40036388888888
        } ...
],
    "planned_route_point": [ ],  # 这个是算法端原始的路径点，可以不用管
    "planned_route_segment_grasped_point": [     # 根据车辆OD队列分割的高德导航路径点（只需要看points、request_id、target_node三个参数）
       {
            "aStarDistanceM": 2475.389976505058,
            "distance": 2475.389976505058,
            "endNodeId": "113.409132_23.060574",
            "endStep": {
                "orderId": "REQ-1781761465166-1-68790",
                "type": "O"
            },
            "grasp": {
                "distance_m": 2448.0,
                "error": null,
                "ok": true,
                "request_points": 94,
                "trimmed_from_previous": true
            },
            "index": 0,
            "points": [				# 用于高德导航的路径点
                {
                    "lat": 23.058379932233322,
                    "lon": 113.40061467795104
                } ...
            ],
            "request_id": "REQ-1781761465166-1-68790",  # 订单id号
            "source": "grasproad_trimmed_trimmed",
            "startNodeId": "113.400616_23.058379|113.400616_23.058379@0.000000",
            "target_node": {		# 目标点信息（O点或D点）
                "id": "113.409132_23.060574",
                "lat": 23.060573669207415,
                "lon": 113.40913197660784,
                "name": "大学城南门",
                "zone": 3
            },
            "type": "O"			# 目标类型（O点或D点）
        },
       {
            "aStarDistanceM": 1918.2684276721493,
            "distance": 1918.2684276721493,
            "endNodeId": "113.409085_23.054287",
            "endStep": {
                "orderId": "REQ-1781761465166-1-68790",
                "type": "D"
            },
            "grasp": {
                "distance_m": 1902.0,
                "error": null,
                "ok": true,
                "request_points": 62,
                "trimmed_from_previous": true
            },
            "index": 1,
            "points": [
                {
                    "lat": 23.060531993113823,
                    "lon": 113.40909251228433
                } ...
            ],
            "request_id": "REQ-1781761465166-1-68790",
            "source": "grasproad_trimmed_trimmed",
            "startNodeId": "113.409132_23.060574",
            "target_node": {
                "id": "113.409085_23.054287",
                "lat": 23.054286591851778,
                "lon": 113.40908505442682,
                "name": "体育馆南门",
                "zone": 3
            },
            "type": "D"
        }
    ],
    "plate_no": "粤A00001",       # 车牌号
    "progress": 0.0,
    "rest_duration": 1200,
    "rest_duration_minutes": 20.0,
    "rest_started_time": null,
    "rest_started_time_text": null,   
    "rest_status": "operating",		  # 车辆状态英文表示
    "rest_status_text": "运营中",		# 车辆状态中文表示
    "rest_timer": 0.0,
    "time": 1781759552.0,
    "time_text": "2026-06-18 13:12:32",
    "vehicle_id": "72057594546143661",
    "zone": 3					# 车辆所在区域
}
```

### 3.3 路径更新

由 `/fleet/<vehicle_id>/path` 返回。

```json
{
    "events": [],
    "gps": {    # 车辆的GPS信息
        "lat": 23.058200500000055,
        "lon": 113.3998150000001
    },
    "orders": {	  # 车辆已接的订单
        "on_board": [], 	# 已上车乘客的订单
        "remaining": [
            {				# OD队列
                "request_id": "REQ-1781761465166-1-68790",
                "target_node": {
                    "id": "113.409132_23.060574",
                    "lat": 23.060573669207415,
                    "lon": 113.40913197660784,
                    "name": "大学城南门",
                    "zone": 3
                },
                "type": "O"
            },
            {
                "request_id": "REQ-1781761465166-1-68790",
                "target_node": {
                    "id": "113.409085_23.054287",
                    "lat": 23.054286591851778,
                    "lon": 113.40908505442682,
                    "name": "体育馆南门",
                    "zone": 3
                },
                "type": "D"
            }
        ]
    },
    "route": {		# 车辆规划的完整路线	
        "distance": 4323.3288480945885,
        "planned_step_count": 2,
        "points": [
            {
                "edge_u": "113.400616_23.058379",
                "edge_v": "113.400295_23.057820",
                "id": "113.400616_23.058379|113.400295_23.057820@0.859277",
                "is_projection": true,
                "lat": 23.057898922358376,
                "lon": 113.40033979285639,
                "name": "车辆当前位置",
                "progress": 0.8592765969912309,
                "zone": 3
            },
            ...
            {
                "id": "113.409085_23.054287",
                "lat": 23.054286591851778,
                "lon": 113.40908505442682,
                "name": "体育馆南门",
                "zone": 3
            }
        ],
        "segments": [		# 根据OD队列分割后的路线
            {
                "distance": 2405.0604204224396,
                "points": [
                    {
                        "edge_u": "113.400616_23.058379",
                        "edge_v": "113.400295_23.057820",
                        "id": "113.400616_23.058379|113.400295_23.057820@0.859277",
                        "is_projection": true,
                        "lat": 23.057898922358376,
                        "lon": 113.40033979285639,
                        "name": "车辆当前位置",
                        "progress": 0.8592765969912309,
                        "zone": 3
                    },
     		       ...
                    {
                        "id": "113.409132_23.060574",
                        "lat": 23.060573669207415,
                        "lon": 113.40913197660784,
                        "name": "大学城南门",
                        "zone": 3
                    }
                ],
                "request_id": "REQ-1781761465166-1-68790",    # 订单号
                "target": {
                    "id": "113.409132_23.060574",
                    "lat": 23.060573669207415,
                    "lon": 113.40913197660784,
                    "name": "大学城南门",
                    "zone": 3
                },
                "type": "O"
            },
            {
                "distance": 1918.2684276721493,
                "points": [
                    {
                        "id": "113.409132_23.060574",
                        "lat": 23.060573669207415,
                        "lon": 113.40913197660784,
                        "name": "大学城南门",
                        "zone": 3
                    },
				  ...
                    {
                        "id": "113.409085_23.054287",
                        "lat": 23.054286591851778,
                        "lon": 113.40908505442682,
                        "name": "体育馆南门",
                        "zone": 3
                    }
                ],
                "request_id": "REQ-1781761465166-1-68790",	 # 订单号
                "target": {
                    "id": "113.409085_23.054287",
                    "lat": 23.054286591851778,
                    "lon": 113.40908505442682,
                    "name": "体育馆南门",
                    "zone": 3
                },
                "type": "D"
            }
        ]
    },
'''  # 这一部分是算法内部所需字段，不需要管
    "snap": {
        "distance_to_gps": 63.30390822174122,
        "edge": {
            "u": "113.400616_23.058379",
            "v": "113.400295_23.057820"
        },
        "next_node": {
            "id": "113.400295_23.057820",
            "lat": 23.057820238408553,
            "lon": 113.40029457631096,
            "name": "普通路点 113.400295_23.057820",
            "zone": 3
        },
        "point": {
            "edge_u": "113.400616_23.058379",
            "edge_v": "113.400295_23.057820",
            "id": "113.400616_23.058379|113.400295_23.057820@0.859277",
            "is_projection": true,
            "lat": 23.057898922358376,
            "lon": 113.40033979285639,
            "name": "车辆当前位置",
            "progress": 0.8592765969912309,
            "zone": 3
        },
        "progress": 0.8592765969912309,
        "source": "planned_route"
    },
    "snapped_point": {
        "distance_to_gps": 63.30390822174122,
        "edge": {
            "u": "113.400616_23.058379",
            "v": "113.400295_23.057820"
        },
        "id": "113.400616_23.058379|113.400295_23.057820@0.859277",
        "lat": 23.057898922358376,
        "lon": 113.40033979285639,
        "name": "车辆当前位置",
        "next_node": {
            "id": "113.400295_23.057820",
            "lat": 23.057820238408553,
            "lon": 113.40029457631096,
            "name": "普通路点 113.400295_23.057820",
            "zone": 3
        },
        "progress": 0.8592765969912309,
        "snap_source": "planned_route",
        "zone": 3
    },
'''
    "vehicle": {	# 车辆信息
        "id": "巴士-绿色01"
    }
}
```

### 3.4 订单ETA信息

由 `/orders/<request_id>/eta` 返回。

```json
{
  "request_id": "order_1",			# 订单ID
  "status": "waiting",				# 订单状态
  "vehicle": {						# 车辆信息
    "id": "巴士-绿色01",
    "plate_no": "粤A00001"
  },
  "origin": {						# 订单O点
    "name": "上车点",
    "lon": 113.38,
    "lat": 23.04
  },
  "destination": {					# 订单D点
    "name": "目的地",
    "lon": 113.39,
    "lat": 23.05
  },
  "eta": {
    "provider": "amap",						
    "status": "ready",
    "updated_at": 1780800000,							# ETA更新时间戳
    "updated_at_text": "2026-06-07 12:00:00",			# ETA更新时间文本
    "estimated_arrival_time": 1780800300,				# 车辆的预计到达时间戳
    "estimated_arrival_time_text": "2026-06-07 12:05:00",	# 订单的预计到达时间文本
    "estimated_arrival_eta_seconds": 300,
    "estimated_dropoff_time": 1780801500,                 # 车辆的预计送时间戳
    "estimated_dropoff_time_text": "2026-06-07 12:25:00",	# 订单的预计送达时间文本
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
    "clock_interval_seconds": 1.0,
    "clock_last_dt": 1.0,
    "clock_running": true,
    "clock_tick_count": 12871,
    "eta_last_refresh_time_text": "2026-06-18 16:48:03",  # ETA更新时间文本（每5秒会进行订单的ETA更新）
    "eta_last_refresh_timestamp": 1781772483.0,		# ETA更新时间戳
    "eta_refresh_interval_seconds": 5.0,
    "eta_thread_running": true,
    "mode": "real_time",
    "route_grasp_async_enabled": true,
    "route_grasp_inflight_count": 0,
    "route_grasp_last_refresh_time_text": "2026-06-18 16:44:53",	# 高德纠偏时间文本
    "route_grasp_last_refresh_timestamp": 1781772293.058061,		# 高德纠偏时间戳
    "route_grasp_mode": "on_route_update_async",
    "route_grasp_thread_running": false,
    "time_text": "2026-06-18 16:48:05",			# 当前时间文本
    "timestamp": 1781772485.0,					# 当前时间戳
    "timezone": "Asia/Shanghai"
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
  "shp_path": "dxc_traffic_shp/dxc_rule.shp"   # 指定的路网文件
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
| --- | :-- |
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
  "pool_size": 1,   # 订单池中的订单数量
  "completed_orders_size": 0,  # 当前进程内已完成/已归档订单数
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
    },
      ...
  ]
}
```

### 4.6 GET `/orders/<request_id>/eta`

乘客端查询订单状态、车辆信息、预计接驾到达时间和预计送达时间。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `request_id` | string | 订单 ID |

成功响应：见 `3.4`的`订单ETA信息`。

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 400 | 系统未初始化 |
| 404 | 订单不存在 |

字段解释：

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

`fleet[]` 元素结构说明见`3.2`的`Vehicle车辆信息`。

前端建议：

- 调度大屏可 1-5 秒轮询。
- 地图页建议结合 `/fleet/<vehicle_id>/path` 绘制单车实时路径。

### 4.9 GET `/fleet/<vehicle_id>`

查询单辆车状态。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `vehicle_id` | string | 车辆业务 ID，注意 URL 编码中文 |

成功响应：见`3.2`的`Vehicle车辆信息`。

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

成功响应：见`3.3`的`路径更新`。

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

请求体为空的话，表示立即收车：

```json
{
    
}
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

### 4.15 GET `/pois`

获取所有合法上下客 POI兴趣点。

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

## 5. 前端典型流程

### 5.1 系统启动流程

1. 调用 `GET /health`查询后端健康。
2. 如果 `initialized=false`，调用 `POST /init`。
3. 调用 `GET /time` 校准后端业务时间。
4. 调用 `GET /pois` 和 `GET /fleet` 初始化页面数据。

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

### 5.5 司机休息流程

1. 司机点击立即休息：调用 `POST /fleet/<vehicle_id>/rest`，请求体 `{}`。
2. 司机预约休息：传 `desired_rest_time` 和可选 `rest_duration_minutes`。
3. 根据 `decision` 和 `rest_status_text` 展示状态。

## 6. 前端实现建议

### 6.1 轮询频率

| 数、据 | 推荐频率 |
| --- | --- |
| `/fleet/<vehicle_id>/path` | 1-5 秒，取决于 GPS 更新频率 |
| `/orders/<request_id>/eta` | 5-10 秒                     |
| `/orders/pool`             | 5 秒                        |

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

### 6.6 后端一些错误展示建议

| 场景 | 前端文案建议 |
| --- | --- |
| 系统未初始化 | 系统正在启动，请稍后重试 |
| 车辆不存在 | 车辆信息已变化，请刷新列表 |
| 订单不存在 | 未找到订单，请确认订单号 |
| 路径不可达 | 当前路线不可达，请调整任务或联系调度 |
| 已上车不可取消 | 乘客已上车，当前订单不可取消 |
| ETA disabled/error | ETA 暂不可用，请稍后刷新 |

## 运营禁区策略

### `GET /operation-restrictions/policies`

返回所有未软删除的禁区策略，以及当前生效策略。

### `POST /operation-restrictions/policies`

创建禁区策略。请求体示例：

```json
{
  "policy_code": "campus-block",
  "policy_name": "校园施工禁区",
  "description": "optional",
  "polygons": [
    {
      "name": "area-1",
      "points": [
        {"lon": 113.4001, "lat": 23.0501},
        {"lon": 113.4011, "lat": 23.0501},
        {"lon": 113.4011, "lat": 23.0511},
        {"lon": 113.4001, "lat": 23.0511}
      ]
    }
  ]
}
```

后端会校验高德 `avoidpolygons` 限制：最多 32 个 polygon、单个 polygon 最多 16 个顶点，且单个 polygon 面积不超过 81 平方公里。

策略名称 `policy_name` 在同一租户下必须唯一；策略编号 `policy_code` 允许重复。

### `GET /operation-restrictions/policies/<policy_name>`

返回单个禁区策略。

### `PUT /operation-restrictions/policies/<policy_name>`

更新单个禁区策略。请求体结构与创建接口一致，策略名称作为唯一标识，编辑已有策略时不允许修改名称。

### `DELETE /operation-restrictions/policies/<policy_name>`

软删除单个禁区策略；如果该策略当前生效，则同步清空当前策略。

### `GET /operation-restrictions/active`

返回当前全局生效的禁区策略。

### `POST /operation-restrictions/active`

选择当前全局生效策略，或关闭禁区限制：

```json
{"policy_code": "campus-block"}
```

```json
{"policy_code": null}
```

策略切换只影响后续新路线计算，不会主动重算已有车辆路线。

## 司机车辆管理

该组接口用于前端动态维护司机档案、车辆档案、车辆状态和车辆司机绑定。删除均为软删除。

### `GET /admin/driver-vehicle/options`

返回司机车辆管理表单所需枚举，以及当前司机和车辆列表：

```json
{
  "driver_employment_statuses": ["active", "inactive", "blocked"],
  "driver_work_statuses": ["off_duty", "listening", "serving", "resting"],
  "vehicle_operation_statuses": ["operating", "resting", "closing", "offline", "maintenance"],
  "vehicle_types": ["bus", "large_bus", "mid_bus", "small_bus"],
  "drivers": [],
  "vehicles": []
}
```

### `GET /admin/drivers`

查询未软删除的司机档案列表。

### `POST /admin/drivers`

创建司机档案。`driver_code` 为路径身份字段，创建后不可修改；`driver_no` 按数据库唯一约束检测，冲突返回 `409`。

```json
{
  "driver_code": "driver-001",
  "driver_no": "D001",
  "driver_name": "张三",
  "phone": "13800000000",
  "id_card_no": "",
  "license_no": "",
  "license_class": "A1",
  "license_expire_date": "2028-12-31",
  "service_city": "广州",
  "employment_status": "active",
  "work_status": "off_duty",
  "remark": ""
}
```

### `GET /admin/drivers/<driver_code>`

查询单个司机档案。

### `PUT /admin/drivers/<driver_code>`

更新司机档案。`driver_code` 以路径为准，请求体中的 `driver_code` 会被忽略。

### `DELETE /admin/drivers/<driver_code>`

软删除司机档案；如果司机仍被车辆绑定，返回 `409`。

### `GET /admin/vehicles`

查询未软删除的车辆档案列表。

### `POST /admin/vehicles`

创建车辆档案。`vehicle_code` 为路径身份字段，创建后不可修改；`plate_no` 按数据库唯一约束检测，冲突返回 `409`。

```json
{
  "vehicle_code": "bus-001",
  "plate_no": "粤A00001",
  "vehicle_type": "bus",
  "seat_count": 10,
  "max_load_count": 10,
  "vehicle_color": "#64748b",
  "vehicle_model": "EV-BUS",
  "operation_status": "operating",
  "operation_mode": "dynamic_bus",
  "current_driver_code": "driver-001",
  "initial_position": {"lon": 113.4001, "lat": 23.0501},
  "remark": ""
}
```

新增或激活为 `operating`、`resting`、`closing` 时必须提供 `initial_position`，或车辆已有运行位置。后端会吸附到最近路网节点，并返回 `snap.node` 和 `snap.snap_distance_m`。

### `GET /admin/vehicles/<vehicle_code>`

查询单个车辆档案。

### `PUT /admin/vehicles/<vehicle_code>`

更新车辆档案并同步运行态车队。

### `DELETE /admin/vehicles/<vehicle_code>`

软删除车辆档案；如果车辆仍有 `on_board_orders` 或 `planned_route`，返回 `409`。

### `POST /admin/vehicles/<vehicle_code>/status`

更新车辆运营状态：

```json
{
  "operation_status": "offline"
}
```

状态规则：
- `operating`：加入或更新运行车队，可参与派单。
- `resting`：保留展示，但不接新单。
- `closing`：停止接新单，允许完成已有任务。
- `offline` / `maintenance`：无任务时从运行车队移除；有未完成任务时返回 `409`。

### `POST /admin/vehicles/<vehicle_code>/bind-driver`

绑定或解绑车辆司机：

```json
{"driver_code": "driver-001"}
```

```json
{"driver_code": null}
```
