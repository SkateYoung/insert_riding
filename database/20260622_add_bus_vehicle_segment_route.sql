ALTER TABLE bus_vehicle
  ADD COLUMN segment_route JSON DEFAULT NULL
  COMMENT '车辆当前高德纠偏分段路线，对应 planned_route_segment_grasped_point'
  AFTER current_driver_id;
