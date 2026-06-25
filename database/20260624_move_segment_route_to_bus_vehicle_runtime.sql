-- 将车辆高德纠偏分段路线从车辆档案表迁移到车辆运行快照表。
-- 目标：MySQL 8.0+，数据库 bus_dispatch_core。
USE `bus_dispatch_core`;

SET @add_runtime_segment_route_sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `bus_vehicle_runtime` ADD COLUMN `segment_route` JSON DEFAULT NULL COMMENT ''车辆当前高德纠偏分段路线，对应 planned_route_segment_grasped_point'' AFTER `planned_step_count`',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'bus_vehicle_runtime'
    AND column_name = 'segment_route'
);
PREPARE add_runtime_segment_route_stmt FROM @add_runtime_segment_route_sql;
EXECUTE add_runtime_segment_route_stmt;
DEALLOCATE PREPARE add_runtime_segment_route_stmt;

SET @insert_missing_runtime_sql = (
  SELECT IF(
    COUNT(*) > 0,
    'INSERT INTO `bus_vehicle_runtime`
       (`vehicle_id`, `driver_id`, `segment_route`, `rest_status`, `can_accept_order`, `reported_at`, `tenant_id`)
     SELECT v.`id`, v.`current_driver_id`, v.`segment_route`, ''operating'', 1, CURRENT_TIMESTAMP(3), v.`tenant_id`
     FROM `bus_vehicle` v
     LEFT JOIN `bus_vehicle_runtime` r
       ON r.`vehicle_id` = v.`id` AND r.`tenant_id` = v.`tenant_id` AND r.`deleted` = 0
     WHERE v.`deleted` = 0 AND v.`segment_route` IS NOT NULL AND r.`id` IS NULL',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'bus_vehicle'
    AND column_name = 'segment_route'
);
PREPARE insert_missing_runtime_stmt FROM @insert_missing_runtime_sql;
EXECUTE insert_missing_runtime_stmt;
DEALLOCATE PREPARE insert_missing_runtime_stmt;

SET @copy_segment_route_sql = (
  SELECT IF(
    COUNT(*) > 0,
    'UPDATE `bus_vehicle_runtime` r
     JOIN `bus_vehicle` v
       ON v.`id` = r.`vehicle_id` AND v.`tenant_id` = r.`tenant_id`
     SET r.`segment_route` = v.`segment_route`, r.`updated_at` = CURRENT_TIMESTAMP(3)
     WHERE v.`deleted` = 0 AND r.`deleted` = 0 AND v.`segment_route` IS NOT NULL',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'bus_vehicle'
    AND column_name = 'segment_route'
);
PREPARE copy_segment_route_stmt FROM @copy_segment_route_sql;
EXECUTE copy_segment_route_stmt;
DEALLOCATE PREPARE copy_segment_route_stmt;

SET @drop_vehicle_segment_route_sql = (
  SELECT IF(
    COUNT(*) > 0,
    'ALTER TABLE `bus_vehicle` DROP COLUMN `segment_route`',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'bus_vehicle'
    AND column_name = 'segment_route'
);
PREPARE drop_vehicle_segment_route_stmt FROM @drop_vehicle_segment_route_sql;
EXECUTE drop_vehicle_segment_route_stmt;
DEALLOCATE PREPARE drop_vehicle_segment_route_stmt;
