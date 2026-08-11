-- 通勤快线车辆绑定去除锚点站字段
-- 说明：
-- 1. commute_fixed_waiting 与 commute_cruising 均使用车辆 GPS 作为匹配当前位置。
-- 2. bus_commute_vehicle_assignment 不再保存 anchor_poi_id、anchor_lon、anchor_lat。
-- 3. 本脚本使用 information_schema 判断字段是否存在，可重复执行。

SET @schema_name := DATABASE();

SET @has_anchor_poi_id := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND COLUMN_NAME='anchor_poi_id'
);
SET @sql := IF(
  @has_anchor_poi_id=1,
  'ALTER TABLE `bus_commute_vehicle_assignment` DROP COLUMN `anchor_poi_id`',
  'SELECT ''anchor_poi_id already removed'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_anchor_lon := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND COLUMN_NAME='anchor_lon'
);
SET @sql := IF(
  @has_anchor_lon=1,
  'ALTER TABLE `bus_commute_vehicle_assignment` DROP COLUMN `anchor_lon`',
  'SELECT ''anchor_lon already removed'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_anchor_lat := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND COLUMN_NAME='anchor_lat'
);
SET @sql := IF(
  @has_anchor_lat=1,
  'ALTER TABLE `bus_commute_vehicle_assignment` DROP COLUMN `anchor_lat`',
  'SELECT ''anchor_lat already removed'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
