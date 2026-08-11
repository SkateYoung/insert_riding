-- 通勤快线业务表
-- 说明：通勤快线独立于动态巴士订单池；订单复用 bus_order，并通过 order_source 区分。

CREATE TABLE IF NOT EXISTS `bus_commute_line` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `line_code` varchar(64) NOT NULL COMMENT '快线线路编码',
  `line_name` varchar(128) NOT NULL COMMENT '快线线路名称',
  `operation_area_id` bigint NOT NULL COMMENT '所属运营区area_id',
  `route_mode` varchar(32) NOT NULL DEFAULT 'loop' COMMENT '线路模式:loop单向循环',
  `status` varchar(32) NOT NULL DEFAULT 'enabled' COMMENT '线路状态:enabled/disabled',
  `stops_json` json DEFAULT NULL COMMENT '线路站点顺序快照，来源于map_poi',
  `stop_count` int NOT NULL DEFAULT 0 COMMENT '线路站点数量',
  `description` varchar(500) DEFAULT NULL COMMENT '线路说明',
  `tenant_id` varchar(32) NOT NULL DEFAULT '000000' COMMENT '租户ID',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '软删除:0否1是',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_commute_line_code` (`tenant_id`, `line_code`, `deleted`),
  KEY `idx_commute_line_area` (`tenant_id`, `operation_area_id`, `status`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='通勤快线线路主表';

CREATE TABLE IF NOT EXISTS `bus_commute_vehicle_assignment` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `vehicle_code` varchar(64) NOT NULL COMMENT '车辆业务ID',
  `line_code` varchar(64) NOT NULL COMMENT '快线线路编码',
  `operation_area_id` bigint NOT NULL COMMENT '所属运营区area_id',
  `task_mode` varchar(32) NOT NULL COMMENT '任务模式:commute_fixed_waiting/commute_cruising',
  `anchor_poi_id` bigint DEFAULT NULL COMMENT '定点候客锚点站点map_poi.id快照',
  `anchor_lon` decimal(11,8) DEFAULT NULL COMMENT '定点候客锚点经度快照',
  `anchor_lat` decimal(10,8) DEFAULT NULL COMMENT '定点候客锚点纬度快照',
  `status` varchar(32) NOT NULL DEFAULT 'active' COMMENT '绑定状态:active/disabled',
  `tenant_id` varchar(32) NOT NULL DEFAULT '000000' COMMENT '租户ID',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '软删除:0否1是',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_commute_vehicle_assignment` (`tenant_id`, `vehicle_code`, `deleted`),
  KEY `idx_commute_vehicle_assignment_line` (`tenant_id`, `line_code`, `status`, `deleted`),
  KEY `idx_commute_vehicle_assignment_mode` (`tenant_id`, `operation_area_id`, `task_mode`, `status`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='通勤快线车辆线路绑定表';
