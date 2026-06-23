-- 将运营禁区策略唯一约束从策略编号调整为策略名称，允许策略编号重复。
-- 只约束未软删除策略的名称唯一，历史软删除同名策略不参与唯一性。
-- 目标：MySQL 8.0+，数据库 bus_dispatch_core。

USE `bus_dispatch_core`;

SET @drop_code_index_sql = (
  SELECT IF(
    COUNT(*) > 0,
    'ALTER TABLE `bus_operation_restriction_policy` DROP INDEX `uk_operation_restriction_policy_code`',
    'SELECT 1'
  )
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'bus_operation_restriction_policy'
    AND index_name = 'uk_operation_restriction_policy_code'
);
PREPARE drop_code_index_stmt FROM @drop_code_index_sql;
EXECUTE drop_code_index_stmt;
DEALLOCATE PREPARE drop_code_index_stmt;

SET @add_name_index_sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `bus_operation_restriction_policy` ADD COLUMN `active_policy_name` varchar(128) GENERATED ALWAYS AS (CASE WHEN `deleted` = 0 THEN `policy_name` ELSE NULL END) STORED COMMENT ''未删除策略名称唯一索引用生成列''',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'bus_operation_restriction_policy'
    AND column_name = 'active_policy_name'
);
PREPARE add_name_index_stmt FROM @add_name_index_sql;
EXECUTE add_name_index_stmt;
DEALLOCATE PREPARE add_name_index_stmt;

SET @drop_legacy_name_index_sql = (
  SELECT IF(
    COUNT(*) > 0,
    'ALTER TABLE `bus_operation_restriction_policy` DROP INDEX `uk_operation_restriction_policy_name`',
    'SELECT 1'
  )
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'bus_operation_restriction_policy'
    AND index_name = 'uk_operation_restriction_policy_name'
);
PREPARE drop_legacy_name_index_stmt FROM @drop_legacy_name_index_sql;
EXECUTE drop_legacy_name_index_stmt;
DEALLOCATE PREPARE drop_legacy_name_index_stmt;

ALTER TABLE `bus_operation_restriction_policy`
  ADD UNIQUE KEY `uk_operation_restriction_policy_name` (`tenant_id`, `active_policy_name`);
