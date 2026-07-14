-- 为站点按坐标删除补充查询索引，支持重复执行。
SET @schema_name = DATABASE();

SET @has_idx_poi_area_coordinate = (
  SELECT COUNT(1)
  FROM information_schema.statistics
  WHERE table_schema = @schema_name
    AND table_name = 'map_poi'
    AND index_name = 'idx_poi_area_coordinate'
);

SET @sql = IF(
  @has_idx_poi_area_coordinate = 0,
  'ALTER TABLE `map_poi` ADD INDEX `idx_poi_area_coordinate` (`tenant_id`, `operation_area_id`, `longitude`, `latitude`, `deleted`)',
  'SELECT ''map_poi.idx_poi_area_coordinate exists'''
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
