-- 撤销通勤快线车辆绑定 vehicle_id 改造
-- 说明：
-- 1. 将 bus_commute_vehicle_assignment 恢复为使用 vehicle_code 保存车辆业务编码。
-- 2. 如当前表中只有 vehicle_id，则按 bus_vehicle.id 反查 vehicle_code 后回填。
-- 3. 本脚本使用 information_schema 判断字段、索引和外键是否存在，可重复执行。

SET @schema_name := DATABASE();

SET @has_assignment_table := (
  SELECT COUNT(*)
  FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
);

SET @has_fk := (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND CONSTRAINT_NAME='fk_commute_assignment_vehicle'
);
SET @sql := IF(
  @has_assignment_table=1 AND @has_fk>0,
  'ALTER TABLE `bus_commute_vehicle_assignment` DROP FOREIGN KEY `fk_commute_assignment_vehicle`',
  'SELECT ''fk_commute_assignment_vehicle already removed or table missing'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_vehicle_code := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND COLUMN_NAME='vehicle_code'
);
SET @sql := IF(
  @has_assignment_table=1 AND @has_vehicle_code=0,
  'ALTER TABLE `bus_commute_vehicle_assignment` ADD COLUMN `vehicle_code` varchar(64) NULL COMMENT ''车辆业务ID'' AFTER `id`',
  'SELECT ''vehicle_code already exists or table missing'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_vehicle_id := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND COLUMN_NAME='vehicle_id'
);
SET @vehicle_id_data_type := (
  SELECT DATA_TYPE
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND COLUMN_NAME='vehicle_id'
  LIMIT 1
);
SET @sql := IF(
  @has_assignment_table=1 AND @has_vehicle_id=1 AND @vehicle_id_data_type='bigint',
  'UPDATE `bus_commute_vehicle_assignment` a
   JOIN `bus_vehicle` v
     ON v.tenant_id=a.tenant_id
    AND v.id=a.vehicle_id
    AND v.deleted=0
   SET a.vehicle_code=v.vehicle_code
   WHERE (a.vehicle_code IS NULL OR a.vehicle_code='''')',
  'SELECT ''vehicle_id bigint source unavailable'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  @has_assignment_table=1 AND @has_vehicle_id=1 AND @vehicle_id_data_type<>'bigint',
  'UPDATE `bus_commute_vehicle_assignment`
   SET vehicle_code=CAST(vehicle_id AS CHAR)
   WHERE (vehicle_code IS NULL OR vehicle_code='''')
     AND vehicle_id IS NOT NULL
     AND CAST(vehicle_id AS CHAR)<>''''',
  'SELECT ''vehicle_id text source unavailable'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @unresolved_count := 0;
SET @sql := IF(
  @has_assignment_table=1,
  'SELECT COUNT(*) INTO @unresolved_count
   FROM `bus_commute_vehicle_assignment`
   WHERE vehicle_code IS NULL OR vehicle_code=''''',
  'SELECT 0 INTO @unresolved_count'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  @unresolved_count>0,
  'SIGNAL SQLSTATE ''45000'' SET MESSAGE_TEXT=''bus_commute_vehicle_assignment has unresolved vehicle_code records''',
  'SELECT ''all assignment vehicle codes resolved'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_unique := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND INDEX_NAME='uk_commute_vehicle_assignment'
);
SET @sql := IF(
  @has_assignment_table=1 AND @has_unique>0,
  'ALTER TABLE `bus_commute_vehicle_assignment` DROP INDEX `uk_commute_vehicle_assignment`',
  'SELECT ''uk_commute_vehicle_assignment already removed or table missing'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_vehicle_idx := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND INDEX_NAME='idx_commute_vehicle_assignment_vehicle'
);
SET @sql := IF(
  @has_assignment_table=1 AND @has_vehicle_idx>0,
  'ALTER TABLE `bus_commute_vehicle_assignment` DROP INDEX `idx_commute_vehicle_assignment_vehicle`',
  'SELECT ''idx_commute_vehicle_assignment_vehicle already removed or table missing'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_vehicle_id := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND COLUMN_NAME='vehicle_id'
);
SET @sql := IF(
  @has_assignment_table=1 AND @has_vehicle_id=1,
  'ALTER TABLE `bus_commute_vehicle_assignment` DROP COLUMN `vehicle_id`',
  'SELECT ''vehicle_id already removed or table missing'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  @has_assignment_table=1,
  'ALTER TABLE `bus_commute_vehicle_assignment` MODIFY COLUMN `vehicle_code` varchar(64) NOT NULL COMMENT ''车辆业务ID''',
  'SELECT ''assignment table missing'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_unique := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=@schema_name
    AND TABLE_NAME='bus_commute_vehicle_assignment'
    AND INDEX_NAME='uk_commute_vehicle_assignment'
);
SET @sql := IF(
  @has_assignment_table=1 AND @has_unique=0,
  'ALTER TABLE `bus_commute_vehicle_assignment` ADD UNIQUE KEY `uk_commute_vehicle_assignment` (`tenant_id`, `vehicle_code`, `deleted`)',
  'SELECT ''uk_commute_vehicle_assignment already exists or table missing'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
