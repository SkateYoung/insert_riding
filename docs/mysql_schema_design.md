# 企业级 MySQL 数据库设计

本文档描述动态公交调度项目的核心 MySQL 业务库设计。DDL 文件位于 `database/bus_dispatch_core.sql`，目标版本为 MySQL 8.0+，字符集为 `utf8mb4`。

## 设计目标

- 支撑司机、车辆、乘客、订单、POI、路网节点等基础业务数据。
- 支撑当前项目中的订单池、车辆路线、O/D 分段、高德纠偏路线、订单 ETA、空车热点 ETA 等算法结果持久化。
- 保持现有 Python 内存调度流程不变，数据库先作为企业级持久化和查询模型。
- 订单自身保存订单路线，方便乘客端和管理端按订单追溯从 O 点到 D 点的路线。

## 表分层

### 基础档案

| 表名 | 说明 |
| --- | --- |
| `sys_tenant` | 租户/运营主体。 |
| `bus_driver` | 司机基础档案，包含司机业务 ID、工号、姓名、手机号、准驾车型、工作状态。 |
| `bus_vehicle` | 车辆基础档案，包含车辆业务 ID、车牌、车型、座位数、核载人数、当前司机、运营状态。 |
| `bus_vehicle_driver_bind` | 司机和车辆绑定历史，用于交班、换车和追溯。 |
| `bus_passenger` | 乘客基础档案，包含乘客业务 ID、手机号、昵称、来源渠道、状态。 |

### 地图与运营点位

| 表名 | 说明 |
| --- | --- |
| `map_poi` | 上下客 POI、热点、停车点等运营点位。 |
| `map_road_node` | 路网节点，对应当前 `CityGraph.nodes_map` 中的节点。 |
| `bus_hotspot_forecast` | 空车热点预测结果，用于空车前往热点和热点 ETA 展示。 |

### 订单与调度

| 表名 | 说明 |
| --- | --- |
| `bus_order` | 订单主表，保存订单、ETA、订单路线和运行结果。 |
| `bus_dispatch_task` | 一次派单、重规划、取消重算或空车调度任务。 |
| `bus_dispatch_route_step` | 车辆后续 O/D 停靠序列，对应 `Vehicle.planned_route`。 |
| `bus_dispatch_route_segment` | 车辆路线分段，保存 O/D 或 IDLE 分段的原始路线、纠偏路线、ETA。 |

### 车辆运行态

| 表名 | 说明 |
| --- | --- |
| `bus_vehicle_runtime` | 车辆当前运行快照，对应 `/fleet` 和 `/fleet/<vehicle_id>` 里的实时状态。 |
| `bus_vehicle_location_log` | GPS 历史轨迹，建议数据量上来后按月分区或归档。 |
| `bus_vehicle_route_snapshot` | 整车路线快照，保存当前原始路线、纠偏总线和分段路线。 |
| `bus_driver_rest_request` | 司机休息/收车申请。 |

## 订单表路线字段

`bus_order` 除了订单主数据和 ETA 字段，还保存单个订单从 O 点到 D 点的路线：

| 字段 | 说明 |
| --- | --- |
| `route_version` | 订单路线版本，用于判断路线是否过期。 |
| `route_status` | 路线状态，建议取值 `pending/ready/error/stale`。 |
| `route_distance_m` | 订单路线总距离，单位米。 |
| `route_duration_s` | 订单路线预计耗时，单位秒。 |
| `raw_route_points` | 算法 A* 生成的订单原始路线点，JSON。 |
| `grasped_route_points` | 高德纠偏后的订单路线点，JSON。 |
| `route_segments` | 订单路线分段详情，JSON，可保存分段点列、距离、ETA、纠偏状态。 |
| `route_updated_at` | 订单路线最近更新时间。 |
| `route_error` | 路线生成或纠偏失败原因。 |

订单 ETA 字段继续保存在 `bus_order`：

| 字段 | 说明 |
| --- | --- |
| `estimated_arrival_time` | 预计接驾到达时间。 |
| `estimated_dropoff_time` | 预计送达时间。 |
| `estimated_arrival_eta_seconds` | 预计接驾 ETA 秒数。 |
| `estimated_dropoff_eta_seconds` | 预计送达 ETA 秒数。 |
| `eta_status` | ETA 状态。 |
| `eta_error` | ETA 错误信息。 |
| `eta_updated_at` | ETA 更新时间。 |

## 与当前内存模型的映射

| 当前对象/字段 | 推荐落库位置 |
| --- | --- |
| `CoreDispatcher.order_pool` | `bus_order.status = 'pooled'` |
| `CoreDispatcher.completed_orders_pool` | `bus_order.status = 'completed'` |
| `Vehicle.planned_route` | `bus_dispatch_route_step` |
| `Vehicle.planned_route_point` | `bus_vehicle_route_snapshot.raw_route_points` |
| `Vehicle.planned_route_grasped_point` | `bus_vehicle_route_snapshot.grasped_route_points` |
| `Vehicle.planned_route_segment_grasped_point` | `bus_dispatch_route_segment.grasped_points` |
| `Vehicle.gps` | `bus_vehicle_runtime` 和 `bus_vehicle_location_log` |
| `Order.estimated_arrival_time` | `bus_order.estimated_arrival_time` |
| `Order.estimated_dropoff_time` | `bus_order.estimated_dropoff_time` |
| `Vehicle.idle_target` | `bus_vehicle_runtime.idle_target_*` |

## 状态枚举建议

订单状态：

- `created`
- `pooled`
- `matched`
- `waiting_pickup`
- `riding`
- `completed`
- `cancelled`
- `expired`

车辆运营状态：

- `offline`
- `idle`
- `serving`
- `closing`
- `resting`
- `maintenance`

纠偏状态：

- `pending`
- `ready`
- `error`
- `disabled`
- `stale`

ETA 状态：

- `pending`
- `loading`
- `ready`
- `partial`
- `not_available`
- `eta_error`
- `disabled`

## 索引策略

- 订单查询以 `request_id`、`status + request_time`、`assigned_vehicle_id + status` 为主。
- 车辆实时状态用 `bus_vehicle_runtime(vehicle_id)` 唯一索引。
- GPS 历史轨迹用 `bus_vehicle_location_log(vehicle_id, report_time)` 支撑按车按时间查询。
- 车辆计划路线用 `bus_dispatch_route_step(vehicle_id, route_version, sequence_no)` 保证顺序稳定。
- 车辆纠偏路线用 `bus_dispatch_route_segment(vehicle_id, route_version, segment_index)` 保证分段顺序稳定。
- POI 检索用 `map_poi(zone, status)` 和经纬度索引。

## 后续接入建议

1. 第一阶段只写入订单、车辆运行快照、GPS 历史和路线快照，不改变现有派单逻辑。
2. 第二阶段把派单任务和路线步骤落库，用于算法回放和问题排查。
3. GPS 历史属于高频写入表，数据量上来后再做按月分区或冷热归档。
