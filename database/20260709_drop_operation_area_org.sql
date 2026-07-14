-- 当前业务采用“一个运营区对应一个 SHP、暂时一个运营区一家公司运营”的模型。
-- 因此移除多公司关系表 map_operation_area_org；运营区所属公司直接使用 map_operation_area.org_code/org_name。

DROP TABLE IF EXISTS `map_operation_area_org`;
