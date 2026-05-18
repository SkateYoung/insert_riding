# test_sync.py
from api.models import CityGraph, Order, Vehicle
from api.core import CoreDispatcher

# 1. 启动数字路网引擎模型实例
print("🌍 正在加载路网...")
city = CityGraph("dxc_traffic_shp/dxc_rule.shp")

# 2. 分配运营配置、声明出勤车组队
z_start = city.pois[0]
v = Vehicle("全城穿梭唯一大巴", z_start, "#10b981", zone=z_start.zone)
fleet = [v]

print("\n--- 测试场景 1: 空闲车指派 (应该立即成功，不受 10k 阈值限制) ---")
# 选取一个较远的节点作为起点
far_node = city.pois[-1]
o1 = Order(1, far_node.lon, far_node.lat, city.pois[5].lon, city.pois[5].lat, req_time=0.0, city_map=city)

status = CoreDispatcher.pool_and_route_planning(fleet, o1, city)
print(f"订单 1 指派结果: {'成功' if status else '失败 (进入池)'}")
print(f"车辆计划路径长度: {len(v.planned_route)}")

print("\n--- 测试场景 2: 忙碌车绕路判定 (应该进入订单池) ---")
# 选取一个非常不顺路的订单
o2 = Order(2, city.pois[10].lon, city.pois[10].lat, city.pois[11].lon, city.pois[11].lat, req_time=0.0, city_map=city)

status = CoreDispatcher.pool_and_route_planning(fleet, o2, city)
print(f"订单 2 指派结果: {'成功' if status else '失败 (进入池)'}")
print(f"订单池大小: {len(CoreDispatcher.order_pool)}")

print("\n--- 测试场景 3: 模拟车辆任务完成，打捞池中订单 ---")
# 清空车辆路径
v.planned_route = []
v.on_board_orders = []

# 执行打捞引擎
CoreDispatcher.process_pool_matching(fleet, city)
print(f"打捞后订单池大小: {len(CoreDispatcher.order_pool)}")
print(f"车辆最终路径长度: {len(v.planned_route)}")
