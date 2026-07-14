-- 运营禁区策略按运营区生效改造。
-- operation_area_id 保存 map_operation_area.area_id；历史未绑定运营区策略保留但不再生效。
SET @db_name = DATABASE();

SET @has_restriction_operation_area_id = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_operation_restriction_policy'
      AND COLUMN_NAME='operation_area_id'
);

SET @sql = IF(
    @has_restriction_operation_area_id = 0,
    'ALTER TABLE bus_operation_restriction_policy ADD COLUMN operation_area_id bigint DEFAULT NULL COMMENT ''所属运营区area_id，对应map_operation_area.area_id'' AFTER description',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE bus_operation_restriction_policy
    MODIFY COLUMN operation_area_id bigint DEFAULT NULL COMMENT '所属运营区area_id，对应map_operation_area.area_id';

UPDATE bus_operation_restriction_policy
SET is_active=0, updated_at=CURRENT_TIMESTAMP(3)
WHERE operation_area_id IS NULL
  AND is_active=1;

UPDATE bus_operation_restriction_policy p
JOIN (
    SELECT tenant_id, operation_area_id, MAX(id) AS keep_id
    FROM bus_operation_restriction_policy
    WHERE operation_area_id IS NOT NULL
      AND deleted=0
      AND is_active=1
    GROUP BY tenant_id, operation_area_id
    HAVING COUNT(*) > 1
) d
  ON p.tenant_id=d.tenant_id
 AND p.operation_area_id=d.operation_area_id
SET p.is_active=0, p.updated_at=CURRENT_TIMESTAMP(3)
WHERE p.id<>d.keep_id;

SET @has_active_operation_area_id = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_operation_restriction_policy'
      AND COLUMN_NAME='active_operation_area_id'
);

SET @sql = IF(
    @has_active_operation_area_id = 0,
    'ALTER TABLE bus_operation_restriction_policy ADD COLUMN active_operation_area_id bigint GENERATED ALWAYS AS (CASE WHEN deleted = 0 AND is_active = 1 AND operation_area_id IS NOT NULL THEN operation_area_id ELSE NULL END) STORED COMMENT ''同运营区当前生效策略唯一索引用生成列''',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_restriction_policy_area = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_operation_restriction_policy'
      AND INDEX_NAME='idx_operation_restriction_policy_area'
);

SET @sql = IF(
    @has_idx_restriction_policy_area = 0,
    'ALTER TABLE bus_operation_restriction_policy ADD INDEX idx_operation_restriction_policy_area (tenant_id, operation_area_id, status, deleted)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_uk_restriction_active_area = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db_name
      AND TABLE_NAME='bus_operation_restriction_policy'
      AND INDEX_NAME='uk_operation_restriction_active_area'
);

SET @sql = IF(
    @has_uk_restriction_active_area = 0,
    'ALTER TABLE bus_operation_restriction_policy ADD UNIQUE KEY uk_operation_restriction_active_area (tenant_id, active_operation_area_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
