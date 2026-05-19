# core.py
"""打车系统的大脑业务算子主控层。
负责派单、重组架构、以及闲置管控等绝对智能内核逻辑。
"""

import time
from datetime import datetime, timedelta
from .models import SPEED_MPS
from .auxiliary import AuxiliaryFunctions
from forecast import od_forecast_module

class CoreDispatcher:
    """提供拼单博弈算力与核心派车路线演算的中枢处理台。"""
    
    # 核心订单池：用于缓存由于运力爆满、或严重绕路(不顺路)而未能及时指派的订单。
    order_pool = []
    
    # [新增] 存放已完成、已结束（或已取消）订单的归档池，内部存储 Order 对象
    completed_orders_pool = []

    @staticmethod
    def evaluate_route(route, vehicle_state, on_board_orders, city_map, capacity=10, v_zone=None, original_etas=None):
        """核心评级器：沙盘量化时间线成本（Cost）以评估未来路线质量分数。
        
        该算法引入了由于车辆绕路等问题产生的物理油耗距离分数、乘客空等惩罚分，
        并在后续可以接入真正的 SLA 防止无限插队模型。
        
        Args:
            route (list): 一条排列好的装载字典列队（每项包含 'type': 'P'/'D', 和 'order' 对象）。
            vehicle_state (dict): 执行这段未来可能路线前的车辆状态副本，如目前开到了哪个节点坐标。
            on_board_orders (list): 该车上目前正被关着的已有乘客清单。
            city_map (CityGraph): 可以用于通过 A* 推算空间距离字典的数字路网基站。
            capacity (int, optional): 车辆容量限制。
            v_zone (int, optional): 本车本命所在的主行政区用于加成跨界拒载权重。
            original_etas (dict, optional): 插入新订单前老乘客的原计划预计到达时间字典，用于计算拼车真实延误。
            
        Returns:
            tuple: (可不可行分支True/False, 最终累计积分成本 float, 推演各订单到达时间字典 dict)。成本分越低代表路线越优。
        """
        speed = SPEED_MPS 
        sim_time = vehicle_state['time']
        sim_last_node = vehicle_state['last_node']
        sim_next_node = vehicle_state['next_node']
        
        current_load = len(on_board_orders)
        empty_dist = 0.0
        loaded_dist = 0.0
        
        first_step_dist = 0.0
        if sim_last_node != sim_next_node:
            pass_dist = city_map.nodes_map[sim_last_node].neighbors[sim_next_node]
            first_step_dist = pass_dist * (1.0 - vehicle_state['progress'])

        if current_load == 0:
            empty_dist += first_step_dist
        else:
            loaded_dist += first_step_dist
            
        sim_time += first_step_dist / speed
        
        pickup_times = {}
        arrival_times = {}
        cross_zone_penalty = 0.0
        
        for step in route:
            order = step['order']
            target_node = order.p_node if step['type'] == 'P' else order.d_node
            
            dist, path = city_map.get_path(city_map.nodes_map[sim_next_node], target_node)
            
            if dist == float('inf'):
                return False, float('inf'), None
                
            if current_load == 0:
                empty_dist += dist
            else:
                loaded_dist += dist
                
            sim_time += dist / speed
            sim_next_node = target_node.id
            
            if target_node.zone != v_zone:
                cross_zone_penalty += 300.0 
            
            if step['type'] == 'P':
                current_load += 1
                if current_load > capacity: 
                    return False, float('inf'), None 
                pickup_times[order.id] = sim_time
            elif step['type'] == 'D':
                current_load -= 1
                if current_load < 0:
                    return False, float('inf'), None
                arrival_times[order.id] = sim_time

        # ===== 终极综合多目标成本函数架构 (按最新四大维度重构) =====
        
        # 1. 权重定义 (严格按照需求配比)
        W_PASSENGER = 0.40  # 乘客体验 (候车时间、绕行系数、时间窗满意度)
        W_ENTERPRISE = 0.30 # 企业效益 (满载率、单车收入、里程利用率)
        W_SOCIAL = 0.20     # 社会效益 (区域覆盖率、碳排放、道路资源占用)
        W_FAIRNESS = 0.10   # 平台公平 (企业间订单分配基尼系数)

        # 核心调优参数
        BETA = 4.0       # 站牌下乘客枯等耗时体验折损
        GAMMA = 3.0      # 车内乘客被拉着绕路耗时体验折损 
        OMEGA = float('inf') # SLA 时间窗红线超额一票否决
        THETA = 1500.0       # 老客严重绕路的极限防背叛护盾
        
        # ---------------------------------------------------------
        # 维度 A: 乘客体验成本 (Passenger Cost)
        passenger_cost = 0.0
        for step in route:
            order = step['order']
            if step['type'] == 'P':
                wait_time = pickup_times[order.id] - order.req_time
                passenger_cost += wait_time * BETA # 乘客候车时间指标（BETA为候车时间成本系数，wait_time * BETA即是乘客候车时间成本）
                
                # 时间窗满意度：超出极限接客时间直接否决（暂定功能，因为实际订单中的信息没加入乘客愿意等待的最大时长）
                if pickup_times[order.id] > order.max_pickup_time:
                    return False, OMEGA, None
            else:
                start_service_time = pickup_times.get(order.id) or order.actual_pick_time or vehicle_state['time']
                in_car_time = arrival_times[order.id] - start_service_time
                passenger_cost += in_car_time * GAMMA # 绕行系数1（这里是统计所有订单中，乘客会在车上等待的时间成本）   
                
                # 时间窗满意度：超出极限送达时间直接否决
                if arrival_times[order.id] > order.max_arrival_time:
                    return False, OMEGA, None
            
        # 乘客体验：强制挂载老乘客被绕路的代价(真实的延误时间)
        for order in on_board_orders:
            for step in route:
                if step['type'] == 'D' and step['order'].id == order.id:
                    # 如果有原计划ETA，则仅惩罚真正多出来的老乘客的延误时间
                    if original_etas and order.id in original_etas:
                        delay_time = arrival_times[order.id] - original_etas[order.id]
                        if delay_time > 0:
                            passenger_cost += delay_time * GAMMA # 绕行系数2（这里是统计所有订单中，已经上车的老乘客被顺路绕行的额外时间成本）
                            if delay_time > 180.0:
                                passenger_cost += THETA
                    break

        # ---------------------------------------------------------
        # 维度 B: 企业效益成本 (Enterprise Cost)
        # 企业效益 = 绝对油耗开销 + 里程利用率惩罚 + 满载率惩罚
        
        total_sim_dist = empty_dist + loaded_dist
        
        # 1. 里程利用率 (Mileage Utilization Rate)：载客里程占比
        mileage_util_rate = loaded_dist / total_sim_dist if total_sim_dist > 0 else 0.0
        # 利用率越低，空跑越多，惩罚越大 (基数可根据业务放大)
        mileage_penalty = (1.0 - mileage_util_rate) * 1000.0
        
        # 2. 满载率 (Load Rate)：这里使用这趟路线服务的总客数占比作为满载率代理
        # (车上原有的 + 这趟新接的) / 最大容量
        total_pax = len(on_board_orders) + sum(1 for step in route if step['type'] == 'P')
        load_rate = min(1.0, total_pax / max(1, capacity))
        # 满载率越低（拉着一两座跑），效率越低，惩罚越大
        load_penalty = (1.0 - load_rate) * 800.0
        
        # 综合企业成本
        enterprise_cost =  mileage_penalty + load_penalty
        enterprise_cost = 0.0

        # ---------------------------------------------------------
        # 维度 C: 社会效益成本 (Social Cost)
        # 总体路权占用、碳排放总长以及跨区调度的惩罚
        total_dist = empty_dist + loaded_dist
        social_cost = total_dist * 1.0 + cross_zone_penalty
        social_cost = 0.0
        # ---------------------------------------------------------
        # 维度 D: 平台公平成本 (Fairness Cost) 
        # 代理基尼系数：当前车辆负载越大、车上已有订单越多，成本增加。
        # 目的是让派单系统更倾向于把新单分派给比较闲的车队/车辆，促进均衡分配。
        # fairness_cost = len(on_board_orders) * 500.0 
        fairness_cost = 0.0

        # ---------------------------------------------------------
        # 最终归一化加权求和 Cost
        cost = (W_PASSENGER * passenger_cost + 
                W_ENTERPRISE * enterprise_cost + 
                W_SOCIAL * social_cost + 
                W_FAIRNESS * fairness_cost)
        
        return True, cost, arrival_times

    @staticmethod
    def _try_insert_order(vehicle, new_order, city_map):
        """【组客内循环】：针对单车的贪婪性全路径缝隙插入探测寻优。
        
        该方法会尝试将新订单的 P 点和 D 点插入到现有计划路径的所有可能位置，并使用 evaluate_route 评估最优选。
        
        Args:
            vehicle (Vehicle): 目标评估车辆。
            new_order (Order): 需要尝试插入的新订单。
            city_map (CityGraph): 路网拓扑地图实例。
            
        Returns:
            tuple: (最优路径 list|None, 最优成本 float)
        """
        best_route = None
        best_cost = float('inf')
        route = vehicle.planned_route
        n = len(route)
        p_step = {'type': 'P', 'order': new_order}
        d_step = {'type': 'D', 'order': new_order}
        v_state = {
            'time': vehicle.time,
            'last_node': vehicle.last_node,
            'next_node': vehicle.next_node,
            'progress': vehicle.progress
        }
        
        # [新增] 在做任何尝试之前，先推演一次原路线，获取所有车上老乘客的原始 ETA
        orig_etas = None
        if vehicle.on_board_orders and route:
            _, _, orig_etas = CoreDispatcher.evaluate_route(route, v_state, vehicle.on_board_orders, city_map, vehicle.capacity, v_zone=vehicle.op_zone)
        
        for i in range(n + 1):
            temp_route = route[:i] + [p_step] + route[i:]
            for j in range(i + 1, n + 2):
                test_route = temp_route[:j] + [d_step] + temp_route[j:]
                
                is_feasible, cost, _ = CoreDispatcher.evaluate_route(test_route, v_state, vehicle.on_board_orders, city_map, vehicle.capacity, v_zone=vehicle.op_zone, original_etas=orig_etas)
                if is_feasible and cost < best_cost:
                    best_cost = cost
                    best_route = test_route
                    
        # ====== 2-Opt 突变反转寻优阶段 ======
        if best_route:
            improved = True
            safety = 50
            while improved and safety > 0:
                safety -= 1
                improved = False
                n_route = len(best_route)
                for i in range(n_route - 1):
                    for j in range(i + 1, n_route):
                        # 执行序列反转
                        mut_route = best_route[:]
                        sub = mut_route[i : j + 1]
                        sub.reverse()
                        mut_route[i : j + 1] = sub
                        
                        # 检查逻辑合规性：不能在接到人之前就送人
                        valid = True
                        seen_p = set()
                        on_board_ids = set(o.id for o in vehicle.on_board_orders)
                        
                        for step in mut_route:
                            oid = step['order'].id
                            if step['type'] == 'P':
                                seen_p.add(oid)
                            else:
                                if oid not in seen_p and oid not in on_board_ids:
                                    valid = False
                                    break
                        
                        if not valid:
                            continue
                            
                        # 评估新路径
                        is_feasible, cost, _ = CoreDispatcher.evaluate_route(mut_route, v_state, vehicle.on_board_orders, city_map, vehicle.capacity, v_zone=vehicle.op_zone, original_etas=orig_etas)
                        
                        # 若成本存在优化，立刻吸纳新的序列
                        if is_feasible and cost < (best_cost - 0.001):
                            best_cost = cost
                            best_route = mut_route
                            improved = True
                            break
                    if improved:
                        break
                        
        return best_route, best_cost

    @staticmethod
    def pool_and_route_planning(fleet, order, city_map):
        """【新流缓冲注池】：所有接驾呼叫全部强制沉降至缓冲池，等待周期性池化打捞。
        
        Args:
            fleet (list): 运营的所有车辆。
            order (Order): 需要被派发的单例客源订单数据。
            city_map (CityGraph): 地图数据。
            
        Returns:
            bool: 永远返回 False 表示进入池化，切断即时指派避免出现极度绕路。
        """
        print(f"[Core.Dispatcher] 新订单 [单{order.id}] 注入系统统筹池，等待匹配车辆中...")
        CoreDispatcher.order_pool.append(order)
        return False

    @staticmethod
    def process_pool_matching(fleet, city_map):
        """【订单池实时匹配引擎】：核心升级为主流【后悔值插入法】。
        
        该函数现在会以 5 秒为周期持续运行，实时监控订单池并进行统筹派发。

        Args:
            fleet (list[Vehicle]): 当前系统中的全部车辆对象。
            city_map (CityGraph): 用于评估路线成本和刷新轨迹的路网对象。

        Returns:
            None。该函数设计为后台常驻循环。

        Side Effects:
            持续消费 CoreDispatcher.order_pool。
            成功派单时写入车辆 planned_route/planned_route_point。
            订单池为空时会尝试触发空车停靠预测。
        """
        print("[Core.Pool] 订单池匹配引擎已启动，每 5 秒进行一轮后悔值统筹调度...")
        
        while True:
            if not CoreDispatcher.order_pool:
                print(f"[Core.Pool] 池中暂无订单...")
                if CoreDispatcher._collect_forecast_orders(fleet):
                    for v in fleet:
                        # 无订单时只对真正空闲且未休息的车辆下发热点停靠建议。
                        if (
                            len(v.on_board_orders) == 0
                            and len(v.planned_route) == 0
                            and not getattr(v, "is_rest_requested", False)
                            and not getattr(v, "is_resting", False)
                        ):
                            CoreDispatcher.idle_parking_scenario(v, city_map, fleet)
                time.sleep(5)
                continue
                
            print(f"[Core.Pool] 正在对池中 {len(CoreDispatcher.order_pool)} 个订单执行后悔值统筹调度...")
            
            assign_count = 0
            # 内部循环：在单次调度周期内尽可能排空订单池
            while CoreDispatcher.order_pool:
                best_o_idx = -1
                max_regret = -1.0
                global_best_v = None
                global_best_route = None
                
                # 评估池内的每一个被积压订单对目前场上所有车辆的组合差价(机会成本)
                for i in range(len(CoreDispatcher.order_pool)):
                    order = CoreDispatcher.order_pool[i]
                    c1, c2 = float('inf'), float('inf')
                    v1, r1 = None, None
                    
                    for v in fleet:
                        # ===== 查看车辆容量是否已满 =====
                        if len(v.on_board_orders) >= v.capacity: 
                            continue
                        # ===== 疲劳驾驶与休息拦截限流 =====
                        if getattr(v, 'is_rest_requested', False) or getattr(v, 'is_resting', False):
                            continue
                            
                        route, cost = CoreDispatcher._try_insert_order(v, order, city_map)
                        is_idle = len(v.on_board_orders) == 0 and len(v.planned_route) == 0
                        
                        # 规则：约束忙碌中车辆强行掉头大绕路；对全空闲车绿灯放行以保障接单率
                        if not is_idle and cost > 30000.0:
                            cost = float('inf')
                            
                        # 维护全局对该订单的“最优车”(c1) 和 “次优车”(c2)
                        if cost < c1:
                            c2 = c1
                            c1 = cost
                            v1 = v
                            r1 = route
                        elif cost < c2:
                            c2 = cost
                            
                    if c1 == float('inf'):
                        continue
                        
                    # 计算后悔值：次优成本与最优成本的差额
                    regret = 1e6 if c2 == float('inf') else (c2 - c1)
                    
                    if regret > max_regret:
                        max_regret = regret
                        best_o_idx = i
                        global_best_v = v1
                        global_best_route = r1
                        
                if best_o_idx != -1:
                    target_o = CoreDispatcher.order_pool.pop(best_o_idx)
                    # 空车热点只是可中断引导；一旦接到真实订单，必须立即清理。
                    CoreDispatcher._clear_idle_parking(global_best_v)
                    global_best_v.planned_route = global_best_route
                    CoreDispatcher.refresh_vehicle_route_metadata(global_best_v, city_map)
                    assign_count += 1
                    print(f"[Core.Pool] [Match] 后悔值匹配成功：单 {target_o.id} 被 {global_best_v.id} 优先划拨！")
                    
                    # ==========================================
                    # 打印车辆更新后的轨迹点 (途径站点) 
                    # ==========================================
                    waypoints = []
                    total_path = []
                    full_path_node_count = 0
                    curr_node_id = global_best_v.next_node
                    
                    for step in global_best_route:
                        o = step['order']
                        target_node = o.p_node if step['type'] == 'P' else o.d_node
                        action_name = "接驾" if step['type'] == 'P' else "送驾"
                        waypoints.append(f"[{action_name}{o.id}] {target_node.name} ({target_node.lon:.5f},{target_node.lat:.5f})")
                        
                        # 顺便统计底层 A* 寻路的精细轨迹点总数
                        dist, path = city_map.get_path(city_map.nodes_map[curr_node_id], target_node)
                        for nodes in path:
                            total_path.append([nodes.lon,nodes.lat])
                        full_path_node_count += len(path)
                        curr_node_id = target_node.id
                        
                    print(f"    [轨迹] {global_best_v.id} 任务途径点序列: {' -> '.join(waypoints)}")
                    print(f"    [明细] 该路线底层共包含 {full_path_node_count} 个路网轨迹点")
                    # print(f"    [明细] 该路线总里程: {total_path} ")
                else:
                    # 池中剩余订单当前均无法匹配
                    break
                    
            if assign_count > 0:
                print(f"[Core.Pool] 本轮调度完毕：成功释放 {assign_count} 个积压订单。")
            
            # 等待 5 秒进行下一轮匹配
            time.sleep(5)

    @staticmethod
    def _project_point_to_segment(lon, lat, u_node, v_node):
        """将 GPS 点投影到指定路段线段上。

        Args:
            lon (float): 车辆 GPS 经度。
            lat (float): 车辆 GPS 纬度。
            u_node (Node): 路段起点。
            v_node (Node): 路段终点。

        Returns:
            tuple: (投影经度, 投影纬度, 路段进度 0~1, GPS 到投影点距离米)。
        """
        ax, ay = u_node.lon, u_node.lat
        bx, by = v_node.lon, v_node.lat
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq == 0:
            progress = 0.0
        else:
            progress = ((lon - ax) * dx + (lat - ay) * dy) / seg_len_sq
            progress = max(0.0, min(1.0, progress))

        projected_lon = ax + progress * dx
        projected_lat = ay + progress * dy
        distance = AuxiliaryFunctions.haversine_distance(lon, lat, projected_lon, projected_lat)
        return projected_lon, projected_lat, progress, distance

    @staticmethod
    def _projection_result(city_map, lon, lat, u_id, v_id, snap_source):
        """构造 GPS 到一条路网边的吸附结果。

        Args:
            city_map (CityGraph): 路网对象。
            lon (float): 车辆 GPS 经度。
            lat (float): 车辆 GPS 纬度。
            u_id (str): 路段起点节点 ID。
            v_id (str): 路段终点节点 ID。
            snap_source (str): 吸附来源标记，例如 planned_route 或 road_network。

        Returns:
            dict | None: 投影结果；节点不存在时返回 None。
        """
        u_node = city_map.nodes_map.get(u_id)
        v_node = city_map.nodes_map.get(v_id)
        if u_node is None or v_node is None:
            return None

        projected_lon, projected_lat, progress, distance = CoreDispatcher._project_point_to_segment(lon, lat, u_node, v_node)
        return {
            "lon": projected_lon,
            "lat": projected_lat,
            "edge_u": u_id,
            "edge_v": v_id,
            "progress": progress,
            "distance_to_gps": distance,
            "next_node": v_node,
            "snap_source": snap_source,
        }

    @staticmethod
    def _nearest_road_projection(city_map, lon, lat, vehicle=None):
        """将车辆 GPS 坐标吸附到路网边上的最近投影点。

        Args:
            city_map (CityGraph): 路网对象。
            lon (float): 车辆 GPS 经度。
            lat (float): 车辆 GPS 纬度。
            vehicle (Vehicle | None): 当前车辆。传入车辆时优先约束在车辆规划轨迹附近。

        Returns:
            dict | None: 最近路段投影信息；没有可用边时返回 None。
        """
        if vehicle is not None and vehicle.planned_route_point:
            route_points = vehicle.planned_route_point
            best_projection = None
            max_lookahead_distance = 500.0

            # 先检查当前所在路段，避免 GPS 轻微偏移时被吸到相邻或对向道路。
            current_projection = CoreDispatcher._projection_result(
                city_map,
                lon,
                lat,
                vehicle.last_node,
                vehicle.next_node,
                "planned_route",
            )
            if (
                current_projection is not None
                and current_projection["progress"] + 0.02 >= vehicle.progress
            ):
                best_projection = current_projection

            start_index = None
            for i, point in enumerate(route_points):
                if point["id"] == vehicle.next_node:
                    start_index = i
                    break
            if start_index is None:
                start_index = 0

            lookahead_distance = 0.0
            for i in range(start_index, len(route_points) - 1):
                u_id = route_points[i]["id"]
                v_id = route_points[i + 1]["id"]
                projection = CoreDispatcher._projection_result(
                    city_map,
                    lon,
                    lat,
                    u_id,
                    v_id,
                    "planned_route",
                )
                if projection is not None and (
                    best_projection is None
                    or projection["distance_to_gps"] < best_projection["distance_to_gps"]
                ):
                    best_projection = projection

                # 只向前搜索有限距离，避免车辆被吸回已走过很远的历史路段。
                u_node = city_map.nodes_map.get(u_id)
                v_node = city_map.nodes_map.get(v_id)
                if u_node is None or v_node is None:
                    continue
                lookahead_distance += AuxiliaryFunctions.haversine_distance(
                    u_node.lon,
                    u_node.lat,
                    v_node.lon,
                    v_node.lat,
                )
                if lookahead_distance >= max_lookahead_distance:
                    break

            if best_projection is not None:
                return best_projection

        best_projection = None
        for edge in city_map.edges:
            projection = CoreDispatcher._projection_result(
                city_map,
                lon,
                lat,
                edge["u"],
                edge["v"],
                "road_network",
            )
            if projection is None:
                continue
            if best_projection is None or projection["distance_to_gps"] < best_projection["distance_to_gps"]:
                best_projection = projection

        return best_projection

    @staticmethod
    def _planned_route_targets(vehicle):
        """按车辆当前订单计划提取后续接送目标点。

        Args:
            vehicle (Vehicle): 需要读取 planned_route 的车辆。

        Returns:
            list[dict]: 每项包含步骤类型、订单 ID 和目标 Node。
        """
        targets = []
        for step in vehicle.planned_route:
            order = step["order"]
            target_node = order.p_node if step["type"] == "P" else order.d_node
            targets.append({
                "type": step["type"],
                "order_id": order.id,
                "node": target_node,
            })
        return targets

    @staticmethod
    def _node_to_path_point(node):
        """将路网节点转成接口可返回的轨迹点。

        Args:
            node (Node): 路网节点对象。

        Returns:
            dict: 包含 id、经纬度、名称和分区的轨迹点。
        """
        return {
            "id": node.id,
            "lon": node.lon,
            "lat": node.lat,
            "name": node.name,
            "zone": node.zone,
        }

    @staticmethod
    def _clear_idle_parking(vehicle):
        """清理车辆的空车停靠预测状态。

        Args:
            vehicle (Vehicle): 需要清理空车引导状态的车辆。

        Returns:
            None。
        """
        vehicle.idle_target = None
        vehicle.idle_forecast = None

    @staticmethod
    def _nearest_graph_node(city_map, lon, lat):
        """查找距离给定经纬度最近的路网节点。

        Args:
            city_map (CityGraph): 路网对象。
            lon (float): 待吸附经度。
            lat (float): 待吸附纬度。

        Returns:
            tuple: (最近 Node | None, 当前经纬度到最近节点的距离(米))。
        """
        best_node = None
        best_dist = float("inf")
        for node in city_map.nodes_map.values():
            dist = AuxiliaryFunctions.haversine_distance(lon, lat, node.lon, node.lat)
            if dist < best_dist:
                best_node = node
                best_dist = dist
        return best_node, best_dist

    @staticmethod
    def _collect_forecast_orders(fleet=None):
        """收集可供 OD 预测使用的历史和运行期订单样本。

        Args:
            fleet (list[Vehicle] | None): 当前车队；为空时只读取全局订单池。

        Returns:
            list[Order]: 去重后的订单对象列表。
        """
        orders = []
        seen_ids = set()

        def add_order(order):
            """按订单 ID 去重后加入预测样本集合。"""
            order_id = getattr(order, "id", None)
            key = str(order_id) if order_id is not None else id(order)
            if key in seen_ids:
                return
            seen_ids.add(key)
            orders.append(order)

        for order in CoreDispatcher.completed_orders_pool:
            add_order(order)
        for order in CoreDispatcher.order_pool:
            add_order(order)
        for v in fleet or []:
            for order in v.on_board_orders:
                add_order(order)
            for step in v.planned_route:
                add_order(step["order"])

        return orders

    @staticmethod
    def _select_idle_hotspot(predictions, vehicle, city_map):
        """从预测结果中选择空车应前往的上车热点。

        Args:
            predictions (list[dict]): od_forecast_module 输出的预测行。
            vehicle (Vehicle): 当前空车，用于距离 tie-break。
            city_map (CityGraph): 路网对象，用于读取车辆当前位置。

        Returns:
            dict | None: 被选中的预测行；没有有效预测时返回 None。
        """
        rows = [row for row in predictions if int(row.get("horizon_min", 15)) == 15]
        if not rows:
            rows = list(predictions)
        if not rows:
            return None

        start_node = city_map.nodes_map.get(vehicle.next_node) or city_map.nodes_map.get(vehicle.last_node)
        if start_node is None:
            return None

        def score(row):
            """按预测订单数降序、距离升序排序。"""
            lon = float(row["o_center_lon"])
            lat = float(row["o_center_lat"])
            dist = AuxiliaryFunctions.haversine_distance(start_node.lon, start_node.lat, lon, lat)
            return (-int(row.get("pred_count", 0)), dist)

        return sorted(rows, key=score)[0]

    @staticmethod
    def _build_idle_route_from_node(vehicle, city_map, start_node):
        """构建空车从当前节点前往预测热点的展示轨迹。

        Args:
            vehicle (Vehicle): 已写入 idle_target 的空车。
            city_map (CityGraph): 路网对象。
            start_node (Node): 轨迹起点节点。

        Returns:
            dict | None: 与订单路径结构兼容的轨迹结果；不可达时返回 None。
        """
        if not vehicle.idle_target:
            return None

        target_node = city_map.nodes_map.get(vehicle.idle_target.get("node_id"))
        if target_node is None:
            return None

        dist, path = city_map.get_path(start_node, target_node)
        if dist == float("inf"):
            return None

        path_points = [CoreDispatcher._node_to_path_point(node) for node in path]
        return {
            "start_node": CoreDispatcher._node_to_path_point(start_node),
            "planned_route_size": 0,
            "total_distance": dist,
            "path": path_points,
            "segments": [
                {
                    "type": "IDLE",
                    "order_id": None,
                    "target_node": CoreDispatcher._node_to_path_point(target_node),
                    "distance": dist,
                    "path": path_points,
                    "forecast": vehicle.idle_forecast,
                }
            ],
        }

    @staticmethod
    def rebuild_vehicle_path_from_node(vehicle, city_map, start_node):
        """从指定路网节点出发，按车辆计划订单重新拼接完整路网轨迹。

        Args:
            vehicle (Vehicle): 需要重建路径的车辆。
            city_map (CityGraph): 路网对象。
            start_node (Node): 后续路径起点。

        Returns:
            dict | None: 后续总轨迹、分段轨迹和总距离；存在不可达路段时返回 None。
        """
        path_points = []
        route_segments = []
        current_node = start_node
        total_distance = 0.0

        for target in CoreDispatcher._planned_route_targets(vehicle):
            dist, path = city_map.get_path(current_node, target["node"])
            if dist == float("inf"):
                return None

            segment_points = [CoreDispatcher._node_to_path_point(n) for n in path]
            if path_points and segment_points:
                path_points.extend(segment_points[1:])
            else:
                path_points.extend(segment_points)

            route_segments.append({
                "type": target["type"],
                "order_id": target["order_id"],
                "target_node": CoreDispatcher._node_to_path_point(target["node"]),
                "distance": dist,
                "path": segment_points,
            })
            total_distance += dist
            current_node = target["node"]

        return {
            "start_node": CoreDispatcher._node_to_path_point(start_node),
            "planned_route_size": len(vehicle.planned_route),
            "total_distance": total_distance,
            "path": path_points,
            "segments": route_segments,
        }

    @staticmethod
    def refresh_vehicle_route_metadata(vehicle, city_map, start_node=None):
        """刷新车辆当前 GPS 和前端展示所需路径元数据。

        Args:
            vehicle (Vehicle): 需要同步元数据的车辆。
            city_map (CityGraph): 路网对象。
            start_node (Node | None): 指定刷新起点；为空时使用车辆 next_node/last_node。

        Returns:
            dict | None: 最新轨迹结果；起点无效或路径不可达时返回 None。

        Side Effects:
            更新 vehicle.gps 和 vehicle.planned_route_point。
            车辆已有真实订单时会清理 idle_target/idle_forecast。
        """
        if start_node is None:
            start_node = city_map.nodes_map.get(vehicle.next_node) or city_map.nodes_map.get(vehicle.last_node)
        if start_node is None:
            vehicle.gps = {"lon": None, "lat": None}
            vehicle.planned_route_point = []
            return None

        if vehicle.planned_route:
            CoreDispatcher._clear_idle_parking(vehicle)

        vehicle.gps = {"lon": start_node.lon, "lat": start_node.lat}
        if not vehicle.planned_route and vehicle.idle_target:
            result = CoreDispatcher._build_idle_route_from_node(vehicle, city_map, start_node)
        else:
            result = CoreDispatcher.rebuild_vehicle_path_from_node(vehicle, city_map, start_node)
        if result is None:
            vehicle.planned_route_point = []
            return None

        vehicle.planned_route_point = result["path"]
        return result

    @staticmethod
    def _projection_to_path_point(projection):
        """将道路投影点转成接口轨迹点。

        Args:
            projection (dict): _nearest_road_projection 返回的投影结果。

        Returns:
            dict: 可直接拼接到 planned_route_point 的虚拟轨迹点。
        """
        return {
            "id": f"{projection['edge_u']}|{projection['edge_v']}@{projection['progress']:.6f}",
            "lon": projection["lon"],
            "lat": projection["lat"],
            "name": "车辆当前位置",
            "zone": projection["next_node"].zone,
            "edge_u": projection["edge_u"],
            "edge_v": projection["edge_v"],
            "progress": projection["progress"],
            "is_projection": True,
        }

    @staticmethod
    def sync_vehicle_route_progress(vehicle, city_map, current_node):
        """根据车辆到达的路网节点同步上下客状态和剩余计划。

        Args:
            vehicle (Vehicle): 需要推进订单状态的车辆。
            city_map (CityGraph): 路网对象，当前函数保留该参数用于接口一致性。
            current_node (Node): 车辆已到达的路网节点。

        Returns:
            list[dict]: 本次触发的 pickup/dropoff 变更列表。

        Side Effects:
            更新 vehicle.last_node、vehicle.next_node、vehicle.progress、vehicle.gps。
            可能修改 vehicle.on_board_orders、vehicle.planned_route 和 completed_orders_pool。
        """
        vehicle.last_node = current_node.id
        vehicle.next_node = current_node.id
        vehicle.progress = 0.0
        vehicle.gps = {"lon": current_node.lon, "lat": current_node.lat}

        changed_steps = []
        while vehicle.planned_route:
            step = vehicle.planned_route[0]
            order = step["order"]
            target_node = order.p_node if step["type"] == "P" else order.d_node
            if target_node.id != current_node.id:
                break

            if step["type"] == "P":
                if all(o.id != order.id for o in vehicle.on_board_orders):
                    vehicle.on_board_orders.append(order)
                order.actual_pick_time = order.actual_pick_time or vehicle.time
                action = "pickup"
            else:
                vehicle.on_board_orders = [o for o in vehicle.on_board_orders if o.id != order.id]
                if order not in CoreDispatcher.completed_orders_pool:
                    CoreDispatcher.completed_orders_pool.append(order)
                action = "dropoff"

            vehicle.planned_route.pop(0)
            changed_steps.append({
                "action": action,
                "type": step["type"],
                "order_id": order.id,
                "node": CoreDispatcher._node_to_path_point(target_node),
            })

        return changed_steps

    @staticmethod
    def _route_point_index(route_points, node_id):
        """查找目标节点在轨迹点列表中的位置。

        Args:
            route_points (list[dict]): planned_route_point 轨迹点列表。
            node_id (str): 需要查找的路网节点 ID。

        Returns:
            int | None: 首次出现的位置；未找到时返回 None。

        Note:
            当前用于前端 GPS 模拟越点判断。实际生产系统中，上下客确认通常由司机端或乘客端事件触发。
        """
        for i, point in enumerate(route_points):
            if point.get("id") == node_id:
                return i
        return None

    @staticmethod
    def _apply_reached_route_step(vehicle, step, target_node):
        """应用一个已到达接送点的订单步骤。

        Args:
            vehicle (Vehicle): 被更新上下客状态的车辆。
            step (dict): planned_route 中的步骤，包含 type 和 order。
            target_node (Node): 当前步骤对应的接客或送客节点。

        Returns:
            dict: 描述本次 pickup/dropoff 的变更记录。

        Note:
            当前用于前端 GPS 模拟越点判断。实际生产系统中，上下客确认通常由司机端或乘客端事件触发。
        """
        order = step["order"]
        if step["type"] == "P":
            if all(o.id != order.id for o in vehicle.on_board_orders):
                vehicle.on_board_orders.append(order)
            order.actual_pick_time = order.actual_pick_time or vehicle.time
            action = "pickup"
        else:
            vehicle.on_board_orders = [o for o in vehicle.on_board_orders if o.id != order.id]
            if order not in CoreDispatcher.completed_orders_pool:
                CoreDispatcher.completed_orders_pool.append(order)
            action = "dropoff"

        return {
            "action": action,
            "type": step["type"],
            "order_id": order.id,
            "node": CoreDispatcher._node_to_path_point(target_node),
        }

    @staticmethod
    def _sync_passed_route_targets(vehicle, route_points, projection):
        """GPS 跨过接送目标点时，同步已经经过的上下客步骤。

        Args:
            vehicle (Vehicle): 需要同步上下客状态的车辆。
            route_points (list[dict]): 本次 GPS 更新前的旧轨迹点列表。
            projection (dict): 新 GPS 吸附到路段后的投影结果。

        Returns:
            list[dict]: 被自动判定为已经完成的 pickup/dropoff 步骤。

        Note:
            当前用于前端 GPS 模拟越点判断。实际生产系统中，上下客确认通常由司机端或乘客端事件触发。
        """
        projection_index = None
        for i in range(len(route_points) - 1):
            if (
                route_points[i].get("id") == projection["edge_u"]
                and route_points[i + 1].get("id") == projection["edge_v"]
            ):
                projection_index = i
                break
        if projection_index is None:
            return []

        changed_steps = []
        while vehicle.planned_route:
            step = vehicle.planned_route[0]
            order = step["order"]
            target_node = order.p_node if step["type"] == "P" else order.d_node
            target_index = CoreDispatcher._route_point_index(route_points, target_node.id)
            if target_index is None:
                break

            is_passed = target_index <= projection_index
            is_at_edge_end = target_index == projection_index + 1 and projection["progress"] >= 0.999
            if not is_passed and not is_at_edge_end:
                break

            vehicle.planned_route.pop(0)
            changed_steps.append(CoreDispatcher._apply_reached_route_step(vehicle, step, target_node))

        return changed_steps

    @staticmethod
    def rebuild_vehicle_path_from_gps(vehicle, city_map, lon, lat):
        """根据车辆 GPS 坐标和当前任务状态重新计算后续路网轨迹。

        Args:
            vehicle (Vehicle): 需要更新位置和路径的车辆。
            city_map (CityGraph): 路网对象。
            lon (float): 车辆 GPS 经度。
            lat (float): 车辆 GPS 纬度。

        Returns:
            dict | None: 前端展示所需的吸附点、轨迹点、上下客变更和订单状态；
                吸附失败或路径不可达时返回 None。

        Side Effects:
            更新 vehicle.gps、last_node、next_node、progress 和 planned_route_point。
            可能触发 pickup/dropoff，从而修改 on_board_orders、planned_route 和 completed_orders_pool。
        """
        old_route_points = list(vehicle.planned_route_point)
        # GPS 先吸附到路网边线，避免原始坐标偏移导致车辆脱离道路。
        projection = CoreDispatcher._nearest_road_projection(city_map, lon, lat, vehicle)
        if projection is None:
            return None

        next_node = projection["next_node"]
        # 离散 GPS 可能一次跨过接客/送客点，需要先按旧轨迹判断越点。
        changed_steps = CoreDispatcher._sync_passed_route_targets(vehicle, old_route_points, projection)
        # 投影接近路段终点时，再按节点到达逻辑推进订单状态。
        if projection["progress"] >= 0.999:
            changed_steps.extend(CoreDispatcher.sync_vehicle_route_progress(vehicle, city_map, next_node))

        # 以吸附后的下一节点为起点重建剩余轨迹；真实 GPS 会作为虚拟起点补回结果首位。
        result = CoreDispatcher.refresh_vehicle_route_metadata(vehicle, city_map, next_node)
        if result is None:
            return None

        vehicle.gps = {"lon": lon, "lat": lat}
        vehicle.last_node = projection["edge_u"]
        vehicle.next_node = projection["edge_v"]
        vehicle.progress = projection["progress"]

        projection_point = CoreDispatcher._projection_to_path_point(projection)
        result["path"] = [projection_point] + result["path"]
        result["planned_route_point"] = result["path"]
        vehicle.planned_route_point = result["planned_route_point"]

        result["gps"] = vehicle.gps
        result.pop("start_node", None)
        result["snapped_point"] = {
            "id": projection_point["id"],
            "lon": projection["lon"],
            "lat": projection["lat"],
            "name": projection_point["name"],
            "zone": projection_point["zone"],
            "edge": {
                "u": projection["edge_u"],
                "v": projection["edge_v"],
            },
            "progress": projection["progress"],
            "distance_to_gps": projection["distance_to_gps"],
            "next_node": CoreDispatcher._node_to_path_point(next_node),
            "snap_source": projection["snap_source"],
        }
        result["snapped_node"] = result["snapped_point"]
        result["changed_steps"] = changed_steps
        result["on_board_orders"] = [o.id for o in vehicle.on_board_orders]
        result["planned_route"] = [
            {
                "type": step["type"],
                "order_id": step["order"].id,
                "target_node": CoreDispatcher._node_to_path_point(
                    step["order"].p_node if step["type"] == "P" else step["order"].d_node
                ),
            }
            for step in vehicle.planned_route
        ]
        return result

    @staticmethod
    def idle_parking_scenario(vehicle, city_map, fleet=None):
        """为空车生成前往未来订单热点的停靠路径。
        
        Args:
            vehicle (Vehicle): 处于闲置待命状态的车辆。
            city_map (CityGraph): 路网对象。
            fleet (list[Vehicle] | None): 当前车队，用于收集运行期订单样本。
            
        Returns:
            bool: 成功生成或已存在空车停靠路径时返回 True，否则返回 False。

        Side Effects:
            成功时写入 vehicle.idle_target、vehicle.idle_forecast 和 planned_route_point。
            不写入 vehicle.planned_route，确保车辆途中接到新订单时可以被真实订单路径覆盖。
        """
        # 只有完全空闲车辆才允许进入空车停靠场景。
        if vehicle.on_board_orders or vehicle.planned_route:
            return False
        if getattr(vehicle, "is_rest_requested", False) or getattr(vehicle, "is_resting", False):
            return False
        if vehicle.idle_target and vehicle.planned_route_point:
            return True

        print(f"[Core.Planner] {vehicle.id} 空车待命，触发未来 15 分钟订单热点预测...")
        orders = CoreDispatcher._collect_forecast_orders(fleet)
        if not orders:
            print(f"[Core.Planner] {vehicle.id} 当前没有历史订单，无法生成空车停靠预测。")
            return False

        try:
            clean_orders = od_forecast_module.orders_from_insert_riding(
                orders,
                city_map=city_map,
                base_datetime=datetime.fromtimestamp(0),
                speed_mps=SPEED_MPS,
            )
        except Exception as exc:
            print(f"[Core.Planner] 订单预测输入转换失败：{exc}")
            return False
        if not clean_orders:
            return False

        # 预测窗口选择“最近一条历史订单之后的下一个 15 分钟窗口”。
        forecast_time = max(order.request_time for order in clean_orders) + timedelta(minutes=15)
        predictions = []
        metrics = []
        try:
            predictions, _, metrics = od_forecast_module.predict_od_flows_v6(
                clean_orders,
                forecast_start_time=forecast_time,
                horizons_min=(15,),
                top_k=50,
            )
        except Exception as exc:
            print(f"[Core.Planner] v6 预测失败，降级使用历史统计预测：{exc}")

        if not predictions:
            predictions, _ = od_forecast_module.predict_od_flows(
                clean_orders,
                forecast_time=forecast_time,
                horizons_min=(15,),
                top_k=50,
            )
        if not predictions:
            print(f"[Core.Planner] {vehicle.id} 没有预测到未来 15 分钟正向订单热点。")
            return False

        hotspot = CoreDispatcher._select_idle_hotspot(predictions, vehicle, city_map)
        if hotspot is None:
            return False

        # 预测输出是经纬度中心点，实际寻路前必须吸附到可达路网节点。
        target_lon = float(hotspot["o_center_lon"])
        target_lat = float(hotspot["o_center_lat"])
        target_node, snap_distance = CoreDispatcher._nearest_graph_node(city_map, target_lon, target_lat)
        start_node = city_map.nodes_map.get(vehicle.next_node) or city_map.nodes_map.get(vehicle.last_node)
        if target_node is None or start_node is None:
            return False

        # idle_forecast/idle_target 会透传给接口，用于解释空车为何去该热点。
        vehicle.idle_forecast = {
            "forecast_start_time": hotspot.get("forecast_start_time"),
            "forecast_end_time": hotspot.get("forecast_end_time"),
            "horizon_min": int(hotspot.get("horizon_min", 15)),
            "pred_count": int(hotspot.get("pred_count", 0)),
            "metrics": metrics,
        }
        vehicle.idle_target = {
            "lon": target_lon,
            "lat": target_lat,
            "node_id": target_node.id,
            "node_name": target_node.name,
            "node_lon": target_node.lon,
            "node_lat": target_node.lat,
            "snap_distance_to_node": snap_distance,
        }

        result = CoreDispatcher.refresh_vehicle_route_metadata(vehicle, city_map, start_node)
        if result is None:
            CoreDispatcher._clear_idle_parking(vehicle)
            return False

        print(
            f"[Core.Planner] {vehicle.id} 空车前往预测热点 {target_node.name} "
            f"({target_node.lon:.5f},{target_node.lat:.5f})，预测订单数 {vehicle.idle_forecast['pred_count']}。"
        )
        return True

    @staticmethod
    def stop_order_prediction(vehicle):
        """【停止接单预测场景】：根据车辆健康度、疲劳度或电量衰退进行的干预算法。
        
        Args:
            vehicle (Vehicle): 需要进行健康扫描的车辆。
            
        Returns:
            bool: 是否下达强制切断接单信令。

        Note:
            当前为预留风控入口，尚未接入真实疲劳、电量或健康度预测模型。
        """
        print(f"[Core.WindControl] 对 {vehicle.id} 下发了疲劳驾驶、晚高峰以及掉电预期寿命扫描...")
        # 预留待办算法：截断车队被推演插入池
        return False
