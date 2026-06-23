-- 新增运营禁区策略表，用于高德 avoidpolygons 与本地 A* 路径过滤。
-- 目标：MySQL 8.0+，数据库 bus_dispatch_core。

USE `bus_dispatch_core`;

CREATE TABLE IF NOT EXISTS `bus_operation_restriction_policy` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `policy_code` varchar(64) NOT NULL COMMENT '禁区策略业务编码，可重复',
  `policy_name` varchar(128) NOT NULL COMMENT '禁区策略名称，同租户下唯一',
  `description` varchar(500) DEFAULT NULL COMMENT '禁区策略说明',
  `polygons_json` json NOT NULL COMMENT '规范化后的禁区 polygon 列表',
  `amap_avoidpolygons` text NOT NULL COMMENT '高德驾车规划 avoidpolygons 参数值',
  `polygon_count` int NOT NULL DEFAULT 0 COMMENT '禁区 polygon 数量',
  `vertex_count` int NOT NULL DEFAULT 0 COMMENT '顶点总数',
  `total_area_km2` decimal(12,6) NOT NULL DEFAULT 0.000000 COMMENT '总面积，单位平方公里',
  `status` varchar(32) NOT NULL DEFAULT 'enabled' COMMENT '策略状态：enabled/disabled',
  `is_active` tinyint NOT NULL DEFAULT 0 COMMENT '是否为当前全局生效策略',
  `tenant_id` varchar(32) NOT NULL DEFAULT '000000' COMMENT '租户ID',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '软删除标记',
  `active_policy_name` varchar(128) GENERATED ALWAYS AS (CASE WHEN `deleted` = 0 THEN `policy_name` ELSE NULL END) STORED COMMENT '未删除策略名称唯一索引用生成列',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_operation_restriction_policy_name` (`tenant_id`, `active_policy_name`),
  KEY `idx_operation_restriction_policy_active` (`tenant_id`, `is_active`, `status`, `deleted`),
  KEY `idx_operation_restriction_policy_status` (`tenant_id`, `status`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='运营禁区策略表';
