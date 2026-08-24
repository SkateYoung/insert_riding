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

### 1.5 错误日志

后端会把接口错误和算法内部异常写入本地 txt 文件，默认路径为：

```text
runtime_logs/error_YYYYMMDD.txt
```

记录范围：

- Flask 接口返回 `4xx/5xx` 时记录请求方法、路径、请求体和响应体摘要。
- 未捕获异常会记录完整 traceback。
- 订单池匹配、空车热点预测、ETA 刷新、高德路径规划、运营区初始化、车辆/站点加载和车辆路径推送等算法内部异常会记录业务上下文。

可选环境变量：

| 环境变量 | 说明 |
| --- | --- |
| `BUS_ERROR_LOG_DIR` / `ERROR_LOG_DIR` | 覆盖默认日志目录 |
| `BUS_ERROR_LOG_FILE` / `ERROR_LOG_FILE` | 覆盖默认日志文件完整路径 |

日志写入失败不会影响接口响应和算法线程运行。

### 1.6 时间字段约定

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
| 订单 | POST | `/orders/<request_id>/driver-push-confirmation` | 平台确认司机端是否收到派单 |
| 订单 | POST | `/admin/orders/query` | 服务端按条件查询订单数据库 |
| 调度 | GET/POST/PUT | `/admin/dispatch/matching-window-config` | 查看或更新远期订单匹配窗口配置 |
| 调度 | GET/POST/PUT | `/admin/dispatch/route-cost-config` | 查看或更新插单成本函数配置 |
| 通勤快线 | GET/POST | `/commute/lines` | 查询或创建通勤快线线路 |
| 通勤快线 | GET/PUT/DELETE | `/commute/lines/<line_code>` | 查询、更新或删除通勤快线线路 |
| 通勤快线 | PUT | `/commute/lines/<line_code>/stops` | 整体替换通勤快线固定站序 |
| 通勤快线 | POST | `/commute/vehicles/assign` | 绑定车辆到通勤快线线路 |
| 通勤快线 | POST | `/commute/orders` | 创建通勤快线订单 |
| 通勤快线 | GET | `/commute/orders/<request_id>` | 查询通勤快线订单 |
| 通勤快线 | POST | `/commute/orders/<request_id>/cancel` | 取消通勤快线订单 |
| 车辆 | GET | `/fleet` | 查询车队列表信息 |
| 车辆 | GET | `/fleet/<vehicle_id>` | 查询单车信息 |
| 车辆 | POST | `/fleet/<vehicle_id>/path` | GPS 上报并更新车辆吸附位置，不触发上下客或路线重规划 |
| 车辆 | POST | `/fleet/<vehicle_id>/boarding-events` | 司机端显式确认当前上车/下车步骤，动态巴士和通勤快线共用 |
| 车辆 | POST | `/fleet/<vehicle_id>/amap-route/replan` | 同步优先重规划单车高德驾车路线 |
| 车辆 | POST | `/fleet/<vehicle_id>/rest` | 司机端请求休息/收车 |
| 系统 | GET | `/status` | 获取系统全量状态 |
| 地图 | GET | `/pois` | 获取所有合法上下客 POI |
| 地图 | GET | `/map/road-network` | 按运营区获取路网节点和边 |
| 运营区域 | GET | `/admin/shp-files` | 查询 shp 目录下可用 SHP 文件路径 |
| 运营区域 | GET | `/admin/operation-areas` | 查询运营区列表 |
| 运营区域 | POST | `/admin/operation-areas` | 新增运营区 |
| 运营区域 | GET | `/admin/operation-areas/<area_id>` | 查询单个运营区 |
| 运营区域 | PUT | `/admin/operation-areas/<area_id>` | 更新单个运营区 |
| 运营区域 | DELETE | `/admin/operation-areas/<area_id>` | 软删除运营区 |
| 运营区域 | POST | `/admin/operation-areas/<area_id>/load-test` | 测试加载运营区 SHP |
| 运营禁区 | GET | `/operation-restrictions/policies` | 查询禁区策略列表 |
| 运营禁区 | POST | `/operation-restrictions/policies` | 创建禁区策略 |
| 运营禁区 | GET | `/operation-restrictions/policies/<policy_identity>` | 查询单个禁区策略 |
| 运营禁区 | PUT | `/operation-restrictions/policies/<policy_identity>` | 更新单个禁区策略 |
| 运营禁区 | DELETE | `/operation-restrictions/policies/<policy_identity>` | 软删除单个禁区策略 |
| 运营禁区 | GET | `/operation-restrictions/active` | 查询当前生效禁区策略 |
| 运营禁区 | POST | `/operation-restrictions/active` | 设置或关闭当前生效禁区策略 |
| 司机车辆管理 | GET | `/admin/driver-vehicle/options` | 获取司机车辆表单选项 |
| 司机车辆管理 | GET | `/admin/drivers` | 查询司机档案列表 |
| 司机车辆管理 | POST | `/admin/drivers` | 创建司机档案 |
| 司机车辆管理 | GET | `/admin/drivers/<driver_code>` | 查询单个司机档案 |
| 司机车辆管理 | PUT | `/admin/drivers/<driver_code>` | 更新司机档案 |
| 司机车辆管理 | DELETE | `/admin/drivers/<driver_code>` | 软删除司机档案 |
| 司机车辆管理 | GET | `/admin/vehicles` | 查询车辆档案列表 |
| 司机车辆管理 | POST | `/admin/vehicles` | 创建车辆档案 |
| 司机车辆管理 | GET | `/admin/vehicles/<vehicle_code>` | 查询单个车辆档案 |
| 司机车辆管理 | PUT | `/admin/vehicles/<vehicle_code>` | 更新车辆档案 |
| 司机车辆管理 | DELETE | `/admin/vehicles/<vehicle_code>` | 软删除车辆档案 |
| 司机车辆管理 | POST | `/admin/vehicles/<vehicle_code>/status` | 更新车辆运营状态 |
| 司机车辆管理 | POST | `/admin/vehicles/<vehicle_code>/bind-driver` | 绑定或解绑车辆司机 |

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
            "source": "driving_plan_trimmed",
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
            "source": "driving_plan_trimmed",
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

> 该接口只用于车辆 GPS 上报、位置吸附、运行态与 GPS 轨迹落库；不会自动触发上车/下车，不会重建 A* 路线，也不会触发高德驾车重规划。若车辆已有高德规划路线，后端优先把 GPS 投影到高德规划路线；没有高德路线时才退回路网/A* 路线吸附。

```json
{
    "events": [],   # /path 不再触发上下客事件，因此通常为空数组
    "gps": {    # 后端吸附后的车辆位置，前端车辆图标应使用该坐标
        "lat": 23.058200500000055,
        "lon": 113.3998150000001
    },
    "reported_gps": {   # 前端原始上报的 GPS 坐标
        "lat": 23.058260000000000,
        "lon": 113.3999000000000
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
        "source": "amap_grasped_route",  # 优先为高德规划路线吸附；无高德路线时可能为 planned_route/road_network
        "raw_point": {
            "lat": 23.058260000000000,
            "lon": 113.3999000000000
        }
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
        "snap_source": "amap_grasped_route",
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
| `matched` | 算法端已匹配车辆，等待平台确认司机端收到派单 |
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

多运营区版本中，初始化来源改为数据库 `map_operation_area`。后端会读取所有满足 `deleted=0`、`is_deleted=0`、`status='enabled'`、`audit_status='approved'`、`load_on_startup=1` 且 `shp_path` 非空的运营区，并为每个成功加载的运营区创建一个 `CityGraph`。旧请求体中的 `shp_path` 字段保留兼容，但当前会被忽略。

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
  "default_operation_area_code": null,
  "loaded_areas": [],
  "failed_areas": [],
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
  "default_operation_area_code": null,
  "loaded_areas": [],
  "nodes": 1000,
  "pois": 50
}
```

如果没有生效运营区：

```json
{
  "status": "no_operation_area",
  "message": "没有生效运营区，未初始化 SHP 路网。"
}
```

状态码：

| 状态码 | 场景 |
| --- | :-- |
| 200 | 初始化成功或已初始化 |
| 400 | 没有生效运营区，或所有运营区 SHP 加载失败 |
| 500 | 初始化异常 |

### 4.4 POST `/order`

创建普通动态巴士订单并进入调度池。起点和终点坐标必须精确匹配订单所属运营区 `map_poi` 表中的启用站点；接口不再把任意坐标吸附到最近 POI。

请求体：

