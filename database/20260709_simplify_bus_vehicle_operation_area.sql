-- 车辆表运营区归属精简：
-- 1. bus_vehicle.operation_area_id 保存 map_operation_area.area_id。
-- 2. 移除 bus_vehicle.operation_area_code、org_code、org_name 冗余字段。

SET @db_name = DATABASE();

SET @has_vehicle_operation_area_id = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_vehicle'
      AND COLUMN_NAME='operation_area_id'
);

SET @sql = IF(
    @has_vehicle_operation_area_id = 0,
    'ALTER TABLE bus_vehicle ADD COLUMN operation_area_id bigint DEFAULT NULL COMMENT ''所属运营区业务ID，对应map_operation_area.area_id'' AFTER operation_mode',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_vehicle_operation_area_code = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_vehicle'
      AND COLUMN_NAME='operation_area_code'
);

SET @sql = IF(
    @has_vehicle_operation_area_code > 0,
    'UPDATE bus_vehicle v
       JOIN map_operation_area a
         ON a.tenant_id=v.tenant_id
        AND a.code=v.operation_area_code
        AND a.deleted=0
        AND a.is_deleted=0
        AND a.area_id IS NOT NULL
      SET v.operation_area_id=a.area_id
      WHERE v.deleted=0
        AND v.operation_area_code IS NOT NULL
        AND v.operation_area_code<>''''',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_vehicle_operation_area = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_vehicle'
      AND INDEX_NAME='idx_vehicle_operation_area'
);

SET @sql = IF(
    @has_idx_vehicle_operation_area > 0,
    'ALTER TABLE bus_vehicle DROP INDEX idx_vehicle_operation_area',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_vehicle_org = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_vehicle'
      AND INDEX_NAME='idx_vehicle_org'
);

SET @sql = IF(
    @has_idx_vehicle_org > 0,
    'ALTER TABLE bus_vehicle DROP INDEX idx_vehicle_org',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_vehicle_operation_area_code = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_vehicle'
      AND COLUMN_NAME='operation_area_code'
);

SET @sql = IF(
    @has_vehicle_operation_area_code > 0,
    'ALTER TABLE bus_vehicle DROP COLUMN operation_area_code',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_vehicle_org_code = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_vehicle'
      AND COLUMN_NAME='org_code'
);

SET @sql = IF(
    @has_vehicle_org_code > 0,
    'ALTER TABLE bus_vehicle DROP COLUMN org_code',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_vehicle_org_name = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_vehicle'
      AND COLUMN_NAME='org_name'
);

SET @sql = IF(
    @has_vehicle_org_name > 0,
    'ALTER TABLE bus_vehicle DROP COLUMN org_name',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_vehicle_operation_area = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_vehicle'
      AND INDEX_NAME='idx_vehicle_operation_area'
);

SET @sql = IF(
    @has_idx_vehicle_operation_area = 0,
    'ALTER TABLE bus_vehicle ADD INDEX idx_vehicle_operation_area (tenant_id, operation_area_id, operation_status, deleted)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
