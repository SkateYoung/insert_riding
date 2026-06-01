# core.py
"""打车系统的大脑业务算子主控层。
负责派单、重组架构、以及闲置管控等绝对智能内核逻辑。
"""

import time
from contextlib import nullcontext
from datetime import datetime, timedelta
from .models import MAX_REST_DURATION_SECONDS, MIN_REST_DURATION_SECONDS, SPEED_MPS
from .auxiliary import AuxiliaryFunctions
from forecast import od_forecast_module

class CoreDispatcher:
    """提供拼单博弈算力与核心派车路线演算的中枢处理台。"""
    
    # 核心订单池：用于缓存由于运力爆满、或严重绕路(不顺路)而未能及时指派的订单。
    order_pool = []
    
    # [新增] 存放已完成、已结束（或已取消）订单的归档池，内部存储 Order 对象
    completed_orders_pool = []

    # 空车热点预测缓存：避免后台循环每 5 秒重复训练/预测。
    IDLE_FORECAST_CACHE_SECONDS = 15 * 60
    IDLE_MIN_HOTSPOT_DISTANCE_METERS = 800.0
    idle_hotspot_cache = None

    # ============================================================
    # 功能一：订单路线成本评估与单车插单寻优
    # 相关方法：evaluate_route、_try_insert_order
    # ============================================================

    @staticmethod
    def evaluate_route(route, vehicle_state, on_board_orders, city_map, capacity=10, v_zone=None, original_etas=None, return_details=False):
        """核心评级器：沙盘量化时间线成本（Cost）以评估未来路线质量分数。
        
        该算法引入了由于车辆绕路等问题产生的物理油耗距离分数、乘客空等惩罚分，
        并在后续可以接入真正的 SLA 防止无限插队模型。
        
        Args:
            route (list): 一条排列好的装载字典列队（每项包含 'type': 'O'/'D', 和 'order' 对象）。
            vehicle_state (dict): 执行这段未来可能路线前的车辆状态副本，如目前开到了哪个节点坐标。
            on_board_orders (list): 该车上目前正被关着的已有乘客清单。
            city_map (CityGraph): 可以用于通过 A* 推算空间距离字典的数字路网基站。
            capacity (int, optional): 车辆容量限制。
            v_zone (int, optional): 预留的运营区参数；当前成本函数暂不计算跨区成本。
            original_etas (dict, optional): 插入新订单前老乘客的原计划预计到达时间字典，用于计算拼车真实延误。
            return_details (bool, optional): 是否额外返回成本明细。
            
        Returns:
            tuple: 默认返回 (可不可行分支True/False, 最终累计积分成本 float, 推演各订单到达时间字典 dict)。
                   return_details=True 时额外返回成本明细 dict。成本分越低代表路线越优。
        """
        def _result(is_feasible, cost, arrivals=None, details=None):
            if return_details:
                return is_feasible, cost, arrivals, details or {}
            return is_feasible, cost, arrivals

        speed = SPEED_MPS 
        sim_time = vehicle_state['time']
        sim_last_node = vehicle_state['last_node']
        sim_next_node = vehicle_state['next_node']
        
        current_load = sum(order.passenger_count for order in on_board_orders)
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
        
        for step in route:
            order = step['order']
            target_node = order.o_node if step['type'] == 'O' else order.d_node
            
            dist, path = city_map.get_path(city_map.nodes_map[sim_next_node], target_node)
            
            if dist == float('inf'):
                return _result(False, float('inf'), None, {"infeasible_reason": "path_unreachable"})
                
            if current_load == 0:
                empty_dist += dist
            else:
                loaded_dist += dist
                
            sim_time += dist / speed
            sim_next_node = target_node.id
            
            if step['type'] == 'O':
                current_load += order.passenger_count
                if current_load > capacity: 
                    return _result(False, float('inf'), None, {"infeasible_reason": "capacity_exceeded"})
                pickup_times[order.request_id] = sim_time
            elif step['type'] == 'D':
                current_load -= order.passenger_count
                if current_load < 0:
                    return _result(False, float('inf'), None, {"infeasible_reason": "negative_load"})
                arrival_times[order.request_id] = sim_time

        # ===== 综合多目标成本函数架构 =====
        
        # 1. 权重定义 (严格按照需求配比)
        W_PASSENGER = 0.40  # 乘客体验 (候车时间、绕行系数、时间窗满意度)
        W_ENTERPRISE = 0.30 # 企业效益 (满载率、单车收入、里程利用率)
        W_SOCIAL = 0.20     # 社会效益 (区域覆盖率、碳排放、道路资源占用)
        W_FAIRNESS = 0.10   # 平台公平 (企业间订单分配基尼系数)

        # 成本统一在分钟、公里和比例维度上计算，避免秒和米的原始尺度压制其他指标。
        SECONDS_PER_MINUTE = 60.0
        METERS_PER_KM = 1000.0
        WAIT_COST_PER_MIN = 4.0
        IN_CAR_COST_PER_MIN = 3.0
        LATE_PICKUP_COST_PER_MIN = 1.0
        LATE_ARRIVAL_COST_PER_MIN = 1.0
        OLD_DELAY_COST_PER_MIN = 3.0
        SEVERE_OLD_DELAY_PENALTY = 25.0
        MILEAGE_UTIL_PENALTY_BASE = 30.0
        LOAD_RATE_PENALTY_BASE = 20.0
        SOCIAL_DISTANCE_COST_PER_KM = 1.0
        
        # ---------------------------------------------------------
        # 维度 A: 乘客体验成本 (Passenger Cost)
        passenger_cost = 0.0
        wait_cost = 0.0
        late_pickup_cost = 0.0
        in_car_cost = 0.0
        late_arrival_cost = 0.0
        old_passenger_delay_cost = 0.0
        old_passenger_severe_delay_cost = 0.0
        for step in route:
            order = step['order']
            if step['type'] == 'O':
                wait_minutes = max(0.0, pickup_times[order.request_id] - order.req_time) / SECONDS_PER_MINUTE
                wait_cost += wait_minutes * WAIT_COST_PER_MIN
                
                # 时间窗满意度：超出期望上车时间不再一票否决，改为有限惩罚，允许积压订单继续派单。
                late_pickup_minutes = max(0.0, pickup_times[order.request_id] - order.max_pickup_time) / SECONDS_PER_MINUTE
                late_pickup_cost += late_pickup_minutes * LATE_PICKUP_COST_PER_MIN
            else:
                start_service_time = pickup_times.get(order.request_id) or order.actual_pick_time or vehicle_state['time']
                in_car_minutes = max(0.0, arrival_times[order.request_id] - start_service_time) / SECONDS_PER_MINUTE
                in_car_cost += in_car_minutes * IN_CAR_COST_PER_MIN
                
                # 送达时间超出估算上限时同样只计入惩罚，不阻断车辆匹配。
                late_arrival_minutes = max(0.0, arrival_times[order.request_id] - order.max_arrival_time) / SECONDS_PER_MINUTE
                late_arrival_cost += late_arrival_minutes * LATE_ARRIVAL_COST_PER_MIN
            
        # 乘客体验：强制挂载老乘客被绕路的代价(真实的延误时间)
        for order in on_board_orders:
            for step in route:
                if step['type'] == 'D' and step['order'].request_id == order.request_id:
                    # 如果有原计划ETA，则仅惩罚真正多出来的老乘客的延误时间
                    if original_etas and order.request_id in original_etas:
                        delay_time = arrival_times[order.request_id] - original_etas[order.request_id]
                        if delay_time > 0:
                            old_passenger_delay_cost += (delay_time / SECONDS_PER_MINUTE) * OLD_DELAY_COST_PER_MIN
                            if delay_time > 180.0:
                                old_passenger_severe_delay_cost += SEVERE_OLD_DELAY_PENALTY
                    break

        passenger_cost = (
            wait_cost
            + late_pickup_cost
            + in_car_cost
            + late_arrival_cost
            + old_passenger_delay_cost
            + old_passenger_severe_delay_cost
        )

        # ---------------------------------------------------------
        # 维度 B: 企业效益成本 (Enterprise Cost)
        # 企业效益 = 绝对油耗开销 + 里程利用率惩罚 + 满载率惩罚
        
        total_sim_dist = empty_dist + loaded_dist
        
        # 1. 里程利用率 (Mileage Utilization Rate)：载客里程占比
        mileage_util_rate = loaded_dist / total_sim_dist if total_sim_dist > 0 else 0.0
        # 利用率越低，空跑越多，惩罚越大。这里使用低基数，避免企业成本压过乘客体验。
        mileage_penalty = (1.0 - mileage_util_rate) * MILEAGE_UTIL_PENALTY_BASE
        
        # 2. 满载率 (Load Rate)：这里使用这趟路线服务的总客数占比作为满载率代理
        # (车上原有的 + 这趟新接的) / 最大容量
        total_pax = sum(order.passenger_count for order in on_board_orders) + sum(
            step['order'].passenger_count for step in route if step['type'] == 'O'
        )
        load_rate = min(1.0, total_pax / max(1, capacity))
        # 满载率越低（拉着一两座跑），效率越低，惩罚越大。
        load_penalty = (1.0 - load_rate) * LOAD_RATE_PENALTY_BASE
        
        # 综合企业成本
        enterprise_cost =  mileage_penalty + load_penalty

        # ---------------------------------------------------------
        # 维度 C: 社会效益成本 (Social Cost)
        # 总体路权占用和碳排放使用总里程代理；本轮暂不考虑跨区成本。
        total_dist = empty_dist + loaded_dist
        total_km = total_dist / METERS_PER_KM
        social_cost = total_km * SOCIAL_DISTANCE_COST_PER_KM
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
        
        cost_details = {
            "passenger_cost": passenger_cost,
            "wait_cost": wait_cost,
            "late_pickup_cost": late_pickup_cost,
            "in_car_cost": in_car_cost,
            "late_arrival_cost": late_arrival_cost,
            "old_passenger_delay_cost": old_passenger_delay_cost,
            "old_passenger_severe_delay_cost": old_passenger_severe_delay_cost,
            "enterprise_cost": enterprise_cost,
            "mileage_penalty": mileage_penalty,
            "load_penalty": load_penalty,
            "social_cost": social_cost,
            "fairness_cost": fairness_cost,
            "weighted_passenger_cost": W_PASSENGER * passenger_cost,
            "weighted_enterprise_cost": W_ENTERPRISE * enterprise_cost,
            "weighted_social_cost": W_SOCIAL * social_cost,
            "weighted_fairness_cost": W_FAIRNESS * fairness_cost,
            "total_cost": cost,
            "metrics": {
                "empty_dist_m": empty_dist,
                "loaded_dist_m": loaded_dist,
                "total_dist_m": total_dist,
                "total_dist_km": total_km,
                "mileage_util_rate": mileage_util_rate,
                "load_rate": load_rate,
                "pickup_times": pickup_times,
                "arrival_times": arrival_times,
            },
        }
        return _result(True, cost, arrival_times, cost_details)

    @staticmethod
    def _try_insert_order(vehicle, new_order, city_map):
        """【组客内循环】：针对单车的贪婪性全路径缝隙插入探测寻优。
        
        该方法会尝试将新订单的 O 点和 D 点插入到现有计划路径的所有可能位置，并使用 evaluate_route 评估最优选。
        
        Args:
            vehicle (Vehicle): 目标评估车辆。
            new_order (Order): 需要尝试插入的新订单。
            city_map (CityGraph): 路网拓扑地图实例。
            
        Returns:
            tuple: (最优路径 list|None, 最优成本 float)
        """
        if not CoreDispatcher._vehicle_has_capacity_for_order(vehicle, new_order):
            return None, float('inf')

        best_route = None
        best_cost = float('inf')
        route = vehicle.planned_route
        n = len(route)
        o_step = {'type': 'O', 'order': new_order}
        d_step = {'type': 'D', 'order': new_order}
        v_state = {
            'time': vehicle.time,
            'last_node': vehicle.last_node,
            'next_node': vehicle.next_node,
            'progress': vehicle.progress
        }
        
        # 在做任何尝试之前，先推演一次原路线，获取所有车上老乘客的原始 ETA
        orig_etas = None
        if vehicle.on_board_orders and route:
            _, _, orig_etas = CoreDispatcher.evaluate_route(route, v_state, vehicle.on_board_orders, city_map, vehicle.capacity, v_zone=vehicle.op_zone)
        
        for i in range(n + 1):
            temp_route = route[:i] + [o_step] + route[i:]
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
                        seen_o = set()
                        on_board_ids = set(o.request_id for o in vehicle.on_board_orders)
                        
                        for step in mut_route:
                            oid = step['order'].request_id
                            if step['type'] == 'O':
                                seen_o.add(oid)
                            else:
                                if oid not in seen_o and oid not in on_board_ids:
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

    # ============================================================
    # 功能二：订单池匹配与后台调度循环
    # 相关方法：pool_and_route_planning、process_pool_matching
    # ============================================================

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
        print(f"[Core.Dispatcher] 新订单 [单{order.request_id}] 注入系统统筹池，等待匹配车辆中...")
        CoreDispatcher.order_pool.append(order)
        return False

    @staticmethod
    def _evaluate_vehicle_current_route_cost(vehicle, city_map):
        """计算车辆当前计划路线的绝对成本，用于订单池内的增量成本比较。"""
        if not vehicle.planned_route:
            return 0.0

        v_state = {
            'time': vehicle.time,
            'last_node': vehicle.last_node,
            'next_node': vehicle.next_node,
            'progress': vehicle.progress
        }
        is_feasible, cost, _ = CoreDispatcher.evaluate_route(
            vehicle.planned_route,
            v_state,
            vehicle.on_board_orders,
            city_map,
            vehicle.capacity,
            v_zone=vehicle.op_zone,
        )
        return cost if is_feasible else 0.0

    @staticmethod
    def _vehicle_committed_passenger_count(vehicle):
        """统计车辆已承诺服务的乘客数。

        已承诺乘客 = 当前已上车乘客 + 已分配但尚未上车的计划接客乘客。
        这样可以避免车辆还没真正接到人时继续无限接单。
        """
        on_board_ids = {order.request_id for order in vehicle.on_board_orders}
        committed_count = sum(order.passenger_count for order in vehicle.on_board_orders)

        for step in vehicle.planned_route:
            if step.get("type") != "O":
                continue
            order = step["order"]
            if order.request_id in on_board_ids:
                continue
            committed_count += order.passenger_count

        return committed_count

    @staticmethod
    def _vehicle_has_capacity_for_order(vehicle, order):
        """判断车辆剩余承诺容量是否足够接收新订单。"""
        return (
            CoreDispatcher._vehicle_committed_passenger_count(vehicle)
            + order.passenger_count
            <= vehicle.capacity
        )

    @staticmethod
    def _calculate_cancel_risk_score(order, current_timestamp):
        """根据乘客已等待时长计算订单池调度用取消风险分，范围为 0~100。"""
        req_time = getattr(order, "req_time", current_timestamp)
        wait_minutes = max(0.0, float(current_timestamp) - float(req_time)) / 60.0
        if wait_minutes <= 10.0:
            return 0.0
        if wait_minutes <= 30.0:
            return ((wait_minutes - 10.0) / 20.0) * 40.0
        if wait_minutes <= 60.0:
            return 40.0 + ((wait_minutes - 30.0) / 30.0) * 40.0
        return 100.0

    @staticmethod
    def process_pool_matching(fleet, city_map, state_lock=None):
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
        
        lock_context = state_lock if state_lock is not None else nullcontext()
        while True:
            with lock_context:
                CoreDispatcher.refresh_scheduled_rest_requests(fleet, city_map)

                if not CoreDispatcher.order_pool:
                    print(f"[Core.Pool] 池中暂无订单...")
                    if CoreDispatcher._collect_forecast_orders(fleet):
                        # 无订单时对全部真正空闲车辆做一次车队级分散热点分配，避免车辆扎堆。
                        CoreDispatcher.assign_idle_parking_targets(fleet, city_map)

                if CoreDispatcher.order_pool:
                    print(f"[Core.Pool] 正在对池中 {len(CoreDispatcher.order_pool)} 个订单执行后悔值统筹调度...")

                assign_count = 0
                # 内部循环：在单次调度周期内尽可能排空订单池
                while CoreDispatcher.order_pool:
                    best_o_idx = -1
                    global_best_v = None
                    global_best_route = None
                    best_priority_score = 0.0
                    best_cancel_risk_score = 0.0
                    order_candidates = []
                    current_timestamp = max(
                        (getattr(v, "time", 0.0) for v in fleet),
                        default=time.time(),
                    ) or time.time()

                    # 评估池内的每一个被积压订单对目前场上所有车辆的组合差价(机会成本)
                    for i in range(len(CoreDispatcher.order_pool)):
                        order = CoreDispatcher.order_pool[i]
                        c1, c2 = float('inf'), float('inf')
                        v1, r1 = None, None

                        for v in fleet:
                            # ===== 查看车辆已承诺容量是否还能接收该订单 =====
                            if not CoreDispatcher._vehicle_has_capacity_for_order(v, order):
                                continue
                            # ===== 疲劳驾驶与休息拦截限流 =====
                            if not CoreDispatcher._vehicle_can_accept_order(v):
                                continue

                            original_cost = CoreDispatcher._evaluate_vehicle_current_route_cost(v, city_map)
                            route, absolute_cost = CoreDispatcher._try_insert_order(v, order, city_map)
                            is_idle = len(v.on_board_orders) == 0 and len(v.planned_route) == 0
                            cost = (
                                absolute_cost - original_cost
                                if route is not None and absolute_cost != float('inf')
                                else float('inf')
                            )

                            # 规则：约束忙碌中车辆强行掉头大绕路；对全空闲车绿灯放行以保障接单率
                            if not is_idle and absolute_cost > 100.0:
                                cost = float('inf')

                            # 维护全局对该订单的“最优车”(c1) 和 “次优车”(c2)，这里使用增量成本。
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
                        regret = None if c2 == float('inf') else max(0.0, c2 - c1)
                        order_candidates.append({
                            "order_index": i,
                            "vehicle": v1,
                            "route": r1,
                            "regret": regret,
                            "cancel_risk_score": CoreDispatcher._calculate_cancel_risk_score(order, current_timestamp),
                        })

                    finite_regrets = [
                        item["regret"]
                        for item in order_candidates
                        if item["regret"] is not None
                    ]
                    max_finite_regret = max(finite_regrets, default=0.0)

                    for item in order_candidates:
                        if item["regret"] is None:
                            normalized_regret_score = 100.0
                        elif max_finite_regret > 0.0:
                            normalized_regret_score = min(100.0, (item["regret"] / max_finite_regret) * 100.0)
                        else:
                            normalized_regret_score = 0.0

                        item["normalized_regret_score"] = normalized_regret_score
                        item["priority_score"] = (
                            0.6 * item["cancel_risk_score"]
                            + 0.4 * normalized_regret_score
                        )

                    if order_candidates:
                        best_candidate = max(
                            order_candidates,
                            key=lambda item: (
                                item["priority_score"],
                                item["cancel_risk_score"],
                                item["normalized_regret_score"],
                            ),
                        )
                        best_o_idx = best_candidate["order_index"]
                        global_best_v = best_candidate["vehicle"]
                        global_best_route = best_candidate["route"]
                        best_priority_score = best_candidate["priority_score"]
                        best_cancel_risk_score = best_candidate["cancel_risk_score"]

                    if best_o_idx != -1:
                        target_o = CoreDispatcher.order_pool.pop(best_o_idx)
                        # 空车热点只是可中断引导；一旦接到真实订单，必须立即清理。
                        CoreDispatcher._clear_idle_parking(global_best_v)
                        global_best_v.planned_route = global_best_route
                        CoreDispatcher.refresh_vehicle_route_metadata(global_best_v, city_map)
                        assign_count += 1
                        print(
                            f"[Core.Pool] [Match] 订单池优先级匹配成功：单 {target_o.request_id} "
                            f"被 {global_best_v.id} 优先划拨！风险分={best_cancel_risk_score:.1f}，综合优先级={best_priority_score:.1f}"
                        )

                        # ==========================================
                        # 打印车辆更新后的轨迹点 (途径站点)
                        # ==========================================
                        # waypoints = []
                        # total_path = []
                        # full_path_node_count = 0
                        # curr_node_id = global_best_v.next_node

                        # for step in global_best_route:
                        #     o = step['order']
                        #     target_node = o.o_node if step['type'] == 'O' else o.d_node
                        #     action_name = "接驾" if step['type'] == 'O' else "送驾"
                        #     waypoints.append(f"[{action_name}{o.request_id}] {target_node.name} ({target_node.lon:.5f},{target_node.lat:.5f})")

                        #     # 顺便统计底层 A* 寻路的精细轨迹点总数
                        #     dist, path = city_map.get_path(city_map.nodes_map[curr_node_id], target_node)
                        #     for nodes in path:
                        #         total_path.append([nodes.lon,nodes.lat])
                        #     full_path_node_count += len(path)
                        #     curr_node_id = target_node.id

                        # print(f"    [轨迹] {global_best_v.id} 任务途径点序列: {' -> '.join(waypoints)}")
                        # print(f"    [明细] 该路线底层共包含 {full_path_node_count} 个路网轨迹点")
                        # print(f"    [明细] 该路线总里程: {total_path} ")
                    else:
                        # 池中剩余订单当前均无法匹配
                        break
                        
                if assign_count > 0:
                    print(f"[Core.Pool] 本轮调度完毕：成功释放 {assign_count} 个积压订单。")

            # 等待 5 秒进行下一轮匹配
            time.sleep(5)

    # ============================================================
    # 功能三：乘客取消订单与司机休息控制
    # 相关方法：cancel_order、request_driver_rest、estimate_vehicle_route_finish_time、
    #          refresh_scheduled_rest_requests
    # ============================================================

    @staticmethod
    def _vehicle_can_accept_order(vehicle):
        """判断车辆当前是否允许继续接收新订单。"""
        return (
            not getattr(vehicle, "is_rest_requested", False)
            and not getattr(vehicle, "is_resting", False)
            and getattr(vehicle, "rest_status", "operating") == "operating"
        )

    @staticmethod
    def _archive_cancelled_order(order, cancel_type="passenger", cancel_time=None):
        """把取消订单记录归档，避免订单从系统中完全消失。"""
        order.status = "cancelled"
        order.cancel_type = cancel_type
        order.cancel_time = cancel_time or datetime.now().replace(microsecond=0)
        if all(o.request_id != order.request_id for o in CoreDispatcher.completed_orders_pool):
            CoreDispatcher.completed_orders_pool.append(order)

    @staticmethod
    def _start_rest_if_ready(vehicle):
        """车辆已经停止接单且没有未完成任务时，立即进入休息状态。"""
        if vehicle.is_rest_requested and not vehicle.on_board_orders and not vehicle.planned_route:
            vehicle.is_resting = True
            vehicle.rest_status = "resting"
            vehicle.rest_started_time = vehicle.time
            vehicle.rest_timer = 0.0
            return True
        return False

    @staticmethod
    def cancel_order(request_id, fleet, city_map, cancel_time=None):
        """取消未上车订单，并在已派车时刷新车辆后续轨迹。

        Args:
            request_id (str): 需要取消的请求 ID。
            fleet (list[Vehicle]): 当前车队。
            city_map (CityGraph): 路网对象。

        Returns:
            dict: 取消结果。status 为 cancelled、rejected 或 not_found。
        """
        request_id = str(request_id)

        for index, order in enumerate(CoreDispatcher.order_pool):
            if str(order.request_id) == request_id:
                CoreDispatcher.order_pool.pop(index)
                CoreDispatcher._archive_cancelled_order(order, cancel_time=cancel_time)
                return {
                    "status": "cancelled",
                    "request_id": request_id,
                    "source": "order_pool",
                    "message": "订单仍在待匹配池中，已取消。",
                }

        for vehicle in fleet:
            if any(str(order.request_id) == request_id for order in vehicle.on_board_orders):
                return {
                    "status": "rejected",
                    "code": "already_on_board",
                    "request_id": request_id,
                    "vehicle_id": vehicle.id,
                    "message": "乘客已上车，乘客端取消订单被拒绝。",
                }

            matched_steps = [
                step for step in vehicle.planned_route
                if str(step["order"].request_id) == request_id
            ]
            if not matched_steps:
                continue

            if not any(step["type"] == "O" for step in matched_steps):
                return {
                    "status": "rejected",
                    "code": "origin_step_missing",
                    "request_id": request_id,
                    "vehicle_id": vehicle.id,
                    "message": "订单已进入上车后的送达阶段，无法按乘客未上车取消处理。",
                }

            cancelled_order = matched_steps[0]["order"]
            vehicle.planned_route = [
                step for step in vehicle.planned_route
                if str(step["order"].request_id) != request_id
            ]
            CoreDispatcher._archive_cancelled_order(cancelled_order, cancel_time=cancel_time)
            path_result = CoreDispatcher.refresh_vehicle_route_metadata(vehicle, city_map)
            CoreDispatcher._start_rest_if_ready(vehicle)
            return {
                "status": "cancelled",
                "request_id": request_id,
                "source": "vehicle_route",
                "vehicle_id": vehicle.id,
                "planned_route": [
                    {
                        "type": step["type"],
                        "request_id": step["order"].request_id,
                    }
                    for step in vehicle.planned_route
                ],
                "planned_route_point": vehicle.planned_route_point,
                "path_result": path_result,
                "message": "订单已从车辆计划路径中移除，车辆轨迹已刷新。",
            }

        for order in CoreDispatcher.completed_orders_pool:
            if str(order.request_id) == request_id:
                return {
                    "status": "rejected",
                    "code": "already_finished_or_cancelled",
                    "request_id": request_id,
                    "message": "订单已结束或已取消，不能重复取消。",
                }

        return {
            "status": "not_found",
            "request_id": request_id,
            "message": "未找到该订单。",
        }

    @staticmethod
    def estimate_vehicle_route_finish_time(vehicle, city_map):
        """估算车辆完成当前已接路线的仿真时间点。"""
        current_node = city_map.nodes_map.get(vehicle.next_node) or city_map.nodes_map.get(vehicle.last_node)
        if current_node is None:
            return None

        finish_time = vehicle.time
        if vehicle.last_node != vehicle.next_node:
            last_node = city_map.nodes_map.get(vehicle.last_node)
            edge_dist = None
            if last_node is not None:
                edge_dist = last_node.neighbors.get(vehicle.next_node)
            if edge_dist is not None:
                finish_time += edge_dist * (1.0 - vehicle.progress) / SPEED_MPS

        for target in CoreDispatcher._planned_route_targets(vehicle):
            dist, _ = city_map.get_path(current_node, target["node"])
            if dist == float("inf"):
                return None
            finish_time += dist / SPEED_MPS
            current_node = target["node"]

        return finish_time

    @staticmethod
    def request_driver_rest(vehicle, city_map, desired_rest_time=None, rest_duration_seconds=None):
        """处理司机端休息请求，并决定车辆是否立刻停止接新单。

        Args:
            vehicle (Vehicle): 请求休息的车辆。
            city_map (CityGraph): 路网对象。
            desired_rest_time (float | None): 期望休息的仿真时间点；为空表示马上收车。
            rest_duration_seconds (float | None): 可选休息时长，限制在 15-30 分钟。

        Returns:
            dict: 车辆休息决策和预计完成时间。
        """
        if rest_duration_seconds is not None:
            vehicle.rest_duration = max(
                MIN_REST_DURATION_SECONDS,
                min(MAX_REST_DURATION_SECONDS, float(rest_duration_seconds)),
            )

        estimated_finish_time = CoreDispatcher.estimate_vehicle_route_finish_time(vehicle, city_map)
        if vehicle.is_resting:
            return {
                "status": "resting",
                "decision": "already_resting",
                "estimated_finish_time": estimated_finish_time,
            }

        if desired_rest_time is None:
            CoreDispatcher._clear_idle_parking(vehicle)
            vehicle.desired_rest_time = None
            vehicle.is_rest_requested = True
            vehicle.rest_status = "closing"
            CoreDispatcher.refresh_vehicle_route_metadata(vehicle, city_map)
            CoreDispatcher._start_rest_if_ready(vehicle)
            return {
                "status": vehicle.rest_status,
                "decision": "close_now",
                "estimated_finish_time": estimated_finish_time,
            }

        desired_rest_time = float(desired_rest_time)
        vehicle.desired_rest_time = desired_rest_time
        threshold_time = desired_rest_time - vehicle.rest_prepare_threshold

        if estimated_finish_time is None or estimated_finish_time >= threshold_time:
            CoreDispatcher._clear_idle_parking(vehicle)
            vehicle.is_rest_requested = True
            vehicle.rest_status = "preparing_closure"
            CoreDispatcher.refresh_vehicle_route_metadata(vehicle, city_map)
            CoreDispatcher._start_rest_if_ready(vehicle)
            return {
                "status": vehicle.rest_status,
                "decision": "prepare_closure",
                "estimated_finish_time": estimated_finish_time,
            }

        if not vehicle.is_rest_requested:
            vehicle.rest_status = "operating"
            vehicle.is_resting = False
        return {
            "status": vehicle.rest_status,
            "decision": "keep_operating_until_rest_time",
            "estimated_finish_time": estimated_finish_time,
        }

    @staticmethod
    def refresh_scheduled_rest_requests(fleet, city_map):
        """周期性检查预约休息车辆，接近休息时间时切换为收车中。"""
        for vehicle in fleet:
            if vehicle.is_resting:
                CoreDispatcher._clear_idle_parking(vehicle)
                if not vehicle.planned_route:
                    vehicle.planned_route_point = []
                continue
            if vehicle.is_rest_requested:
                if not vehicle.planned_route:
                    CoreDispatcher._clear_idle_parking(vehicle)
                    CoreDispatcher.refresh_vehicle_route_metadata(vehicle, city_map)
                CoreDispatcher._start_rest_if_ready(vehicle)
                continue
            if vehicle.desired_rest_time is None:
                continue

            estimated_finish_time = CoreDispatcher.estimate_vehicle_route_finish_time(vehicle, city_map)
            threshold_time = vehicle.desired_rest_time - vehicle.rest_prepare_threshold
            should_close = vehicle.time >= threshold_time
            if estimated_finish_time is not None and estimated_finish_time >= threshold_time:
                should_close = True

            if should_close:
                CoreDispatcher._clear_idle_parking(vehicle)
                vehicle.is_rest_requested = True
                vehicle.rest_status = "closing"
                CoreDispatcher.refresh_vehicle_route_metadata(vehicle, city_map)
                CoreDispatcher._start_rest_if_ready(vehicle)

    # ============================================================
    # 功能四：车辆 GPS 路网吸附
    # 相关方法：_project_point_to_segment、_projection_result、_nearest_road_projection
    # ============================================================

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

    # ============================================================
    # 功能五：订单目标点与轨迹点格式转换
    # 相关方法：_planned_route_targets、_node_to_path_point
    # ============================================================

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
            target_node = order.o_node if step["type"] == "O" else order.d_node
            targets.append({
                "type": step["type"],
                "request_id": order.request_id,
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

    # ============================================================
    # 功能六：空车停靠预测辅助函数
    # 相关方法：_clear_idle_parking、_nearest_graph_node、_collect_forecast_orders、
    #          _select_idle_hotspot、_build_idle_route_from_node
    # ============================================================

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
            request_id = getattr(order, "request_id", None)
            key = str(request_id) if request_id is not None else id(order)
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
    def _forecast_order_signature(orders):
        """生成预测样本签名，用于判断热点缓存是否仍可复用。"""
        latest_time = 0.0
        for order in orders:
            request_time = getattr(order, "request_time", None)
            if isinstance(request_time, datetime):
                order_time = request_time.timestamp()
            else:
                order_time = float(getattr(order, "req_time", 0.0) or 0.0)
            latest_time = max(latest_time, order_time)
        return len(orders), latest_time

    @staticmethod
    def _idle_forecast_cache_is_valid(cache, city_map, order_signature, now_ts):
        """判断空车热点预测缓存是否仍在有效期内。"""
        return (
            cache
            and cache.get("city_map_id") == id(city_map)
            and cache.get("order_signature") == order_signature
            and float(cache.get("expires_at", 0.0)) > now_ts
        )

    @staticmethod
    def _build_idle_hotspot_candidates(predictions, metrics, city_map):
        """把预测结果转成可分配的去重热点候选。"""
        rows = [row for row in predictions if int(row.get("horizon_min", 15)) == 15]
        if not rows:
            rows = list(predictions)

        hotspots_by_node = {}
        for row in rows:
            try:
                pred_count = int(row.get("pred_count", 0))
                target_lon = float(row["o_center_lon"])
                target_lat = float(row["o_center_lat"])
            except (KeyError, TypeError, ValueError):
                continue
            if pred_count <= 0:
                continue

            target_node, snap_distance = CoreDispatcher._nearest_graph_node(city_map, target_lon, target_lat)
            if target_node is None:
                continue

            hotspot = {
                "row": row,
                "node": target_node,
                "node_id": target_node.id,
                "target_lon": target_lon,
                "target_lat": target_lat,
                "pred_count": pred_count,
                "snap_distance": snap_distance,
                "metrics": metrics,
            }
            current = hotspots_by_node.get(target_node.id)
            if (
                current is None
                or pred_count > current["pred_count"]
                or (pred_count == current["pred_count"] and snap_distance < current["snap_distance"])
            ):
                hotspots_by_node[target_node.id] = hotspot

        return sorted(
            hotspots_by_node.values(),
            key=lambda item: (-item["pred_count"], item["snap_distance"], item["node_id"]),
        )

    @staticmethod
    def _build_idle_hotspot_cache(orders, order_signature, city_map, now_ts):
        """刷新未来 15 分钟空车热点预测缓存。"""
        try:
            clean_orders = od_forecast_module.orders_from_insert_riding(
                orders,
                city_map=city_map,
                base_datetime=datetime.fromtimestamp(0),
                speed_mps=SPEED_MPS,
            )
        except Exception as exc:
            print(f"[Core.Planner] 订单预测输入转换失败：{exc}")
            return None
        if not clean_orders:
            return None

        # 沿用现有预测窗口：最近一条历史订单之后的下一个 15 分钟窗口。
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

        hotspots = CoreDispatcher._build_idle_hotspot_candidates(predictions, metrics, city_map)
        generated_at_text = datetime.fromtimestamp(now_ts).isoformat(sep=" ", timespec="seconds")
        cache = {
            "city_map_id": id(city_map),
            "order_signature": order_signature,
            "generated_at": now_ts,
            "generated_at_text": generated_at_text,
            "expires_at": now_ts + CoreDispatcher.IDLE_FORECAST_CACHE_SECONDS,
            "forecast_time": forecast_time,
            "forecast_time_text": forecast_time.isoformat(sep=" ", timespec="seconds"),
            "hotspots": hotspots,
            "metrics": metrics,
        }
        CoreDispatcher.idle_hotspot_cache = cache
        print(f"[Core.Planner] 已刷新空车热点预测缓存，候选热点 {len(hotspots)} 个。")
        return cache

    @staticmethod
    def _get_idle_hotspot_cache(fleet, city_map):
        """读取或刷新车队级空车热点预测缓存。"""
        orders = CoreDispatcher._collect_forecast_orders(fleet)
        if not orders:
            return None

        now_ts = time.time()
        order_signature = CoreDispatcher._forecast_order_signature(orders)
        cache = CoreDispatcher.idle_hotspot_cache
        if CoreDispatcher._idle_forecast_cache_is_valid(cache, city_map, order_signature, now_ts):
            return cache

        return CoreDispatcher._build_idle_hotspot_cache(orders, order_signature, city_map, now_ts)

    @staticmethod
    def _is_idle_vehicle_available(vehicle):
        """判断车辆是否可参与空车热点分配。"""
        return (
            len(vehicle.on_board_orders) == 0
            and len(vehicle.planned_route) == 0
            and CoreDispatcher._vehicle_can_accept_order(vehicle)
        )

    @staticmethod
    def _idle_target_cache_time(vehicle):
        """读取车辆当前空车热点所属的预测缓存时间戳。"""
        forecast = getattr(vehicle, "idle_forecast", None) or {}
        return forecast.get("forecast_generated_at")

    @staticmethod
    def _idle_target_matches_cache(vehicle, cache):
        """判断车辆当前空车目标是否来自本轮有效预测缓存。"""
        return (
            getattr(vehicle, "idle_target", None)
            and getattr(vehicle, "planned_route_point", None)
            and CoreDispatcher._idle_target_cache_time(vehicle) == cache.get("generated_at")
        )

    @staticmethod
    def _idle_target_node(vehicle, city_map):
        """读取车辆当前空车热点吸附到的路网节点。"""
        target = getattr(vehicle, "idle_target", None) or {}
        node_id = target.get("node_id")
        return city_map.nodes_map.get(node_id) if node_id else None

    @staticmethod
    def _rank_idle_hotspots_for_vehicle(vehicle, cache, city_map, assigned_nodes, rejected_node_ids):
        """按需求优先、分散补偿和车辆距离为单车排序热点候选。"""
        start_node = city_map.nodes_map.get(vehicle.next_node) or city_map.nodes_map.get(vehicle.last_node)
        if start_node is None:
            return []

        assigned_node_ids = {node.id for node in assigned_nodes}
        ranked = []
        for hotspot in cache.get("hotspots", []):
            node = hotspot["node"]
            if node.id in assigned_node_ids or node.id in rejected_node_ids:
                continue

            vehicle_distance = AuxiliaryFunctions.haversine_distance(
                start_node.lon,
                start_node.lat,
                node.lon,
                node.lat,
            )
            if assigned_nodes:
                nearest_assigned_distance = min(
                    AuxiliaryFunctions.haversine_distance(node.lon, node.lat, assigned.lon, assigned.lat)
                    for assigned in assigned_nodes
                )
            else:
                nearest_assigned_distance = float("inf")

            is_spaced = (
                not assigned_nodes
                or nearest_assigned_distance >= CoreDispatcher.IDLE_MIN_HOTSPOT_DISTANCE_METERS
            )
            dispersion_bonus = (
                100.0
                if nearest_assigned_distance == float("inf")
                else min(nearest_assigned_distance, CoreDispatcher.IDLE_MIN_HOTSPOT_DISTANCE_METERS)
                / CoreDispatcher.IDLE_MIN_HOTSPOT_DISTANCE_METERS
                * 100.0
            )
            score = hotspot["pred_count"] * 1000.0 + dispersion_bonus - vehicle_distance / 1000.0
            ranked.append((is_spaced, score, hotspot))

        preferred = [item for item in ranked if item[0]]
        usable = preferred if preferred else ranked
        return [
            item[2]
            for item in sorted(
                usable,
                key=lambda item: (item[1], item[2]["pred_count"]),
                reverse=True,
            )
        ]

    @staticmethod
    def _write_idle_hotspot_to_vehicle(vehicle, city_map, cache, hotspot, assignment_rank):
        """把一个热点写入车辆，并刷新前端展示轨迹。"""
        start_node = city_map.nodes_map.get(vehicle.next_node) or city_map.nodes_map.get(vehicle.last_node)
        if start_node is None:
            return False

        row = hotspot["row"]
        target_node = hotspot["node"]
        vehicle.idle_forecast = {
            "forecast_start_time": row.get("forecast_start_time"),
            "forecast_end_time": row.get("forecast_end_time"),
            "horizon_min": int(row.get("horizon_min", 15)),
            "pred_count": int(hotspot.get("pred_count", 0)),
            "metrics": cache.get("metrics", []),
            "forecast_generated_at": cache.get("generated_at"),
            "forecast_generated_at_text": cache.get("generated_at_text"),
            "assignment_rank": assignment_rank,
            "assigned_hotspot_count": None,
            "assignment_strategy": "demand_first_dispersion",
        }
        vehicle.idle_target = {
            "lon": hotspot["target_lon"],
            "lat": hotspot["target_lat"],
            "node_id": target_node.id,
            "node_name": target_node.name,
            "node_lon": target_node.lon,
            "node_lat": target_node.lat,
            "snap_distance_to_node": hotspot["snap_distance"],
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
    def assign_idle_parking_targets(fleet, city_map, target_vehicle=None):
        """按车队级预测热点池为空车分散分配停靠目标。

        Args:
            fleet (list[Vehicle]): 当前车队。
            city_map (CityGraph): 路网对象。
            target_vehicle (Vehicle | None): 兼容单车入口；为空时批量处理全部空车。

        Returns:
            int: 本次新分配成功的车辆数量。
        """
        cache = CoreDispatcher._get_idle_hotspot_cache(fleet, city_map)
        if not cache or not cache.get("hotspots"):
            return 0

        idle_vehicles = [v for v in fleet if CoreDispatcher._is_idle_vehicle_available(v)]
        if target_vehicle is not None and target_vehicle not in idle_vehicles:
            return 0

        assigned_nodes = []
        vehicles_to_assign = []
        for vehicle in idle_vehicles:
            if CoreDispatcher._idle_target_matches_cache(vehicle, cache):
                node = CoreDispatcher._idle_target_node(vehicle, city_map)
                if node is not None:
                    assigned_nodes.append(node)
                continue

            if target_vehicle is not None and vehicle is not target_vehicle:
                continue

            if vehicle.idle_target or vehicle.idle_forecast or vehicle.planned_route_point:
                CoreDispatcher._clear_idle_parking(vehicle)
                vehicle.planned_route_point = []

            vehicles_to_assign.append(vehicle)

        assigned_count = 0
        for vehicle in vehicles_to_assign:
            rejected_node_ids = set()
            while True:
                candidates = CoreDispatcher._rank_idle_hotspots_for_vehicle(
                    vehicle,
                    cache,
                    city_map,
                    assigned_nodes,
                    rejected_node_ids,
                )
                if not candidates:
                    break

                hotspot = candidates[0]
                assignment_rank = len(assigned_nodes) + 1
                if CoreDispatcher._write_idle_hotspot_to_vehicle(vehicle, city_map, cache, hotspot, assignment_rank):
                    assigned_nodes.append(hotspot["node"])
                    assigned_count += 1
                    break

                rejected_node_ids.add(hotspot["node_id"])

        active_count = 0
        for vehicle in idle_vehicles:
            if CoreDispatcher._idle_target_matches_cache(vehicle, cache):
                active_count += 1
        for vehicle in idle_vehicles:
            if CoreDispatcher._idle_target_matches_cache(vehicle, cache):
                vehicle.idle_forecast["assigned_hotspot_count"] = active_count

        return assigned_count

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
                    "request_id": None,
                    "target_node": CoreDispatcher._node_to_path_point(target_node),
                    "distance": dist,
                    "path": path_points,
                    "forecast": vehicle.idle_forecast,
                }
            ],
        }

    # ============================================================
    # 功能七：车辆路径重建与前端轨迹元数据刷新
    # 相关方法：rebuild_vehicle_path_from_node、refresh_vehicle_route_metadata、_projection_to_path_point
    # ============================================================

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
                "request_id": target["request_id"],
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

    # ============================================================
    # 功能八：GPS 实时路径更新与上下客状态同步
    # 相关方法：sync_vehicle_route_progress、_apply_reached_route_step、
    #          _sync_nearby_route_target、rebuild_vehicle_path_from_gps
    # ============================================================

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
            target_node = order.o_node if step["type"] == "O" else order.d_node
            if target_node.id != current_node.id:
                break

            if step["type"] == "O":
                if all(o.request_id != order.request_id for o in vehicle.on_board_orders):
                    vehicle.on_board_orders.append(order)
                order.actual_pick_time = order.actual_pick_time or vehicle.time
                action = "pickup"
            else:
                vehicle.on_board_orders = [o for o in vehicle.on_board_orders if o.request_id != order.request_id]
                if order not in CoreDispatcher.completed_orders_pool:
                    CoreDispatcher.completed_orders_pool.append(order)
                action = "dropoff"

            vehicle.planned_route.pop(0)
            changed_steps.append({
                "action": action,
                "type": step["type"],
                "request_id": order.request_id,
                "node": CoreDispatcher._node_to_path_point(target_node),
            })

        return changed_steps

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
        if step["type"] == "O":
            if all(o.request_id != order.request_id for o in vehicle.on_board_orders):
                vehicle.on_board_orders.append(order)
            order.actual_pick_time = order.actual_pick_time or vehicle.time
            action = "pickup"
        else:
            vehicle.on_board_orders = [o for o in vehicle.on_board_orders if o.request_id != order.request_id]
            if order not in CoreDispatcher.completed_orders_pool:
                CoreDispatcher.completed_orders_pool.append(order)
            action = "dropoff"

        return {
            "action": action,
            "type": step["type"],
            "request_id": order.request_id,
            "node": CoreDispatcher._node_to_path_point(target_node),
        }

    @staticmethod
    def _sync_nearby_route_target(vehicle, lon, lat, threshold_meters=10.0):
        """GPS 靠近当前下一步接送点时，完成一个上下客步骤。

        Args:
            vehicle (Vehicle): 需要同步上下客状态的车辆。
            lon (float): 车辆当前 GPS 经度。
            lat (float): 车辆当前 GPS 纬度。
            threshold_meters (float): 触发上下客的距离阈值，单位米。

        Returns:
            list[dict]: 本次触发的 pickup/dropoff 变更列表。
        """
        if not vehicle.planned_route:
            return []

        step = vehicle.planned_route[0]
        order = step["order"]
        target_node = order.o_node if step["type"] == "O" else order.d_node
        distance_to_target = AuxiliaryFunctions.haversine_distance(
            lon,
            lat,
            target_node.lon,
            target_node.lat,
        )
        if distance_to_target > threshold_meters:
            return []

        vehicle.planned_route.pop(0)
        changed_step = CoreDispatcher._apply_reached_route_step(vehicle, step, target_node)
        changed_step["distance_to_target"] = distance_to_target
        return [changed_step]

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
        # GPS 先吸附到路网边线，避免原始坐标偏移导致车辆脱离道路。
        projection = CoreDispatcher._nearest_road_projection(city_map, lon, lat, vehicle)
        if projection is None:
            return None

        next_node = projection["next_node"]
        # 只在真实 GPS 靠近当前下一步接送点时触发一次上下客，避免 GPS 跳跃导致批量完成订单。
        changed_steps = CoreDispatcher._sync_nearby_route_target(vehicle, lon, lat)

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
        result["on_board_orders"] = [o.request_id for o in vehicle.on_board_orders]
        result["planned_route"] = [
            {
                "type": step["type"],
                "request_id": step["order"].request_id,
                "target_node": CoreDispatcher._node_to_path_point(
                    step["order"].o_node if step["type"] == "O" else step["order"].d_node
                ),
            }
            for step in vehicle.planned_route
        ]
        return result

    # ============================================================
    # 功能九：空车停靠场景入口
    # 相关方法：idle_parking_scenario
    # ============================================================

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
        if not CoreDispatcher._is_idle_vehicle_available(vehicle):
            return False

        fleet_scope = fleet or [vehicle]
        CoreDispatcher.assign_idle_parking_targets(fleet_scope, city_map, target_vehicle=vehicle)
        return bool(vehicle.idle_target and vehicle.planned_route_point)

    # ============================================================
    # 功能十：停止接单预测预留入口
    # 相关方法：stop_order_prediction
    # ============================================================

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
