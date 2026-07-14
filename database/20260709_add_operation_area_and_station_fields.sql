-- 根据《广工算法需求.docx》前两个示例表新增运营区表，并扩展 map_poi 站点字段。
-- 本迁移只调整数据库结构，不新增后端 API、不修改运行态逻辑。

CREATE TABLE IF NOT EXISTS `map_operation_area` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `area_id` bigint DEFAULT NULL COMMENT '区域ID',
  `org_id` bigint DEFAULT NULL COMMENT '机构ID',
  `dept_id` bigint DEFAULT NULL COMMENT '部门ID',
  `org_code` varchar(64) DEFAULT NULL COMMENT '机构编码',
  `org_name` varchar(100) DEFAULT NULL COMMENT '机构名称',
  `name` varchar(50) DEFAULT NULL COMMENT '区域名称',
  `code` varchar(20) DEFAULT NULL COMMENT '区域编码',
  `type` varchar(20) DEFAULT NULL COMMENT '区域类型',
  `status` varchar(20) NOT NULL DEFAULT 'pending' COMMENT '启用状态:pending/disabled/enabled/rejected',
  `area_control` text COMMENT '地理围栏数据',
  `area_type` varchar(50) DEFAULT NULL COMMENT '区域类型:服务区/限行区/站点覆盖区等',
  `city_code` varchar(64) DEFAULT NULL COMMENT '城市编码',
  `city_name` varchar(100) DEFAULT NULL COMMENT '城市名称',
  `county_code` varchar(64) DEFAULT NULL COMMENT '区县编码',
  `county_name` varchar(100) DEFAULT NULL COMMENT '区县名称',
  `area_shape` varchar(20) DEFAULT NULL COMMENT '区域形状:circle/polygon',
  `area_points` text COMMENT '区域坐标点',
  `area_polygon` text COMMENT '多边形数据',
  `area_center` varchar(100) DEFAULT NULL COMMENT '区域中心点',
  `area_radius` decimal(10,2) DEFAULT NULL COMMENT '区域半径(米)',
  `area_area` decimal(10,2) DEFAULT NULL COMMENT '区域面积(km²)',
  `nearest_station_distance` int DEFAULT NULL COMMENT '最近站点距离(米)',
  `surrounding_station_distance` int DEFAULT NULL COMMENT '周边站点距离(米)',
  `max_return_stops` int DEFAULT NULL COMMENT '最大返程站点数',
  `time_rule` varchar(50) DEFAULT NULL COMMENT '时间规则',
  `start_time` varchar(20) DEFAULT NULL COMMENT '开始时间',
  `end_time` varchar(20) DEFAULT NULL COMMENT '结束时间',
  `audit_status` varchar(20) NOT NULL DEFAULT 'pending' COMMENT '审核状态:pending/approved/rejected',
  `is_deleted` tinyint(1) NOT NULL DEFAULT 0 COMMENT '源系统是否删除:0否1是',
  `source_create_time` datetime DEFAULT NULL COMMENT '源系统创建时间',
  `tenant_id` varchar(32) NOT NULL DEFAULT '000000' COMMENT '租户ID',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '软删除:0否1是',
  PRIMARY KEY (`id`),
  KEY `idx_operation_area_area_id` (`tenant_id`, `area_id`, `deleted`),
  KEY `idx_operation_area_code` (`tenant_id`, `code`, `deleted`),
  KEY `idx_operation_area_status` (`tenant_id`, `status`, `audit_status`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='运营区表';

SET @schema_name := DATABASE();

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND index_name = 'idx_operation_area_area_id') = 0,
  'ALTER TABLE `map_operation_area` ADD INDEX `idx_operation_area_area_id` (`tenant_id`, `area_id`, `deleted`)',
  'SELECT ''map_operation_area.idx_operation_area_area_id exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND index_name = 'idx_operation_area_code') = 0,
  'ALTER TABLE `map_operation_area` ADD INDEX `idx_operation_area_code` (`tenant_id`, `code`, `deleted`)',
  'SELECT ''map_operation_area.idx_operation_area_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND index_name = 'idx_operation_area_status') = 0,
  'ALTER TABLE `map_operation_area` ADD INDEX `idx_operation_area_status` (`tenant_id`, `status`, `audit_status`, `deleted`)',
  'SELECT ''map_operation_area.idx_operation_area_status exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'station_id') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `station_id` bigint DEFAULT NULL COMMENT ''后台站点ID'' AFTER `id`',
  'SELECT ''map_poi.station_id exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'station_type') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `station_type` varchar(10) DEFAULT NULL COMMENT ''站点类型:0普通公交站/1总站/2虚拟站/3停车场/4临停点'' AFTER `poi_type`',
  'SELECT ''map_poi.station_type exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'station_direction') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `station_direction` varchar(10) DEFAULT NULL COMMENT ''站点方向:东/西/南/北'' AFTER `station_type`',
  'SELECT ''map_poi.station_direction exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'direction_angle') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `direction_angle` int DEFAULT NULL COMMENT ''方向角'' AFTER `station_direction`',
  'SELECT ''map_poi.direction_angle exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'areas') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `areas` varchar(100) DEFAULT NULL COMMENT ''所属区域'' AFTER `address`',
  'SELECT ''map_poi.areas exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'dept_id') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `dept_id` bigint DEFAULT NULL COMMENT ''部门ID'' AFTER `areas`',
  'SELECT ''map_poi.dept_id exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'org_code') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `org_code` varchar(64) DEFAULT NULL COMMENT ''机构编码'' AFTER `dept_id`',
  'SELECT ''map_poi.org_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'source_status') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `source_status` varchar(10) DEFAULT NULL COMMENT ''源系统状态:0启用/1停用'' AFTER `status`',
  'SELECT ''map_poi.source_status exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'audit_status') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `audit_status` varchar(20) DEFAULT NULL COMMENT ''审核状态:pending/approved/rejected'' AFTER `source_status`',
  'SELECT ''map_poi.audit_status exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'source_create_time') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `source_create_time` datetime DEFAULT NULL COMMENT ''源系统创建时间'' AFTER `audit_status`',
  'SELECT ''map_poi.source_create_time exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND index_name = 'idx_poi_station_id') = 0,
  'ALTER TABLE `map_poi` ADD INDEX `idx_poi_station_id` (`tenant_id`, `station_id`)',
  'SELECT ''map_poi.idx_poi_station_id exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND index_name = 'idx_poi_org_code') = 0,
  'ALTER TABLE `map_poi` ADD INDEX `idx_poi_org_code` (`tenant_id`, `org_code`)',
  'SELECT ''map_poi.idx_poi_org_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND index_name = 'idx_poi_audit_status') = 0,
  'ALTER TABLE `map_poi` ADD INDEX `idx_poi_audit_status` (`tenant_id`, `audit_status`)',
  'SELECT ''map_poi.idx_poi_audit_status exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
