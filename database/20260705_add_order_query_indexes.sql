ALTER TABLE bus_order
  ADD INDEX idx_order_passenger_phone_created (tenant_id, passenger_phone, created_at),
  ADD INDEX idx_order_created_at (tenant_id, created_at),
  ADD INDEX idx_order_plate_created (tenant_id, assigned_plate_no, created_at);
