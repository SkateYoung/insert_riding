-- 订单表运营区归属精简：
-- 1. bus_order.operation_area_id 保存 map_operation_area.area_id。
-- 2. 移除 bus_order.operation_area_code 冗余字段。

SET @db_name = DATABASE();

SET @has_order_operation_area_id = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_order'
      AND COLUMN_NAME='operation_area_id'
);

SET @sql = IF(
    @has_order_operation_area_id = 0,
    'ALTER TABLE bus_order ADD COLUMN operation_area_id bigint DEFAULT NULL COMMENT ''所属运营区业务ID，对应map_operation_area.area_id'' AFTER order_source',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_order_operation_area_code = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_order'
      AND COLUMN_NAME='operation_area_code'
);

SET @sql = IF(
    @has_order_operation_area_code > 0,
    'UPDATE bus_order o
       JOIN map_operation_area a
         ON a.tenant_id=o.tenant_id
        AND a.code=o.operation_area_code
        AND a.deleted=0
        AND a.is_deleted=0
        AND a.area_id IS NOT NULL
      SET o.operation_area_id=a.area_id
      WHERE o.deleted=0
        AND (o.operation_area_id IS NULL OR o.operation_area_id=0)
        AND o.operation_area_code IS NOT NULL
        AND o.operation_area_code<>''''',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    @has_order_operation_area_id > 0,
    'UPDATE bus_order o
       JOIN map_operation_area a
         ON a.tenant_id=o.tenant_id
        AND a.id=o.operation_area_id
        AND a.deleted=0
        AND a.is_deleted=0
        AND a.area_id IS NOT NULL
      SET o.operation_area_id=a.area_id
      WHERE o.deleted=0
        AND o.operation_area_id IS NOT NULL
        AND o.operation_area_id<>a.area_id',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_order_operation_area_created = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_order'
      AND INDEX_NAME='idx_order_operation_area_created'
);

SET @sql = IF(
    @has_idx_order_operation_area_created > 0,
    'ALTER TABLE bus_order DROP INDEX idx_order_operation_area_created',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_order_operation_area_status = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_order'
      AND INDEX_NAME='idx_order_operation_area_status'
);

SET @sql = IF(
    @has_idx_order_operation_area_status > 0,
    'ALTER TABLE bus_order DROP INDEX idx_order_operation_area_status',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_order_operation_area_code = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_order'
      AND COLUMN_NAME='operation_area_code'
);

SET @sql = IF(
    @has_order_operation_area_code > 0,
    'ALTER TABLE bus_order DROP COLUMN operation_area_code',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE bus_order MODIFY COLUMN operation_area_id bigint DEFAULT NULL COMMENT '所属运营区业务ID，对应map_operation_area.area_id';

SET @has_idx_order_operation_area_created = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_order'
      AND INDEX_NAME='idx_order_operation_area_created'
);

SET @sql = IF(
    @has_idx_order_operation_area_created = 0,
    'ALTER TABLE bus_order ADD INDEX idx_order_operation_area_created (tenant_id, operation_area_id, created_at)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_order_operation_area_status = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_order'
      AND INDEX_NAME='idx_order_operation_area_status'
);

SET @sql = IF(
    @has_idx_order_operation_area_status = 0,
    'ALTER TABLE bus_order ADD INDEX idx_order_operation_area_status (tenant_id, operation_area_id, status, request_time)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
