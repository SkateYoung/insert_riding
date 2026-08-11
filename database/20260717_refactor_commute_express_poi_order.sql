-- 通勤快线按 map_poi 经纬度站点与 bus_order 复用改造
-- 说明：
-- 1. 线路站点顺序从 bus_commute_line_stop 迁移到 bus_commute_line.stops_json。
-- 2. 快线订单从 bus_commute_order 迁移到 bus_order，order_source='commute_express'。
-- 3. 车辆绑定锚点从 anchor_stop_seq 改为 anchor_poi_id/anchor_lon/anchor_lat。

SET @schema_name := DATABASE();

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name AND TABLE_NAME='bus_commute_line' AND COLUMN_NAME='stops_json'
);
SET @sql := IF(
  @column_exists=0,
  'ALTER TABLE `bus_commute_line` ADD COLUMN `stops_json` json DEFAULT NULL COMMENT ''线路站点顺序快照，来源于map_poi'' AFTER `status`',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name AND TABLE_NAME='bus_commute_line' AND COLUMN_NAME='stop_count'
);
SET @sql := IF(
  @column_exists=0,
  'ALTER TABLE `bus_commute_line` ADD COLUMN `stop_count` int NOT NULL DEFAULT 0 COMMENT ''线路站点数量'' AFTER `stops_json`',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name AND TABLE_NAME='bus_commute_vehicle_assignment' AND COLUMN_NAME='anchor_poi_id'
);
SET @sql := IF(
  @column_exists=0,
  'ALTER TABLE `bus_commute_vehicle_assignment` ADD COLUMN `anchor_poi_id` bigint DEFAULT NULL COMMENT ''定点候客锚点站点map_poi.id快照'' AFTER `task_mode`',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name AND TABLE_NAME='bus_commute_vehicle_assignment' AND COLUMN_NAME='anchor_lon'
);
SET @sql := IF(
  @column_exists=0,
  'ALTER TABLE `bus_commute_vehicle_assignment` ADD COLUMN `anchor_lon` decimal(11,8) DEFAULT NULL COMMENT ''定点候客锚点经度快照'' AFTER `anchor_poi_id`',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name AND TABLE_NAME='bus_commute_vehicle_assignment' AND COLUMN_NAME='anchor_lat'
);
SET @sql := IF(
  @column_exists=0,
  'ALTER TABLE `bus_commute_vehicle_assignment` ADD COLUMN `anchor_lat` decimal(10,8) DEFAULT NULL COMMENT ''定点候客锚点纬度快照'' AFTER `anchor_lon`',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_line_stop := (
  SELECT COUNT(*)
  FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=@schema_name AND TABLE_NAME='bus_commute_line_stop'
);

SET @sql := IF(
  @has_line_stop=1,
  'UPDATE `bus_commute_line` l
   JOIN (
     SELECT s.tenant_id, s.line_code,
            CONCAT(''['', GROUP_CONCAT(
              JSON_OBJECT(
                ''poi_id'', p.id,
                ''poi_code'', COALESCE(p.poi_code, s.poi_code),
                ''station_name'', COALESCE(p.poi_name, s.station_name),
                ''lon'', COALESCE(p.longitude, s.longitude),
                ''lat'', COALESCE(p.latitude, s.latitude),
                ''longitude'', COALESCE(p.longitude, s.longitude),
                ''latitude'', COALESCE(p.latitude, s.latitude),
                ''node_code'', COALESCE(p.node_code, s.node_code),
                ''line_order'', s.stop_seq
              )
              ORDER BY s.stop_seq SEPARATOR '',''
            ), '']'') AS stops_json,
            COUNT(*) AS stop_count
     FROM `bus_commute_line_stop` s
     LEFT JOIN `map_poi` p
       ON p.tenant_id=s.tenant_id
      AND p.operation_area_id=s.operation_area_id
      AND p.longitude=s.longitude
      AND p.latitude=s.latitude
      AND p.deleted=0
      AND p.status=''enabled''
     WHERE s.deleted=0
     GROUP BY s.tenant_id, s.line_code
   ) x ON x.tenant_id=l.tenant_id AND x.line_code=l.line_code
   SET l.stops_json=x.stops_json,
       l.stop_count=x.stop_count,
       l.updated_at=CURRENT_TIMESTAMP(3)',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  @has_line_stop=1,
  'UPDATE `bus_commute_vehicle_assignment` a
   JOIN `bus_commute_line_stop` s
     ON s.tenant_id=a.tenant_id
    AND s.line_code=a.line_code
    AND s.stop_seq=a.anchor_stop_seq
    AND s.deleted=0
   LEFT JOIN `map_poi` p
     ON p.tenant_id=s.tenant_id
    AND p.operation_area_id=s.operation_area_id
    AND p.longitude=s.longitude
    AND p.latitude=s.latitude
    AND p.deleted=0
    AND p.status=''enabled''
   SET a.anchor_poi_id=p.id,
       a.anchor_lon=COALESCE(p.longitude, s.longitude),
       a.anchor_lat=COALESCE(p.latitude, s.latitude),
       a.updated_at=CURRENT_TIMESTAMP(3)
   WHERE a.deleted=0',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_commute_order := (
  SELECT COUNT(*)
  FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=@schema_name AND TABLE_NAME='bus_commute_order'
);

SET @sql := IF(
  @has_commute_order=1,
  'INSERT INTO `bus_order`
     (request_id, passenger_code, passenger_phone, passenger_count, order_source,
      operation_area_id, status, origin_lon, origin_lat, destination_lon, destination_lat,
      origin_name, destination_name, request_time, assigned_vehicle_id, assigned_plate_no,
      answer_time, actual_pickup_time, completion_time, cancel_time, cancel_reason,
      route_status, route_segments, route_updated_at, tenant_id, created_at, updated_at, deleted)
   SELECT co.request_id, co.passenger_id, co.passenger_phone, co.passenger_count, ''commute_express'',
          co.operation_area_id, co.status,
          co.origin_lon, co.origin_lat, co.destination_lon, co.destination_lat,
          co.origin_station_name, co.destination_station_name,
          COALESCE(co.request_time, co.created_at),
          bv.id, co.assigned_plate_no,
          CASE WHEN co.status IN (''waiting_pickup'', ''riding'', ''completed'') THEN co.updated_at ELSE NULL END,
          co.pickup_time, co.dropoff_time, co.cancel_time, co.cancel_reason,
          NULL,
          JSON_OBJECT(''line_code'', co.line_code, ''route_poi_sequence'', co.route_stop_sequence),
          co.updated_at, co.tenant_id, co.created_at, co.updated_at, co.deleted
   FROM `bus_commute_order` co
   LEFT JOIN `bus_vehicle` bv
     ON bv.tenant_id=co.tenant_id
    AND bv.vehicle_code=co.assigned_vehicle_code
    AND bv.deleted=0
   LEFT JOIN `bus_order` existing
     ON existing.tenant_id=co.tenant_id
    AND existing.request_id=co.request_id
    AND existing.deleted=0
   WHERE existing.id IS NULL
     AND co.deleted=0
     AND co.origin_lon IS NOT NULL
     AND co.origin_lat IS NOT NULL
     AND co.destination_lon IS NOT NULL
     AND co.destination_lat IS NOT NULL',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name AND TABLE_NAME='bus_commute_vehicle_assignment' AND COLUMN_NAME='anchor_stop_seq'
);
SET @sql := IF(
  @column_exists=1,
  'ALTER TABLE `bus_commute_vehicle_assignment` DROP COLUMN `anchor_stop_seq`',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

DROP TABLE IF EXISTS `bus_commute_line_stop`;
DROP TABLE IF EXISTS `bus_commute_order`;
