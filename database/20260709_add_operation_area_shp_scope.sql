-- 多运营区 SHP 地图模型数据库准备。
-- 一个运营区对应一个 SHP；路网节点、站点、车辆和订单均增加运营区归属字段。

SET @schema_name := DATABASE();

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'shp_path') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `shp_path` varchar(500) DEFAULT NULL COMMENT ''SHP文件路径'' AFTER `source_create_time`',
  'SELECT ''map_operation_area.shp_path exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'shp_name') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `shp_name` varchar(255) DEFAULT NULL COMMENT ''SHP文件名称'' AFTER `shp_path`',
  'SELECT ''map_operation_area.shp_name exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'shp_version') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `shp_version` varchar(64) DEFAULT NULL COMMENT ''SHP地图版本'' AFTER `shp_name`',
  'SELECT ''map_operation_area.shp_version exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'shp_hash') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `shp_hash` varchar(128) DEFAULT NULL COMMENT ''SHP文件哈希'' AFTER `shp_version`',
  'SELECT ''map_operation_area.shp_hash exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'shp_encoding') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `shp_encoding` varchar(32) DEFAULT ''utf-8'' COMMENT ''SHP/DBF编码'' AFTER `shp_hash`',
  'SELECT ''map_operation_area.shp_encoding exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'coord_system') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `coord_system` varchar(32) DEFAULT ''gcj02'' COMMENT ''坐标系:gcj02/wgs84/bd09'' AFTER `shp_encoding`',
  'SELECT ''map_operation_area.coord_system exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'load_on_startup') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `load_on_startup` tinyint NOT NULL DEFAULT 1 COMMENT ''系统启动时是否加载该运营区地图:0否1是'' AFTER `coord_system`',
  'SELECT ''map_operation_area.load_on_startup exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'load_status') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `load_status` varchar(32) NOT NULL DEFAULT ''pending'' COMMENT ''地图加载状态:pending/ready/error/disabled'' AFTER `load_on_startup`',
  'SELECT ''map_operation_area.load_status exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'load_error') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `load_error` varchar(1000) DEFAULT NULL COMMENT ''最近一次地图加载错误'' AFTER `load_status`',
  'SELECT ''map_operation_area.load_error exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'node_count') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `node_count` int DEFAULT NULL COMMENT ''路网节点数量'' AFTER `load_error`',
  'SELECT ''map_operation_area.node_count exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'edge_count') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `edge_count` int DEFAULT NULL COMMENT ''路网边数量'' AFTER `node_count`',
  'SELECT ''map_operation_area.edge_count exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'poi_count') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `poi_count` int DEFAULT NULL COMMENT ''POI数量'' AFTER `edge_count`',
  'SELECT ''map_operation_area.poi_count exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'bounds_json') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `bounds_json` json DEFAULT NULL COMMENT ''地图边界JSON:min_lon/max_lon/min_lat/max_lat'' AFTER `poi_count`',
  'SELECT ''map_operation_area.bounds_json exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND column_name = 'last_loaded_at') = 0,
  'ALTER TABLE `map_operation_area` ADD COLUMN `last_loaded_at` datetime(3) DEFAULT NULL COMMENT ''最近一次地图加载时间'' AFTER `bounds_json`',
  'SELECT ''map_operation_area.last_loaded_at exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND index_name = 'idx_operation_area_load') = 0,
  'ALTER TABLE `map_operation_area` ADD INDEX `idx_operation_area_load` (`tenant_id`, `load_on_startup`, `status`, `audit_status`, `deleted`)',
  'SELECT ''map_operation_area.idx_operation_area_load exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_operation_area' AND index_name = 'idx_operation_area_shp') = 0,
  'ALTER TABLE `map_operation_area` ADD INDEX `idx_operation_area_shp` (`tenant_id`, `shp_path`(191), `deleted`)',
  'SELECT ''map_operation_area.idx_operation_area_shp exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_road_node' AND column_name = 'operation_area_id') = 0,
  'ALTER TABLE `map_road_node` ADD COLUMN `operation_area_id` bigint DEFAULT NULL COMMENT ''所属运营区主键'' AFTER `id`',
  'SELECT ''map_road_node.operation_area_id exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_road_node' AND column_name = 'operation_area_code') = 0,
  'ALTER TABLE `map_road_node` ADD COLUMN `operation_area_code` varchar(64) NOT NULL DEFAULT '''' COMMENT ''所属运营区编码'' AFTER `operation_area_id`',
  'SELECT ''map_road_node.operation_area_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_road_node' AND index_name = 'uk_road_node_code') > 0,
  'ALTER TABLE `map_road_node` DROP INDEX `uk_road_node_code`',
  'SELECT ''map_road_node.uk_road_node_code absent'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_road_node' AND index_name = 'uk_road_node_area_code') = 0,
  'ALTER TABLE `map_road_node` ADD UNIQUE KEY `uk_road_node_area_code` (`tenant_id`, `operation_area_code`, `node_code`, `deleted`)',
  'SELECT ''map_road_node.uk_road_node_area_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_road_node' AND index_name = 'idx_road_node_operation_area') = 0,
  'ALTER TABLE `map_road_node` ADD INDEX `idx_road_node_operation_area` (`tenant_id`, `operation_area_code`, `status`)',
  'SELECT ''map_road_node.idx_road_node_operation_area exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'operation_area_id') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `operation_area_id` bigint DEFAULT NULL COMMENT ''所属运营区主键'' AFTER `id`',
  'SELECT ''map_poi.operation_area_id exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND column_name = 'operation_area_code') = 0,
  'ALTER TABLE `map_poi` ADD COLUMN `operation_area_code` varchar(64) NOT NULL DEFAULT '''' COMMENT ''所属运营区编码'' AFTER `operation_area_id`',
  'SELECT ''map_poi.operation_area_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND index_name = 'uk_poi_code') > 0,
  'ALTER TABLE `map_poi` DROP INDEX `uk_poi_code`',
  'SELECT ''map_poi.uk_poi_code absent'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND index_name = 'uk_poi_area_code') = 0,
  'ALTER TABLE `map_poi` ADD UNIQUE KEY `uk_poi_area_code` (`tenant_id`, `operation_area_code`, `poi_code`, `deleted`)',
  'SELECT ''map_poi.uk_poi_area_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'map_poi' AND index_name = 'idx_poi_operation_area') = 0,
  'ALTER TABLE `map_poi` ADD INDEX `idx_poi_operation_area` (`tenant_id`, `operation_area_code`, `status`)',
  'SELECT ''map_poi.idx_poi_operation_area exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'bus_vehicle' AND column_name = 'operation_area_id') = 0,
  'ALTER TABLE `bus_vehicle` ADD COLUMN `operation_area_id` bigint DEFAULT NULL COMMENT ''所属运营区主键'' AFTER `operation_mode`',
  'SELECT ''bus_vehicle.operation_area_id exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'bus_vehicle' AND column_name = 'operation_area_code') = 0,
  'ALTER TABLE `bus_vehicle` ADD COLUMN `operation_area_code` varchar(64) DEFAULT NULL COMMENT ''所属运营区编码'' AFTER `operation_area_id`',
  'SELECT ''bus_vehicle.operation_area_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'bus_vehicle' AND index_name = 'idx_vehicle_operation_area') = 0,
  'ALTER TABLE `bus_vehicle` ADD INDEX `idx_vehicle_operation_area` (`tenant_id`, `operation_area_code`, `operation_status`, `deleted`)',
  'SELECT ''bus_vehicle.idx_vehicle_operation_area exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'bus_order' AND column_name = 'operation_area_id') = 0,
  'ALTER TABLE `bus_order` ADD COLUMN `operation_area_id` bigint DEFAULT NULL COMMENT ''所属运营区主键'' AFTER `order_source`',
  'SELECT ''bus_order.operation_area_id exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = @schema_name AND table_name = 'bus_order' AND column_name = 'operation_area_code') = 0,
  'ALTER TABLE `bus_order` ADD COLUMN `operation_area_code` varchar(64) DEFAULT NULL COMMENT ''所属运营区编码'' AFTER `operation_area_id`',
  'SELECT ''bus_order.operation_area_code exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'bus_order' AND index_name = 'idx_order_operation_area_created') = 0,
  'ALTER TABLE `bus_order` ADD INDEX `idx_order_operation_area_created` (`tenant_id`, `operation_area_code`, `created_at`)',
  'SELECT ''bus_order.idx_order_operation_area_created exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @ddl := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = @schema_name AND table_name = 'bus_order' AND index_name = 'idx_order_operation_area_status') = 0,
  'ALTER TABLE `bus_order` ADD INDEX `idx_order_operation_area_status` (`tenant_id`, `operation_area_code`, `status`, `request_time`)',
  'SELECT ''bus_order.idx_order_operation_area_status exists'''
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