```json
{
  "request_id": "order_10001",
  "operation_area_id": 10001,
  "passenger_phone": "13900000001",
  "passenger_id": "passenger_10001",
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
| `operation_area_id` | integer | 是 | 订单所属运营区业务 ID，对应 `map_operation_area.area_id`；不传时返回 `400` |
| `passenger_phone` | string | 是 | 乘客手机号 |
| `passenger_id` | string/null | 否 | 前端/业务系统乘客 ID；为空时不写入 |
| `origin.lon` | number | 是 | 起点站经度，按 8 位小数精确匹配当前运营区启用站点 |
| `origin.lat` | number | 是 | 起点站纬度，按 8 位小数精确匹配当前运营区启用站点 |
| `destination.lon` | number | 是 | 终点站经度，按 8 位小数精确匹配当前运营区启用站点 |
| `destination.lat` | number | 是 | 终点站纬度，按 8 位小数精确匹配当前运营区启用站点 |
| `expected_pickup_time.earliest` | string | 是 | 期望最早上车时间 |
| `expected_pickup_time.latest` | string | 是 | 期望最晚上车时间 |
| `passenger_count` | integer | 是 | 乘客人数，必须大于 0 |

成功响应：

```json
{
  "status": "pooled",   
  "request_id": "order_10001",
  "operation_area_code": "area_001",
  "passenger_phone": "13900000001",
  "passenger_id": "passenger_10001",
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
| 400 | 未初始化、缺字段、坐标不是有限数字或超出范围、手机号为空、时间格式错误、人数非法 |
| 404 | 起点或终点坐标未匹配到当前运营区的启用站点 |
| 409 | 起终点相同、坐标匹配多个站点，或站点尚未加载到运营区路网 |
| 503 | 数据库不可用，无法校验站点坐标 |

坐标相关错误码：

| 错误码 | 说明 |
| --- | --- |
| `station_coordinate_invalid` | 经纬度不是有限数字或超出合法范围 |
| `origin_station_not_found_by_coordinate` | 起点坐标未匹配到启用站点 |
| `destination_station_not_found_by_coordinate` | 终点坐标未匹配到启用站点 |
| `origin_station_coordinate_ambiguous` | 起点坐标匹配到多个启用站点 |
| `destination_station_coordinate_ambiguous` | 终点坐标匹配到多个启用站点 |
| `same_origin_destination` | 起点和终点为同一站点 |
| `origin_station_not_loaded` / `destination_station_not_loaded` | 数据库站点尚未加载到当前 A* 路网 |

前端建议：

- 创建成功后轮询 `/orders/<request_id>/eta` 获取派车状态和 ETA。
- 不要使用前端传入的 `request_time`；后端会统一生成。
- 起终点应直接使用 `GET /pois?operation_area_id=xxx` 返回的站点经纬度，不要传地图任意点击坐标。

### 4.4.1 POST `/admin/orders/query`

服务端按条件查询订单数据库。该接口直接读取 `bus_order`，不要求调度系统已初始化。

请求体：

```json
{
  "request_id": "order_10001",
  "passenger_phone": "13900000001",
  "status": "completed",
  "station_name": "体育中心",
  "driver_name": "张三",
  "plate_no": "粤A00001",
  "created_at": {
    "start": "2026-07-01 00:00:00",
    "end": "2026-07-05 23:59:59"
  },
  "limit": 500,
  "offset": 0
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 否 | 订单请求 ID，精确匹配 |
| `passenger_phone` | string | 否 | 乘客手机号，精确匹配 |
| `status` | string | 否 | 订单状态，精确匹配 |
| `station_name` | string | 否 | 站点名称，匹配起点名称或终点名称，模糊查询 |
| `driver_name` | string | 否 | 司机姓名，模糊查询 |
| `plate_no` | string | 否 | 车牌号，精确匹配 |
| `created_at.start` | string | 否 | 创建时间起始，包含边界 |
| `created_at.end` | string | 否 | 创建时间结束，包含边界 |
| `limit` | integer | 否 | 返回条数；不传时返回全部匹配数据 |
| `offset` | integer | 否 | 分页跳过条数，仅在传入 `limit` 时生效 |

说明：

- 所有条件均可省略；传多个条件时按 `AND` 联合查询。
- `passenger_id` 在订单创建时按业务乘客 ID 写入 `bus_order.passenger_code`，查询返回结果中也会包含该字段。

成功响应：

```json
{
  "count": 1,
  "orders": [
    {
      "id": 1,
      "request_id": "order_10001",
      "passenger_code": "passenger_10001",
      "passenger_phone": "13900000001",
      "status": "completed",
      "origin_name": "体育中心站",
      "destination_name": "珠江新城站",
      "assigned_plate_no": "粤A00001",
      "assigned_driver_name": "张三",
      "assigned_vehicle_code": "vehicle_001",
      "created_at": "2026-07-05 12:00:00"
    }
  ]
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 400 | 请求体格式错误、时间格式错误、分页参数非法 |
| 503 | 数据库未启用或 PyMySQL 不可用 |

### 4.4.2 GET/POST/PUT `/admin/dispatch/matching-window-config`

查看或运行时更新订单池远期订单匹配窗口配置。该配置用于控制预约时间较远的订单何时进入车辆匹配流程。

默认规则：

- 如果 `expected_pickup_earliest - request_time` 不超过 `far_pickup_threshold_seconds`，订单可以立即参与匹配。
- 如果超过 `far_pickup_threshold_seconds`，订单会先保留在订单池中，直到 `expected_pickup_earliest - far_pickup_match_lead_seconds` 后才参与匹配。
- 默认 `far_pickup_threshold_seconds=3600`，即 1 小时外的订单视为远期订单。
- 默认 `far_pickup_match_lead_seconds=1800`，即远期订单在期望上车时间前 30 分钟释放匹配。
- 配置为内存运行时配置，服务重启后恢复代码默认值。

GET 响应：

```json
{
  "far_pickup_threshold_seconds": 3600.0,
  "far_pickup_match_lead_seconds": 1800.0
}
```

POST/PUT 请求体：

```json
{
  "far_pickup_threshold_seconds": 3600,
  "far_pickup_match_lead_seconds": 1800
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `far_pickup_threshold_seconds` | number | 否 | 远期订单判断阈值，单位秒，必须大于等于 0 |
| `far_pickup_match_lead_seconds` | number | 否 | 远期订单提前释放匹配时间，单位秒，必须大于等于 0 |

说明：

- POST/PUT 可只传其中一个字段，未传字段保持当前值。
- 多运营区匹配也会使用同一套配置；订单仍只会在所属运营区内匹配车辆。

成功响应：

```json
{
  "status": "ok",
  "config": {
    "far_pickup_threshold_seconds": 3600.0,
    "far_pickup_match_lead_seconds": 1800.0
  }
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询或更新成功 |
| 400 | 参数不是数字或小于 0 |

### 4.4.3 GET/POST/PUT `/admin/dispatch/route-cost-config`

查看或运行时更新订单插单成本函数配置。配置更新后只影响后续新的派单、插单和重规划评估，不会主动重算已经生成的车辆路线。配置为内存运行时配置，服务重启后恢复代码默认值。

GET 响应示例：

```json
{
  "config": {
    "W_PASSENGER": 0.65,
    "W_ENTERPRISE": 0.2,
    "W_SOCIAL": 0.2,
    "W_FAIRNESS": 0.05,
    "WAIT_COST_PER_MIN": 4.0,
    "IN_CAR_COST_PER_MIN": 3.0,
    "LATE_ARRIVAL_COST_PER_MIN": 1.0,
    "OLD_DELAY_COST_PER_MIN": 6.0,
    "SEVERE_OLD_DELAY_PENALTY": 50.0,
    "MILEAGE_UTIL_PENALTY_BASE": 30.0,
    "LOAD_RATE_PENALTY_BASE": 20.0,
    "SOCIAL_DISTANCE_COST_PER_KM": 1.0,
    "BUSY_VEHICLE_MAX_ABSOLUTE_COST": 200.0
  },
  "defaults": {},
  "descriptions": {},
  "weight_total": 1.1,
  "runtime_only": true
}
```

POST/PUT 请求体示例：

```json
{
  "W_PASSENGER": 0.75,
  "OLD_DELAY_COST_PER_MIN": 8,
  "IN_CAR_COST_PER_MIN": 5,
  "BUSY_VEHICLE_MAX_ABSOLUTE_COST": 120
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `W_PASSENGER` | number | 否 | 乘客体验总权重 |
| `W_ENTERPRISE` | number | 否 | 企业效益总权重 |
| `W_SOCIAL` | number | 否 | 社会效益总权重 |
| `W_FAIRNESS` | number | 否 | 平台公平总权重 |
| `WAIT_COST_PER_MIN` | number | 否 | 乘客候车每分钟成本 |
| `IN_CAR_COST_PER_MIN` | number | 否 | 乘客在车每分钟成本 |
| `LATE_ARRIVAL_COST_PER_MIN` | number | 否 | 晚于最大送达时间后的每分钟成本 |
| `OLD_DELAY_COST_PER_MIN` | number | 否 | 插单导致原有乘客延误的每分钟成本 |
| `SEVERE_OLD_DELAY_PENALTY` | number | 否 | 原有乘客严重延误固定惩罚 |
| `MILEAGE_UTIL_PENALTY_BASE` | number | 否 | 里程利用率惩罚基数 |
| `LOAD_RATE_PENALTY_BASE` | number | 否 | 满载率惩罚基数 |
| `SOCIAL_DISTANCE_COST_PER_KM` | number | 否 | 每公里社会里程成本 |
| `BUSY_VEHICLE_MAX_ABSOLUTE_COST` | number | 否 | 非空闲车辆插单后的路线总成本上限；超过该值时不再给已有任务车辆继续插单，空车不受该阈值限制 |

说明：

- POST/PUT 可只传其中一个或多个字段，未传字段保持当前值。
- 所有字段必须是有限数字且大于或等于 0；允许传 `0` 关闭对应成本。
- 四个权重不强制相加等于 1，接口仅返回 `weight_total` 供平台观察。
- 调低 `BUSY_VEHICLE_MAX_ABSOLUTE_COST` 会更严格限制忙车继续插单，使订单更容易分给空车；调高后忙车更容易继续接顺路订单。

成功响应：

```json
{
  "status": "ok",
  "config": {
    "W_PASSENGER": 0.75
  },
  "weight_total": 1.2,
  "runtime_only": true
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询或更新成功 |
| 400 | 请求体不是 JSON 对象、存在未知字段、参数不是有限数字或小于 0 |

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
- 如果 `status=matched`，展示“已匹配车辆，等待司机端接收”。
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

- 仅在 `status=matching/matched/waiting` 时展示取消按钮。
- 收到 409 时刷新订单状态并禁用取消按钮。

### 4.7.1 POST `/orders/<request_id>/driver-push-confirmation`

平台回调司机端是否真正收到派单信息。算法端匹配成功后，订单先保持 `matched`；只有该接口确认 `received=true` 后，订单才进入 `waiting_pickup`。`matched` 待确认期间车辆仍可继续接新单；算法端不做 60 秒计时，平台推送超时或司机端未收到时由平台调用本接口并传 `received=false`。

请求体：

```json
{
  "vehicle_id": "72057594546144444",
  "route_version": "grasp-xxxx",
  "received": true,
  "reason": "driver_app_ack",
  "platform_message_id": "optional",
  "occurred_at": "2026-07-14 12:00:00"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `received` | boolean | 是 | `true` 表示司机端已收到；`false` 表示平台确认司机端未收到或平台侧超时 |
| `vehicle_id` | string | 否 | 本次派单车辆业务 ID；传入时会校验是否与当前待确认车辆一致 |
| `route_version` | string | 否 | 兼容旧平台的展示字段；确认逻辑只按订单 ID 和车辆 ID 判断，不再校验路线版本 |
| `reason` | string | 否 | 平台返回原因，如 `driver_app_ack/driver_app_unreachable/driver_push_timeout` |
| `occurred_at` | string | 否 | 平台确认发生时间，格式 `YYYY-MM-DD HH:MM:SS` |

`received=true` 成功响应：

```json
{
  "status": "waiting_pickup",
  "request_id": "order_10001",
  "vehicle_id": "72057594546144444",
  "answer_time": "2026-07-14 12:00:00"
}
```

`received=false` 成功响应：

```json
{
  "status": "requeued",
  "request_id": "order_10001",
  "vehicle_id": "72057594546144444",
  "reason": "driver_app_unreachable",
  "pool_size": 1
}
```

说明：`received=false` 只会移除当前 `request_id` 对应订单的 O/D 步骤，并将该订单退回订单池；同一辆车上的其他订单和后续插单路线会保留并刷新。

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 确认成功，或已退回订单池 |
| 400 | 请求体缺少 `received`、类型非法或时间格式非法 |
| 409 | 订单已退回、已改派或车辆不匹配 |

### 4.7.2 通勤快线 `/commute/*`

通勤快线适用于固定线路、固定站点、单向循环运行的业务，例如园区环线、校园通勤线和企业班车短驳线。快线不进入动态巴士 `/order` 订单池，订单复用 `bus_order`，并通过 `order_source='commute_express'` 区分。

典型业务场景：

- 后台先创建一条快线线路，并按固定站点顺序配置 `stops`。
- 后台把车辆绑定到线路，并设置车辆快线任务模式。
- 乘客按线路中的固定站点下单，系统只在该线路、该运营区内寻找可接快线车辆。
- 快线车辆接单后只维护服务步骤队列，不生成 A* 路线和高德导航路线。
- 司机端通过统一上下客接口推进快线订单状态。

核心约定：

- 一条线路按 `stops` 数组顺序单向循环，例如 `站点A -> 站点B -> 站点C -> 站点A`。
- 前端只传站点经纬度，后端用 `operation_area_id + longitude + latitude + deleted=0 + status='enabled'` 精确匹配 `map_poi`。
- 快线只做车辆匹配和订单状态推进，不生成 A* 路径、不请求高德驾车规划、不返回导航路线点。
- 快线车辆由 `bus_vehicle.operation_mode` 区分：`commute_fixed_waiting` 为定点候客，`commute_cruising` 为巡游车辆。
- 快线车辆调用 `/fleet/<vehicle_id>/path` 时只更新 GPS 和运行态，不触发动态巴士的路网吸附、路线裁剪或上下客联动。
- 两种快线车辆匹配时都使用车辆 GPS 作为当前位置，按车辆 GPS 到乘客上车站点的直线距离就近选择车辆。
- 车辆接单或插单时会维护 `vehicle.planned_route` 服务步骤队列；队列中 `O` 表示上车，`D` 表示下车。
- 快线车辆服务步骤变化后，通过单车推送接口 `/bus/python-dispatch/internal/fleet/{vehicleId}/push-navigation` 推送给平台。

#### GET `/commute/lines`

查询通勤快线线路列表。可选查询参数 `include_deleted=true` 用于包含已软删除线路。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `include_deleted` | boolean/string | 否 | `true/1/yes` 表示包含已软删除线路 |

成功响应：

```json
{
  "lines": [
    {
      "line_code": "line_001",
      "line_name": "大学城通勤快线",
      "operation_area_id": 10001,
      "route_mode": "loop",
      "status": "enabled",
      "stop_count": 3,
      "stops": [
        {
          "poi_id": 1,
          "poi_code": "poi_001",
          "station_name": "大学城北门",
          "lon": 113.1,
          "lat": 23.1,
          "line_order": 1
        }
      ]
    }
  ]
}
```

#### POST `/commute/lines`

创建线路，可同时携带 `stops` 初始化固定站点顺序。

```json
{
  "line_code": "line_001",
  "line_name": "大学城通勤快线",
  "operation_area_id": 10001,
  "route_mode": "loop",
  "status": "enabled",
  "description": "单向循环线路",
  "stops": [
    {"lon": 113.1, "lat": 23.1},
    {"lon": 113.2, "lat": 23.2}
  ]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `line_code` | string | 是 | 线路编码；未软删除线路中唯一 |
| `line_name` | string | 是 | 线路名称 |
| `operation_area_id` | integer | 是 | 运营区 ID，取 `map_operation_area.area_id` |
| `route_mode` | string | 否 | 线路运行方式，默认 `loop`，当前按单向循环处理 |
| `status` | string | 否 | 线路状态，默认 `enabled` |
| `description` | string | 否 | 线路说明 |
| `stops` | array | 否 | 固定站序；如传入则每项只需要 `lon/lat` |

`stops[]` 只需要 `lon/lat`，不传 `stop_seq/station_id/poi_id`。后端会按请求数组顺序保存线路循环顺序，并在响应中返回解析出的站点快照，如 `poi_id`、`poi_code`、`station_name`、`lon`、`lat`。

成功响应：

```json
{
  "status": "created",
  "line": {
    "line_code": "line_001",
    "line_name": "大学城通勤快线",
    "operation_area_id": 10001,
    "route_mode": "loop",
    "status": "enabled",
    "stop_count": 2,
    "stops": []
  }
}
```

#### GET/PUT/DELETE `/commute/lines/<line_code>`

按线路编码查询、更新或软删除线路。`PUT` 请求体与创建线路一致；如果携带 `stops`，会按经纬度重新解析并替换线路站点顺序。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `line_code` | string | 通勤快线线路编码 |

`GET` 成功响应：

```json
{
  "line": {
    "line_code": "line_001",
    "line_name": "大学城通勤快线",
    "operation_area_id": 10001,
    "status": "enabled",
    "stop_count": 2,
    "stops": []
  }
}
```

`DELETE` 为软删除，会把线路状态置为不可用，并同步停用该线路的车辆绑定关系。

`DELETE` 成功响应：

```json
{
  "status": "deleted",
  "line_code": "line_001"
}
```

#### PUT `/commute/lines/<line_code>/stops`

整体替换线路站点顺序。

```json
{
  "stops": [
    {"lon": 113.1, "lat": 23.1},
    {"lon": 113.2, "lat": 23.2},
    {"lon": 113.3, "lat": 23.3}
  ]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stops` | array | 是 | 站点经纬度数组，至少 2 个 |
| `stops[].lon` | number | 是 | 站点经度，必须精确匹配 `map_poi.longitude` |
| `stops[].lat` | number | 是 | 站点纬度，必须精确匹配 `map_poi.latitude` |

业务规则：`stops` 至少 2 个；同一线路不能重复使用同一个 `map_poi`；坐标不存在返回 `commute_stop_not_found_by_coordinate`；同一运营区相同坐标匹配多个站点返回 `commute_stop_coordinate_ambiguous`。

成功响应：

```json
{
  "status": "updated",
  "line_code": "line_001",
  "stops": [
    {
      "poi_id": 1,
      "poi_code": "poi_001",
      "station_name": "大学城北门",
      "lon": 113.1,
      "lat": 23.1,
      "line_order": 1
    }
  ]
}
```

#### POST `/commute/vehicles/assign`

把车辆绑定到线路，并设置快线任务模式。

```json
{
  "vehicle_code": "72057594546144444",
  "line_code": "line_001",
  "task_mode": "commute_fixed_waiting",
  "status": "active"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `vehicle_code` | string | 是 | 车辆业务编码 |
| `line_code` | string | 是 | 快线线路编码 |
| `task_mode` | string | 是 | `commute_fixed_waiting` 或 `commute_cruising` |
| `status` | string | 否 | 绑定状态，默认 `active` |

绑定成功后写入 `bus_commute_vehicle_assignment.vehicle_code`；同时同步更新车辆档案的 `operation_mode` 和 `operation_area_id`。定点候客不再保存固定等待站字段，匹配时统一使用车辆最新 GPS。

成功响应：

```json
{
  "status": "assigned",
  "assignment": {
    "vehicle_code": "72057594546144444",
    "line_code": "line_001",
    "operation_area_id": 10001,
    "task_mode": "commute_fixed_waiting",
    "status": "active"
  },
  "runtime_applied": true
}
```

说明：

- `vehicle_code` 当前表示车辆业务编码，对应车辆档案 `bus_vehicle.vehicle_code`。
- `runtime_applied=true` 表示该车辆已在当前运行态车队中找到并同步更新。
- `runtime_applied=false` 表示数据库绑定成功，但车辆当前不在运行态内存中，通常需要初始化或重新加载车辆后生效。

#### POST `/commute/orders`

创建通勤快线订单，并尝试匹配同线路、同运营区、容量足够的快线车辆。

```json
{
  "request_id": "commute_order_001",
  "line_code": "line_001",
  "origin_lon": 113.1,
  "origin_lat": 23.1,
  "destination_lon": 113.3,
  "destination_lat": 23.3,
  "passenger_phone": "13800000000",
  "passenger_id": "p001",
  "passenger_count": 1
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 订单请求 ID，全局唯一 |
| `line_code` | string | 是 | 快线线路编码 |
| `origin_lon` | number | 是 | 上车站经度，必须是该线路站点坐标 |
| `origin_lat` | number | 是 | 上车站纬度，必须是该线路站点坐标 |
| `destination_lon` | number | 是 | 下车站经度，必须是该线路站点坐标 |
| `destination_lat` | number | 是 | 下车站纬度，必须是该线路站点坐标 |
| `passenger_phone` | string | 是 | 乘客手机号 |
| `passenger_id` | string | 否 | 业务乘客 ID，落库到 `passenger_code` |
| `passenger_count` | integer | 否 | 乘客人数，默认 `1` |

匹配规则：

- 线路必须存在且 `status='enabled'`。
- 上下车坐标必须都属于该线路站点，且起终点不能相同。
- 定点候客和巡游车辆都使用车辆 GPS 到上车站点的直线距离做就近匹配。
- 无 GPS 的快线车辆不参与匹配。
- 候选车辆必须绑定同一线路、同一运营区，绑定状态为 `active`，车辆 `operation_mode` 为 `commute_fixed_waiting` 或 `commute_cruising`，且 `rest_status='operating'`。
- 车辆接单和插单时会保持已有上下客步骤相对顺序，只局部插入新订单 O/D，并校验全程载客数不超过容量。
- 匹配成功后订单状态为 `waiting_pickup`；无可用车辆时状态为 `pooled`。
- 快线订单写入 `bus_order`，`order_source='commute_express'`，线路和站点序列快照写入 `route_segments`。

匹配成功响应示例：

```json
{
  "status": "waiting_pickup",
  "order": {
    "request_id": "commute_order_001",
    "order_source": "commute_express",
    "status": "waiting_pickup",
    "line_code": "line_001",
    "operation_area_id": 10001,
    "origin_station_name": "大学城北门",
    "destination_station_name": "大学城南门",
    "assigned_vehicle_code": "72057594546144444",
    "route_poi_sequence": [1, 2, 3]
  },
  "candidate": {
    "vehicle_id": "72057594546144444",
    "vehicle_code": "72057594546144444",
    "plate_no": "粤A00001",
    "distance_to_origin_m": 0,
    "extra_distance_m": 0,
    "origin_insert_index": 0,
    "destination_insert_index": 1,
    "task_mode": "commute_fixed_waiting"
  },
  "vehicle": {
    "vehicle_id": "72057594546144444",
    "vehicle_code": "72057594546144444",
    "plate_no": "粤A00001",
    "operation_mode": "commute_fixed_waiting",
    "operation_area_id": 10001,
    "planned_route": [
      {
        "type": "O",
        "request_id": "commute_order_001",
        "target_poi_id": 1,
        "target_station_name": "大学城北门",
        "status": "waiting_pickup"
      },
      {
        "type": "D",
        "request_id": "commute_order_001",
        "target_poi_id": 3,
        "target_station_name": "大学城南门",
        "status": "waiting_pickup"
      }
    ]
  }
}
```

无可用车辆响应示例：

```json
{
  "status": "pooled",
  "order": {
    "request_id": "commute_order_001",
    "order_source": "commute_express",
    "status": "pooled"
  },
  "candidate": null
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 201 | 订单创建成功，可能已匹配车辆，也可能进入 `pooled` |
| 400 | 请求体字段缺失、类型非法或 JSON 非对象 |
| 404 | 线路不存在、车辆不存在或站点坐标未匹配 |
| 409 | 订单号冲突、站点重复、起终点相同或业务状态冲突 |
| 503 | 数据库不可用 |

#### GET `/commute/orders/<request_id>`

查询快线订单。返回数据来自 `bus_order`，其中 `route_segments.line_code` 和 `route_segments.route_poi_sequence` 保存快线线路快照。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `request_id` | string | 快线订单请求 ID |

成功响应：

```json
{
  "order": {
    "request_id": "commute_order_001",
    "order_source": "commute_express",
    "status": "waiting_pickup",
    "line_code": "line_001",
    "operation_area_id": 10001,
    "route_poi_sequence": [1, 2, 3],
    "origin_station_name": "大学城北门",
    "destination_station_name": "大学城南门",
    "assigned_vehicle_code": "72057594546144444"
  }
}
```

#### POST `/commute/orders/<request_id>/cancel`

取消快线订单；若订单已分配车辆，会从该车辆的剩余服务步骤中移除对应 O/D。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `request_id` | string | 快线订单请求 ID |

成功响应：

```json
{
  "status": "cancelled",
  "order": {
    "request_id": "commute_order_001",
    "status": "cancelled",
    "cancel_reason": "passenger_cancelled"
  }
}
```

#### POST `/fleet/<vehicle_id>/boarding-events`

快线车辆与动态巴士共用该接口确认当前下一步上车或下车。后端会根据车辆 `operation_mode` 自动分流，快线车辆不会调用动态巴士的 A* 或高德路线逻辑。

```json
{
  "action": "pickup",
  "request_id": "commute_order_001",
  "lon": 113.1,
  "lat": 23.1,
  "distance_threshold_m": 30
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `action` | string | 是 | `pickup` 表示确认上车，`dropoff` 表示确认下车 |
| `request_id` | string | 否 | 订单请求 ID；不传时默认确认车辆当前服务队列第一步 |
| `lon` | number | 否 | 确认位置经度；不传时使用车辆当前 GPS |
| `lat` | number | 否 | 确认位置纬度；不传时使用车辆当前 GPS |
| `distance_threshold_m` | number | 否 | 兼容旧请求字段，当前不再用于拦截上下客确认 |

确认限制：

- 车辆必须是快线车辆，且当前 `planned_route` 不为空。
- 只能确认当前下一步，即 `vehicle.planned_route[0]`。
- 当前步骤为 `O` 时只能执行 `pickup`，当前步骤为 `D` 时只能执行 `dropoff`。
- 如果传入 `request_id`，必须与当前第一步订单一致。
- 确认位置会写入响应中的 `distance_to_target`，但不再按距离阈值拦截上下客确认。

状态流转：`pickup` 将订单改为 `riding`；`dropoff` 将订单改为 `completed`。确认成功后会更新车辆运行态并触发 `commute_boarding_updated` 单车推送。

成功响应：

```json
{
  "status": "ok",
  "event": {
    "action": "pickup",
    "request_id": "commute_order_001",
    "distance_to_target": 8.5,
    "target_node": {
      "id": "poi_001",
      "poi_id": 1,
      "lon": 113.1,
      "lat": 23.1,
      "name": "大学城北门"
    }
  },
  "orders": {
    "on_board": ["commute_order_001"],
    "remaining": []
  },
  "vehicle": {}
}
```

#### 快线车辆 GPS 上报说明

快线车辆仍使用 `POST /fleet/<vehicle_id>/path` 上报 GPS。与动态巴士不同，快线车辆只更新 `gps/time`、车辆运行态和位置日志，不做道路吸附、路线裁剪、A* 重建、高德重规划或自动上下客。

请求示例：

```json
{
  "lon": 113.1,
  "lat": 23.1
}
```

#### 快线单车推送说明

快线车辆服务队列变化后，后端复用 `api/fleet_push.py` 的单车推送能力，把当前车辆信息推送到平台：

```text
POST /bus/python-dispatch/internal/fleet/{vehicleId}/push-navigation
```

常见 `event_reason`：

| 事件原因 | 触发场景 |
| --- | --- |
| `commute_order_assigned` | 快线车辆从无任务变为接到订单 |
| `commute_order_inserted` | 快线车辆已有服务步骤时插入新订单 |
| `commute_order_cancelled` | 快线订单取消后移除车辆服务步骤 |
| `commute_boarding_updated` | 快线车辆完成上车或下车确认 |

常见错误码：

| 错误码 | HTTP 状态码 | 说明 |
| --- | --- | --- |
| `invalid_json_body` | 400 | 请求体不是 JSON 对象 |
| `invalid_request` | 400 | 请求字段缺失或格式非法 |
| `request_id_required` | 400 | 创建快线订单缺少 `request_id` |
| `line_code_required` | 400 | 创建快线订单缺少 `line_code` |
| `passenger_phone_required` | 400 | 创建快线订单缺少乘客手机号 |
| `origin_lon_required` / `origin_lat_required` | 400 | 缺少上车站经纬度 |
| `destination_lon_required` / `destination_lat_required` | 400 | 缺少下车站经纬度 |
| `commute_stops_required` | 400 | 替换站序时 `stops` 不是非空数组 |
| `commute_stop_not_found_by_coordinate` | 404 | 坐标未匹配到启用站点 |
| `commute_stop_coordinate_ambiguous` | 409 | 坐标匹配多个启用站点或线路内重复 |
| `commute_stop_duplicate` | 409 | 同一线路重复配置同一个站点 |
| `commute_stop_not_in_line` | 404 | 上下车坐标不在线路中 |
| `same_origin_destination` | 409 | 上下车站点相同 |
| `commute_line_exists` | 409 | 线路编码已存在 |
| `commute_line_not_found` | 404 | 线路不存在或未启用 |
| `commute_order_exists` | 409 | 订单请求 ID 已存在 |
| `commute_order_not_found` | 404 | 快线订单不存在 |
| `vehicle_not_found` | 404 | 车辆不存在或未进入运行态 |
| `no_commute_step` | 409 | 车辆当前没有待确认服务步骤 |
| `invalid_action` | 400 | `action` 不是 `pickup/dropoff` |
| `invalid_step_action` | 409 | 当前服务步骤与上/下车动作不匹配 |
| `request_id_not_current` | 409 | `request_id` 不是车辆当前下一步订单 |
| `vehicle_position_missing` | 400 | 车辆当前位置为空，无法确认上下客 |
| `database_unavailable` | 503 | 数据库不可用 |

### 4.8 GET `/fleet`

查询全部车辆状态。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `operation_area_code` | string | 否 | 只查询指定运营区的运行车队；不传时返回全量车队 |

响应示例：

```json
{
  "operation_area_code": "area_001",
  "fleet": []
}
```

`fleet[]` 元素结构说明见`3.2`的`Vehicle车辆信息`。

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

### 4.9 POST `/fleet/<vehicle_id>/path`

车辆 GPS 上报接口。后端根据车辆当前高德规划路线或路网对 GPS 坐标做吸附，更新车辆 `gps`、`last_node`、`next_node`、`progress`，并写入运行态和 GPS 历史轨迹。

该接口只处理GPS信息更新：

- 不自动触发上车/下车，响应中的 `events` 通常为空数组。
- 不重建 A* 后续路线。
- 不触发高德驾车路线重规划。
- 有 `planned_route_segment_grasped_point` / `planned_route_grasped_point` 时，优先吸附到高德规划路线，`snap.source` / `snapped_point.snap_source` 为 `amap_grasped_route`。
- 前端车辆图标应使用响应中的 `gps` 或 `snap.point`，`reported_gps` 仅表示原始上报坐标。

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
| 409 | 车辆当前位置无法吸附到可用路线或路网 |

### 4.10 POST `/fleet/<vehicle_id>/boarding-events`

司机端显式确认当前车辆的下一步上车或下车事件。该接口用于替代旧版 `/path` 中的自动上下客逻辑。

处理规则：

- 只允许确认当前车辆 `planned_route[0]` 对应的下一步 O/D。
- `action=pickup` 只能确认 `O` 步骤，`action=dropoff` 只能确认 `D` 步骤。
- 后端会计算车辆当前位置或请求体坐标到目标 O/D 点的距离并随响应返回，但不再按距离阈值拦截。
- 成功后会推进订单状态并移除当前计划步骤，但不会触发高德重规划，也不会重建 A* 路线。

请求体：

```json
{
  "action": "pickup",
  "request_id": "REQ-1781761465166-1-68790",
  "lon": 113.409132,
  "lat": 23.060574,
  "distance_threshold_m": 30,
  "occurred_at": "2026-06-29 12:00:00"
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `action` | string | 是 | `pickup` 表示已上车，`dropoff` 表示已下车 |
| `request_id` | string/null | 否 | 为空时默认确认当前下一步订单；传入时必须等于当前下一步订单 |
| `lon` / `lng` / `longitude` | number | 否 | 确认位置经度；为空时使用车辆当前 `gps.lon` |
| `lat` / `latitude` | number | 否 | 确认位置纬度；为空时使用车辆当前 `gps.lat` |
| `distance_threshold_m` | number | 否 | 兼容旧请求字段，当前不再用于拦截上下客确认 |
| `occurred_at` | string | 否 | 事件发生时间，格式 `YYYY-MM-DD HH:MM:SS`；为空时使用当前业务时间 |

成功响应：

```json
{
  "status": "ok",
  "event": {
    "action": "pickup",
    "type": "O",
    "request_id": "REQ-1781761465166-1-68790",
    "distance_to_target": 8.5,
    "confirmed_position": {
      "lon": 113.409132,
      "lat": 23.060574
    },
    "node": {
      "id": "113.409132_23.060574",
      "lon": 113.409132,
      "lat": 23.060574,
      "name": "大学城南门",
      "zone": 3
    }
  },
  "orders": {
    "on_board": ["REQ-1781761465166-1-68790"],
    "remaining": []
  },
  "vehicle": {
    "...": "见 3.2 Vehicle车辆信息"
  }
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 确认成功 |
| 400 | 未初始化、`action` 非法、时间格式非法、坐标不是数字 |
| 404 | 车辆不存在 |
| 409 | 当前无待确认步骤、`action` 与当前步骤不匹配、`request_id` 不是当前下一步 |

### 4.11 POST `/fleet/<vehicle_id>/rest`

司机端或平台请求车辆休息。接口兼容旧请求体，不传 `source` 时按司机主动休息处理；平台可通过 `source=platform` 复用同一接口发起立即休息或预约休息。

请求体为空的话，表示立即收车：

```json
{
    
}
```

请求体，预约休息：

```json
{
  "source": "platform",
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
| `source` | string | 否 | 请求来源：`driver` 司机主动休息，`platform` 平台发起休息；默认 `driver` |
| `desired_rest_time` | string/number/null | 否 | 为空表示马上收车；数字表示从当前后端时间起多少秒后休息；字符串按业务时间解析 |
| `rest_duration_minutes` | number | 否 | 休息时长，后端限制在 15-30 分钟 |

响应示例：

```json
{
  "vehicle_id": "巴士-绿色01",
  "source": "platform",
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
| 400 | 未初始化、`source` 非法或参数格式错误 |
| 404 | 车辆不存在 |

说明：车辆连续运营时间 `driving_time` 只作为展示/统计字段，不再由算法自动触发强制收车休息；强制休息和预约休息均由司机端或平台调用本接口触发。

### 4.12 GET `/status`

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
  "order_pool_size": 0,
  "completed_orders": 0,
  "operation_restriction_policies": {
    "10001": null
  }
}
```

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `initialized` | boolean | 系统是否已初始化 |
| `system_time` | object | 当前后端业务时间 |
| `nodes_count` | integer | 路网节点数量 |
| `pois_count` | integer | 合法上下客 POI 数量 |
| `edges_count` | integer | 路网有向边数量 |
| `default_operation_area_code` | string/null | 固定为 `null`；系统不再使用默认运营区 |
| `loaded_areas` | array | 当前已加载的运营区列表 |
| `fleet` | array | 当前内存运行车队 |
| `order_pool_size` | integer | 待匹配订单池数量 |
| `completed_orders` | integer | 已完成/归档订单数量 |
| `operation_restriction_policies` | object | 按运营区 ID 返回的当前生效运营禁区策略映射 |

### 4.13 GET `/pois`

获取指定运营区的合法上下客 POI 兴趣点。接口对外返回数据库 `map_poi` 中的原始站点坐标，供前端展示、手动下单和随机下单使用；吸附到路网后的节点坐标只通过 `snapped_*` 字段返回，作为算法内部地图运算的参考信息。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `operation_area_id` | integer | 是 | 指定运营区业务 ID；不传时返回 `400` |

响应示例：

```json
{
  "operation_area_id": 10001,
  "operation_area_code": "area_001",
  "pois": [
    {
      "id": 101,
      "poi_id": 101,
      "poi_code": "poi_1",
      "name": "站点A",
      "lon": 113.38,
      "lat": 23.04,
      "longitude": 113.38,
      "latitude": 23.04,
      "zone": "A",
      "snapped_node_id": "113.380100_23.040200",
      "snapped_lon": 113.3801,
      "snapped_lat": 23.0402,
      "poi_snap_source": "reflect_csv",
      "reflect_snap_mode": "existing_node",
      "reflect_station_name": "站点A",
      "reflect_road_name": "道路A",
      "reflect_direction": "东-西",
      "reflect_lng": 113.3801,
      "reflect_lat": 23.0402
    }
  ]
}
```

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `pois[].id` | integer | 数据库 `map_poi.id` |
| `pois[].poi_id` | integer | 数据库 `map_poi.id`，与 `id` 一致 |
| `pois[].poi_code` | string | 数据库 POI 业务编码 |
| `pois[].name` | string | POI 名称 |
| `pois[].lon` / `pois[].longitude` | number | 数据库 `map_poi.longitude` 原始站点经度 |
| `pois[].lat` / `pois[].latitude` | number | 数据库 `map_poi.latitude` 原始站点纬度 |
| `pois[].zone` | string/number/null | 所属分区 |
| `pois[].station_direction` | string/null | 数据库 `map_poi.station_direction`，用于匹配映射表 `Calc_Dir` |
| `pois[].snapped_node_id` | string/null | 运行态内部吸附后的路网节点 ID |
| `pois[].snapped_lon` / `pois[].snapped_lat` | number/null | 运行态内部吸附后的路网节点坐标 |
| `pois[].poi_snap_source` | string/null | 运行态节点来源；`reflect_csv` 表示映射表坐标命中已有路网节点，`reflect_csv_nearest_node` 表示映射表坐标未命中已有节点后按映射表坐标吸附最近路网节点，`nearest_node` 表示未命中映射表后按数据库原始坐标吸附 |
| `pois[].reflect_snap_mode` | string/null | 映射表坐标处理方式；`existing_node` 表示已有节点，`nearest_node` 表示按映射表坐标二次吸附 |
| `pois[].reflect_station_name` | string/null | 命中的映射表 `STIONNAME` |
| `pois[].reflect_road_name` | string/null | 命中的映射表 `name` |
| `pois[].reflect_direction` | string/null | 命中的映射表 `Calc_Dir` |
| `pois[].reflect_lng` / `pois[].reflect_lat` | number/null | 命中的映射表 `gd_lng/gd_lat` |

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 400 | 系统未初始化 |

### 4.13.1 GET `/map/road-network`

按运营区返回当前内存路网节点和边，主要供前端地图测试展示。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `operation_area_id` | integer | 是 | 指定运营区业务 ID；不传时返回 `400` |

响应示例：

```json
{
  "operation_area_id": 10001,
  "operation_area_code": "area_001",
  "nodes": [],
  "edges": []
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 400 | 系统未初始化或运营区未加载 |

### 4.13.2 POST `/admin/stations`

新增单个或多个站点，并写入 `map_poi`。新增时只校验运营区是否存在、站点必填字段、经纬度格式与唯一性，不再校验站点坐标是否落在所属运营区 SHP 范围内。新增成功后，如果对应运营区已经加载到运行态，会立即重新读取数据库站点并刷新该运营区 POI。

请求体支持单条：

```json
{
  "operation_area_id": 10001,
  "station_name": "大学城北门",
  "area": "大学城外环西路",
  "station_direction": "东-西",
  "lon": 113.12345678,
  "lat": 23.12345678
}
```

也支持批量：

```json
{
  "stations": [
    {
      "operation_area_id": 10001,
      "station_name": "大学城北门",
      "area": "大学城外环西路",
      "station_direction": "东-西",
      "lon": 113.12345678,
      "lat": 23.12345678
    }
  ]
}
```

必填字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `operation_area_id` | integer | 运营区业务 ID，对应 `map_operation_area.area_id` |
| `station_name` | string | 站点名称，落库到 `map_poi.poi_name` |
| `area` | string | 站点所属道路或区域名称，落库到 `map_poi.areas` |
| `station_direction` | string | 站点方向，落库到 `map_poi.station_direction`，并用于映射表 `Calc_Dir` 匹配 |
| `lon`/`lng`/`longitude` | number | 经度 |
| `lat`/`latitude` | number | 纬度 |

可选字段包括：`poi_code`、`station_id`、`station_type`、`direction_angle`、`address`、`dept_id`、`org_code`、`poi_type`、`zone`、`status`、`source_status`、`audit_status`、`source_create_time`。

响应示例：

```json
{
  "total": 1,
  "success_count": 1,
  "failure_count": 0,
  "results": [
    {
      "index": 0,
      "success": true,
      "status": 201,
      "station": {
        "id": 123,
        "operation_area_id": 10001,
        "poi_code": "station_10001_113_12345678_23_12345678",
        "station_name": "大学城北门",
        "lon": 113.12345678,
        "lat": 23.12345678
      }
    }
  ],
  "runtime_refresh": {
    "runtime_refreshed": true,
    "refreshed": [{"operation_area_id": 10001, "poi_count": 12}],
    "skipped": []
  }
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 201 | 全部新增成功 |
| 207 | 批量中部分成功、部分失败 |
| 400 | 请求体格式、必填字段或经纬度非法 |
| 404 | 运营区不存在 |
| 409 | 坐标或站点编号冲突 |
| 503 | 数据库不可用 |

### 4.13.3 DELETE `/admin/stations`

按经纬度删除单个或多个站点。删除采用软删除：`deleted=1`，`status='disabled'`。后端不做最近点匹配，只按数据库中规范化到 8 位小数后的经纬度精确匹配。

请求体支持单条：

```json
{
  "lon": 113.12345678,
  "lat": 23.12345678
}
```

也支持批量：

```json
{
  "stations": [
    {
      "lon": 113.12345678,
      "lat": 23.12345678,
      "operation_area_id": 10001
    }
  ]
}
```

说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `lon`/`lng`/`longitude` | number | 是 | 经度 |
| `lat`/`latitude` | number | 是 | 纬度 |
| `operation_area_id` | integer | 否 | 坐标匹配多个站点时用于消除歧义 |

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 全部删除成功 |
| 207 | 批量中部分成功、部分失败 |
| 400 | 请求体格式或经纬度非法 |
| 404 | 数据库中不存在该坐标站点 |
| 409 | 同一坐标匹配多个站点，需要补充 `operation_area_id` |
| 503 | 数据库不可用 |

错误码：

| 错误码 | 说明 |
| --- | --- |
| `invalid_json_body` | 请求体不是合法 JSON 对象 |
| `stations_required` | 批量模式下 `stations` 为空或不是数组 |
| `operation_area_id_required` | 新增站点缺少运营区 ID |
| `operation_area_id_invalid` | 运营区 ID 格式非法 |
| `operation_area_not_found` | 运营区不存在或已删除 |
| `station_name_required` | 缺少站点名称 |
| `station_area_required` | 缺少站点所属道路或区域名称 |
| `station_direction_required` | 缺少站点方向 |
| `station_lon_required` / `station_lat_required` | 缺少经纬度字段 |
| `station_lon_invalid` / `station_lat_invalid` | 经纬度不是数字 |
| `station_coordinate_out_of_range` | 经纬度超出合法范围 |
| `station_coordinate_exists` | 同一运营区已有相同经纬度站点 |
| `station_code_exists` | 同一运营区站点编号冲突 |
| `station_not_found_by_coordinate` | 数据库中不存在该经纬度站点 |
| `station_coordinate_ambiguous` | 同一坐标匹配多个站点 |
| `database_unavailable` | 数据库不可用 |
| `station_create_failed` | 新增站点发生未分类异常 |
| `station_delete_failed` | 删除站点发生未分类异常 |

### 4.14 GET `/operation-restrictions/policies`

查询运营禁区策略列表。可通过 `operation_area_id` 过滤某个运营区；传入该参数时同时返回该运营区当前生效策略。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `operation_area_id` | integer | 否 | 运营区业务 ID，对应 `map_operation_area.area_id`；不传时返回全部策略，但 `active_policy=null` |

响应示例：

```json
{
  "operation_area_id": 10001,
  "policies": [					# 当前数据库中所有的运营禁区策略
    {
      "operation_area_id": 10001,
      "policy_code": "campus-block",  # 运营禁区属性
      "policy_name": "校园施工禁区",	 # 运营禁区名字（通过该字段查询）
      "description": "临时施工区域",   # 运营禁区描述
      "polygons": [{
                    "area_km2": 0.198103, # 区域1面积
                    "bounds": {
                        "max_lat": 23.052028,
                        "max_lon": 113.39797,
                        "min_lat": 23.046698,
                        "min_lon": 113.392875},
                    "index": 0,			# 索引
                    "name": "polygon-1",  # 区域1名字
                    "points": [		# 区域1多边形坐标点
                        {
                            "lat": 23.050053,
                            "lon": 113.39797
                        },
                        {
                            "lat": 23.046698,
                            "lon": 113.394843
                        },
                        {
                            "lat": 23.048752,
                            "lon": 113.392895
                        },
                        {
                            "lat": 23.051336,
                            "lon": 113.392875
                        },
                        {
                            "lat": 23.052028,
                            "lon": 113.395199
                        },
                        {
                            "lat": 23.051109,
                            "lon": 113.397691
                        }
                    ]
                }
            ],
            "polygons_json": [
                {
                    "area_km2": 0.198103,
                    "bounds": {
                        "max_lat": 23.052028,
                        "max_lon": 113.39797,
                        "min_lat": 23.046698,
                        "min_lon": 113.392875
                    },
                    "index": 0,
                    "name": "polygon-1",
                    "points": [
                        {
                            "lat": 23.050053,
                            "lon": 113.39797
                        },
                        {
                            "lat": 23.046698,
                            "lon": 113.394843
                        },
                        {
                            "lat": 23.048752,
                            "lon": 113.392895
                        },
                        {
                            "lat": 23.051336,
                            "lon": 113.392875
                        },
                        {
                            "lat": 23.052028,
                            "lon": 113.395199
                        },
                        {
                            "lat": 23.051109,
                            "lon": 113.397691
                        }
                    ]
                }],
      "amap_avoidpolygons": "113.4001,23.0501;113.4011,23.0501;113.4011,23.0511",   # 组成多边形禁区的若干个点（最多支持16个）
      "polygon_count": 1,   # 当前运营禁区策略的禁区数量
      "vertex_count": 4,
      "total_area_km2": 0.01,	# 当前运营禁区策略的面积
      "status": "enabled",		# 是否可用
      "tenant_id": "000000",
      "is_active": true,        # 是否启用
      "created_at": "2026-06-23 16:30:16.703000",
      "updated_at": "2026-06-24 18:59:54.741000",
      "policy_signature": "campus-block：xxxxxxxx"
    },
	...
  ],
  "active_policy": null			# 指定运营区当前生效的运营禁区策略
},
...  # 如果有多个运营禁区策略的话
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |

### 4.15 POST `/operation-restrictions/policies`

创建运营禁区策略。后端会校验并规范化 polygon，生成可传给高德 Web 服务 v5 驾车规划的 `avoidpolygons` 字符串。

请求体：

```json
{
  "operation_area_id": 10001,
  "policy_code": "campus-block",
  "policy_name": "校园施工禁区",
  "description": "临时施工区域",
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

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `operation_area_id` | integer | 是 | 策略所属运营区业务 ID，对应 `map_operation_area.area_id` |
| `policy_code` | string | 是 | 策略编号，允许重复 |
| `policy_name` | string | 是 | 策略名称，同租户下必须唯一 |
| `description` | string/null | 否 | 策略描述 |
| `polygons` | array | 是 | 禁区 polygon 列表，至少 1 个 |
| `polygons[].name` | string/null | 否 | 禁区区域名称 |
| `polygons[].points` | array | 是 | polygon 顶点列表，后端允许前端重复传闭合尾点 |

校验规则：

| 规则 | 说明 |
| --- | --- |
| polygon 数量 | 最多 32 个 |
| 单个 polygon 顶点数 | 最多 16 个，至少 3 个有效顶点 |
| 单个 polygon 面积 | 不超过 81 平方公里 |
| 坐标范围 | 经度 `-180~180`，纬度 `-90~90` |
| 几何形状 | 不允许零面积或自相交 polygon |

成功响应：

```json
{
  "policy": {
    "operation_area_id": 10001,
    "policy_code": "campus-block",
    "policy_name": "校园施工禁区",
    "is_active": false,
    "policy_signature": "campus-block:xxxxxxxxxxxxxxxx"
  }
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 201 | 创建成功 |
| 400 | 参数错误、polygon 不合法或策略名称已存在 |
| 500 | 服务端异常 |

### 4.16 GET `/operation-restrictions/policies/<policy_identity>`

查询单个运营禁区策略。`policy_identity` 可传策略名称或策略编号；由于策略编号允许重复，前端优先使用唯一的 `policy_name`，只有确认编号唯一时再使用 `policy_code`。前端拼接 URL 时需要编码。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `policy_identity` | string | 策略名称或策略编号，推荐传 `policy_name` |

成功响应：

```json
{
  "policy": {
    "policy_code": "campus-block",
    "policy_name": "校园施工禁区",
    "polygons": []
  }
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 404 | 策略不存在 |

### 4.17 PUT `/operation-restrictions/policies/<policy_identity>`

更新单个运营禁区策略。请求体结构与创建接口一致；编辑已有策略时不允许修改 `policy_name`。由于策略编号允许重复，前端优先使用唯一的 `policy_name` 作为路径参数。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `policy_identity` | string | 策略名称或策略编号，推荐传 `policy_name` |

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 更新成功 |
| 400 | 参数错误、polygon 不合法或试图修改策略名称 |
| 404 | 策略不存在 |
| 500 | 服务端异常 |

### 4.18 DELETE `/operation-restrictions/policies/<policy_identity>`

软删除单个运营禁区策略。如果删除的是某运营区当前生效策略，后端只同步清空该运营区当前策略。

成功响应：

```json
{
  "status": "deleted",
  "policy_identity": "校园施工禁区",
  "operation_area_id": 10001,
  "active_policy": null
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 删除成功 |
| 404 | 策略不存在 |
| 500 | 服务端异常 |

### 4.19 GET `/operation-restrictions/active`

查询指定运营区当前生效的运营禁区策略。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `operation_area_id` | integer | 是 | 运营区业务 ID，对应 `map_operation_area.area_id` |

响应示例：

```json
{
  "operation_area_id": 10001,
  "policy": null
}
```

`policy=null` 表示当前未启用任何禁区策略。

### 4.20 POST `/operation-restrictions/active`

设置指定运营区当前生效的禁区策略，或关闭该运营区禁区限制。策略切换只影响后续新路线计算，不会主动重算已有车辆路线。由于策略编号允许重复，前端优先传 `policy_name`。

请求体，按策略名称选择：

```json
{
  "operation_area_id": 10001,
  "policy_name": "校园施工禁区"
}
```

请求体，关闭禁区：

```json
{
  "operation_area_id": 10001,
  "policy_code": null
}
```

成功响应：

```json
{
  "status": "active_updated",
  "operation_area_id": 10001,
  "policy": null
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 设置成功 |
| 400 | 缺少 `operation_area_id` |
| 404 | 指定策略不存在或已禁用 |
| 500 | 服务端异常 |

### 4.20.0 GET `/admin/shp-files`

查询项目 `shp` 文件夹下可用于运营区配置的 SHP 地图文件路径。接口只返回相对于项目根目录的路径，可直接作为新增或更新运营区时的 `shp_path` 填充值。

可用规则：

- `.shp` 文件存在。
- 同目录下存在同名 `.shx` 文件。
- 同目录下存在同名 `.dbf` 文件。

响应示例：

```json
{
  "root": "shp",
  "count": 1,
  "paths": [
    "shp/tianhe_shp_0713/zjgc_0713.shp"
  ]
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |

### 4.20.1 GET `/admin/operation-areas`

查询数据库中未软删除的运营区列表。该接口不要求系统已初始化。

响应示例：

```json
{
  "areas": [],
  "loaded_areas": [],
  "default_operation_area_code": null
}
```

### 4.20.2 POST `/admin/operation-areas`

新增运营区。`code` 在未软删除记录中必须唯一，一个运营区对应一个 SHP 文件。

请求体：

```json
{
  "area_id": 10001,
  "org_id": 20001,
  "dept_id": 30001,
  "code": "area_001",
  "name": "大学城运营区",
  "org_code": "org_001",
  "org_name": "示例公司",
  "status": "enabled",
  "city_code": "440100",
  "city_name": "广州市",
  "country_code": "440113",
  "country_name": "番禺区",
  "audit_status": "approved",
  "shp_path": "dxc_traffic_shp/dxc_rule.shp",
  "shp_name": "dxc_rule.shp",
  "shp_version": "v1",
  "shp_encoding": "utf-8",
  "coord_system": "gcj02",
  "load_on_startup": 1,
  "description": "测试运营区"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `area_id` | integer | 是 | 业务区域 ID |
| `org_id` | integer | 是 | 机构 ID |
| `dept_id` | integer | 是 | 部门 ID |
| `code` | string | 是 | 运营区编码，未软删除记录中唯一 |
| `name` | string | 是 | 运营区名称 |
| `org_code` | string | 是 | 所属公司或机构编码 |
| `org_name` | string | 是 | 所属公司或机构名称 |
| `status` | string | 是 | `enabled/disabled`，生效加载要求为 `enabled` |
| `city_code` | string | 是 | 城市编码 |
| `city_name` | string | 是 | 城市名称 |
| `country_code` | string | 是 | 区县编码；后端兼容写入数据库 `county_code` |
| `country_name` | string | 是 | 区县名称；后端兼容写入数据库 `county_name` |
| `audit_status` | string | 否 | `approved/pending/rejected`，生效加载要求为 `approved` |
| `shp_path` | string | 是 | SHP 文件路径 |
| `shp_name` | string | 否 | SHP 文件名 |
| `shp_version` | string | 否 | SHP 版本 |
| `shp_encoding` | string | 否 | SHP/DBF 首选编码，默认先尝试 `utf-8`；失败后自动尝试 `gb18030/gbk/cp936/gb2312/big5`，成功编码会写回加载结果 |
| `coord_system` | string | 否 | 坐标系，默认 `gcj02` |
| `load_on_startup` | integer/boolean | 是 | 是否在 `/init` 时自动加载 |
| `area_points/area_polygon/area_center` | object/array/string | 否 | 区域几何信息 |
| `description` | string | 否 | 说明文本 |

状态码：

| 状态码 | 场景 |
| --- | --- |
| 201 | 创建成功 |
| 400 | 缺少运营区创建必填字段、枚举值非法，或运行态预加载失败 |
| 409 | 运营区编码已存在 |
| 503 | 数据库不可用 |

新增运营区时，后端会先预加载 SHP 并确认可进入运行态；预加载失败会返回 `operation_area_runtime_load_failed`，且不会写入 `map_operation_area`。创建或更新运营区后，如果 `status='enabled'` 且 `audit_status='approved'`，后端会立即尝试把该运营区 SHP 加载进当前运行态。响应中会包含 `runtime_load`：

```json
{
  "area": {},
  "runtime_load": {
    "status": "ready",
    "area": {
      "code": "area_001",
      "nodes": 1000,
      "edges": 2000,
      "pois": 50
    },
    "default_operation_area_code": null,
    "fleet_size": 3
  }
}
```

`runtime_load.status` 可能为：

| 值 | 说明 |
| --- | --- |
| `ready` | 已加入运行态，可被 `/pois`、`/fleet`、订单和车辆接口使用 |
| `skipped` | 当前运营区状态未触发运行态加载 |
| `error` | SHP 加载失败，错误原因见 `runtime_load.error` |

### 4.20.3 GET `/admin/operation-areas/<area_id>`

查询单个运营区。

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 404 | 运营区不存在 |
| 503 | 数据库不可用 |

### 4.20.4 PUT `/admin/operation-areas/<area_id>`

更新单个运营区。路径中的 `area_id` 为身份字段，对应 `map_operation_area.area_id`；请求体中的 `code` 仅作为运营区编码字段保存。

| 状态码 | 场景 |
| --- | --- |
| 200 | 更新成功 |
| 400 | 缺少名称或 SHP 路径 |
| 404 | 运营区不存在 |
| 503 | 数据库不可用 |

### 4.20.5 DELETE `/admin/operation-areas/<area_id>`

软删除运营区。软删除前会检查该运营区是否仍有未完成订单；只要存在 `pooled/matched/waiting_pickup/riding` 订单，或运行态车辆仍有 `planned_route/on_board_orders`，接口会拒绝删除。

删除成功后，该运营区不会被 `/init` 加载；该运营区下车辆会被重置为 `operation_status='offline'` 且 `operation_area_id=NULL`，对应运行态记录也会被清理。

删除失败示例：

```json
{
  "error": "operation_area_has_unfinished_orders",
  "message": "运营区仍有未完成订单，不能删除",
  "operation_area_id": 10001,
  "blockers": {
    "pooled_orders": [],
    "vehicles": [],
    "database_orders": []
  }
}
```

| 状态码 | 场景 |
| --- | --- |
| 200 | 删除成功 |
| 409 | 运营区仍有未完成订单或车辆任务 |
| 404 | 运营区不存在 |
| 503 | 数据库不可用 |

### 4.20.6 POST `/admin/operation-areas/<area_id>/load-test`

测试加载指定运营区 SHP。接口会尝试构建 `CityGraph`，并写回 `load_status`、`load_error`、`node_count`、`edge_count`、`poi_count`、`bounds_json`、`last_loaded_at` 等加载结果，但不会改变当前运行中的 `state.city_maps`。

响应示例：

```json
{
  "status": "ready",
  "area": {
    "code": "area_001",
    "node_count": 1000,
    "edge_count": 2000,
    "poi_count": 50
  }
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 测试加载成功 |
| 400 | SHP 路径为空或加载失败 |
| 404 | 运营区不存在 |
| 503 | 数据库不可用 |

### 4.21 GET `/admin/driver-vehicle/options`

返回司机车辆管理表单所需枚举，以及当前司机和车辆档案列表。

响应示例：

```json
{
  "driver_employment_statuses": ["active", "inactive", "blocked"],  # 雇佣司机的状态
  "driver_work_statuses": ["off_duty", "listening", "serving", "resting"],  # 司机的工作状态
  "vehicle_operation_statuses": ["operating", "resting", "closing", "offline", "maintenance"], # 车辆的状态
  "vehicle_types": ["bus", "large_bus", "mid_bus", "small_bus"],
  "operation_areas": [],
  "loaded_operation_areas": [],
  "default_operation_area_code": null,
  "drivers": [],  # 当前司机信息
  "vehicles": []  # 当前车辆信息
}
```

前端建议：

- 新增/编辑司机车辆表单的下拉框统一从该接口读取。
- 页面打开时调用一次，新增、编辑、删除成功后再刷新一次。

### 4.22 GET `/admin/drivers`

查询未软删除的司机档案列表。

响应示例：

```json
{
  "drivers": []
}
```

### 4.23 POST `/admin/drivers`

创建司机档案。`driver_code` 是司机业务身份字段，创建后不可修改；`driver_no` 遵循数据库唯一约束，冲突返回 `409`。

请求体：

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
  "work_status": "off_duty",  # 工作状态
  "remark": ""
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `driver_code` | string | 是 | 司机业务编码，创建后不可修改 |
| `driver_no` | string | 是 | 司机工号，同租户下唯一 |
| `driver_name` | string | 否 | 司机姓名；为空时后端会回退为工号或编码 |
| `phone` | string | 否 | 手机号 |
| `id_card_no` | string | 否 | 身份证号 |
| `license_no` | string | 否 | 驾驶证号 |
| `license_class` | string | 否 | 准驾车型 |
| `license_expire_date` | string/null | 否 | 驾驶证到期日，格式 `YYYY-MM-DD` |
| `service_city` | string | 否 | 服务城市 |
| `employment_status` | string | 否 | 雇佣状态，见 `/admin/driver-vehicle/options` |
| `work_status` | string | 否 | 工作状态，见 `/admin/driver-vehicle/options` |
| `remark` | string | 否 | 备注 |

成功响应：

```json
{
  "driver": {}
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 201 | 创建成功 |
| 400 | 参数错误 |
| 409 | 司机工号等唯一字段冲突 |

### 4.24 GET `/admin/drivers/<driver_code>`

查询单个司机档案。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `driver_code` | string | 司机业务编码 |

成功响应：

```json
{
  "driver": {}
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 404 | 司机不存在 |

### 4.25 PUT `/admin/drivers/<driver_code>`

更新司机档案。`driver_code` 以路径参数为准，请求体中的 `driver_code` 会被忽略。

请求体：同 `POST /admin/drivers`。

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 更新成功 |
| 400 | 参数错误 |
| 404 | 司机不存在 |
| 409 | 司机工号等唯一字段冲突 |

### 4.26 DELETE `/admin/drivers/<driver_code>`

软删除司机档案。如果司机仍被车辆绑定，返回 `409`。

成功响应：

```json
{
  "status": "deleted",
  "driver_code": "driver-001"
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 删除成功 |
| 404 | 司机不存在 |
| 409 | 司机仍被车辆绑定 |

### 4.27 GET `/admin/vehicles`

查询未软删除的车辆档案列表，包含当前司机和运行位置字段。

响应示例：

```json
{
  "vehicles": []
}
```

### 4.28 POST `/admin/vehicles`

创建离线车辆档案。`vehicle_code` 是车辆业务身份字段，创建后不可修改；`plate_no` 遵循数据库唯一约束，冲突返回 `409`。新增车辆时 `operation_status` 必须为 `offline`，不能携带 `initial_position`；车辆创建后调用 `POST /admin/vehicles/<vehicle_code>/status` 切换为 `operating`，车辆才会进入运行车队并参与运营。司机绑定为可选项。

请求体：

```json
{
  "vehicle_code": "bus-001",
  "plate_no": "粤A00001",
  "vehicle_type": "bus",
  "seat_count": 10,
  "max_load_count": 10,
  "operation_area_id": 10001,
  "vehicle_color": "#64748b",
  "vehicle_model": "EV-BUS",
  "operation_status": "offline",
  "operation_mode": "dynamic_bus",
  "current_driver_code": "driver-001",
  "remark": ""
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `vehicle_code` | string | 是 | 车辆业务编码，创建后不可修改 |
| `plate_no` | string | 是 | 车牌号，同租户下唯一 |
| `vehicle_type` | string | 否 | 车辆类型，见 `/admin/driver-vehicle/options` |
| `seat_count` | integer | 是 | 座位数，必须为正整数 |
| `max_load_count` | integer | 是 | 核载人数，必须为正整数 |
| `operation_area_id` | integer | 否 | 车辆所属运营区业务 ID，对应 `map_operation_area.area_id`；切换为可运行状态时必须归属到已加载运营区 |
| `vehicle_color` | string | 否 | 车辆展示颜色 |
| `vehicle_model` | string | 否 | 车辆型号 |
| `operation_status` | string | 是 | 新增车辆时必须为 `offline` |
| `operation_mode` | string | 否 | 运营模式，默认 `dynamic_bus`，可选值有： `dynamic_bus`、`commute_fixed_waiting`、`commute_cruising` |
| `current_driver_code` | string/null | 否 | 当前绑定司机编码；同一个司机只能绑定一台未删除车辆 |
| `remark` | string | 否 | 备注 |

`POST /admin/vehicles` 不接收车辆初始位置。需要让车辆开始运营时，调用 `POST /admin/vehicles/<vehicle_code>/status` 并传 `operation_status=operating` 与车辆当前位置；可按需提前或之后绑定司机。

车辆管理接口只接受 `operation_area_id` 表示车辆所属运营区，不再接受 `operation_area_code` 或 `area_code` 作为车辆归属输入；如继续传入会返回 `400`。

成功响应：

```json
{
  "vehicle": {},
  "runtime": {
    "runtime_applied": true,
    "runtime_action": "removed"
  },
  "snap": null
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 201 | 创建成功 |
| 400 | 参数错误、`operation_status` 不是 `offline`、缺少座位数/核载人数或创建时传入位置 |
| 409 | 车牌号等唯一字段冲突 |

### 4.29 GET `/admin/vehicles/<vehicle_id>`

查询单个车辆档案。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `vehicle_id` | string | 车辆业务ID |

成功响应：

```json
{
  "vehicle": {}
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 查询成功 |
| 404 | 车辆不存在 |

### 4.30 PUT `/admin/vehicles/<vehicle_id>`

更新车辆档案并按运营状态同步运行车队。`vehicle_id` 以路径参数为准，请求体中的 `vehicle_id` 会被忽略。

请求体：同 `POST /admin/vehicles`，并根据 `operation_mode` 增加以下规则：

- `operation_mode="dynamic_bus"`：保持普通动态巴士逻辑，不需要 `line_code`。
- `operation_mode="commute_fixed_waiting"` 或 `operation_mode="commute_cruising"`：必须额外传入 `line_code`，后端会复用通勤快线车辆绑定逻辑，把车辆绑定到该快线线路。
- 快线模式下车辆 `operation_area_id` 会以后端查询到的线路所属运营区为准，请求体中的 `operation_area_id` 会被线路运营区覆盖。
- 车辆从快线模式改回 `dynamic_bus` 时，后端会停用该车辆旧的快线绑定关系。

快线车辆更新示例：

```json
{
  "plate_no": "粤A00001",
  "vehicle_type": "bus",
  "seat_count": 10,
  "max_load_count": 10,
  "vehicle_color": "#64748b",
  "vehicle_model": "EV-BUS",
  "operation_status": "operating",
  "operation_mode": "commute_fixed_waiting",
  "line_code": "line_001",
  "current_driver_code": "driver-001",
  "initial_position": {
    "lon": 113.1,
    "lat": 23.1
  }
}
```

快线绑定成功时响应会额外返回：

```json
{
  "vehicle": {},
  "runtime": {},
  "snap": {},
  "commute_assignment": {
    "vehicle_code": "bus-001",
    "line_code": "line_001",
    "operation_area_id": 10001,
    "task_mode": "commute_fixed_waiting",
    "status": "active"
  },
  "commute_runtime_applied": true
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 更新成功 |
| 400 | 参数错误、状态枚举非法、快线模式缺少 `line_code` 或可运行车辆缺少位置 |
| 404 | 车辆不存在或快线线路不存在 |
| 409 | 车辆有未完成任务，不能退出运营 |

### 4.31 DELETE `/admin/vehicles/<vehicle_id>`

软删除车辆档案，并在可删除时从运行车队移除。如果车辆仍有 `on_board_orders` 或 `planned_route`，返回 `409`。

成功响应：

```json
{
  "status": "deleted",
  "vehicle_code": "bus-001"
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 删除成功 |
| 404 | 车辆不存在 |
| 409 | 车辆仍有未完成任务 |

### 4.32 POST `/admin/vehicles/<vehicle_id>/status`

更新车辆运营状态，并同步运行车队。

请求体：

```json
{
  "operation_status": "offline"
}
```

激活可运行状态时可以同时传当前位置；对于刚通过 `POST /admin/vehicles` 新增、尚无运行位置的离线车辆，切换为 `operating` 时必须传 `initial_position`，但不强制绑定司机：

如果传入 `operation_area_id`，车辆会归属到该运营区；切换为 `operating/resting/closing` 时，该运营区必须已经通过 `/init` 成功加载。车辆表只保存 `operation_area_id`，接口响应中的 `operation_area_code`、`operation_area_name`、`operation_area_org_code`、`operation_area_org_name` 均由 `map_operation_area` 关联得到。

该接口同样不再接受 `operation_area_code` 或 `area_code` 作为车辆归属输入。

```json
{
  "operation_status": "operating",
  "operation_area_id": 10001,
  "initial_position": {
    "lon": 113.4001,
    "lat": 23.0501
  }
}
```

状态规则：

| 状态 | 说明 |
| --- | --- |
| `operating` | 加入或更新运行车队，可参与派单；司机绑定为可选 |
| `resting` | 保留展示，但不接新单 |
| `closing` | 停止接新单，允许完成已有任务 |
| `offline` | 无任务时从运行车队移除，仅保留数据库档案 |
| `maintenance` | 无任务时从运行车队移除，仅保留数据库档案 |

成功响应：

```json
{
  "vehicle": {},
  "runtime": {
    "runtime_applied": true,
    "runtime_action": "removed"
  },
  "snap": null
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 状态更新成功 |
| 400 | 状态枚举非法或可运行车辆缺少位置 |
| 404 | 车辆不存在 |
| 409 | 车辆仍有未完成任务不能退出运营，或司机重复绑定 |

### 4.33 POST `/admin/vehicles/<vehicle_id>/bind-driver`

绑定或解绑车辆司机，并同步运行车队中的司机字段。同一个司机只能绑定一台未删除车辆；已处于 `operating` 的车辆也可以解绑司机，车辆会继续保持运营状态。

请求体，绑定司机：

```json
{
  "driver_code": "driver-001",
  "operator": "admin"
}
```

请求体，解绑司机：

```json
{
  "driver_code": null
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `driver_code` | string/null | 是 | 司机业务编码；传 `null` 或空字符串表示解绑 |
| `operator` | string/null | 否 | 操作人标识，用于绑定历史 |

成功响应：

```json
{
  "vehicle": {},
  "runtime": {
    "runtime_applied": true,
    "runtime_action": "updated"
  }
}
```

状态码：

| 状态码 | 场景 |
| --- | --- |
| 200 | 绑定或解绑成功 |
| 404 | 车辆不存在或司机不存在 |
| 409 | 司机已绑定其他车辆，或运营车辆尝试解绑司机 |

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

订单 ID 建议统一编码：

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
