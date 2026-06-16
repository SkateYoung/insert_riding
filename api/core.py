# core.py
"""打车系统的大脑业务算子主控层。
负责派单、重组架构、以及闲置管控等绝对智能内核逻辑。
"""

import copy
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timedelta
from . import persistence
from .models import MAX_REST_DURATION_SECONDS, MIN_REST_DURATION_SECONDS, SPEED_MPS
from .auxiliary import AuxiliaryFunctions
from forecast import od_forecast_module
from forecast.amap_eta_correct import DEFAULT_AMAP_KEY, AmapEtaCorrectClient, build_eta_pipeline_from_astar

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

    # 高德纠偏 ETA 后台刷新配置：ETA 仍由独立线程周期刷新，不参与派单评分。
    ETA_REFRESH_INTERVAL_SECONDS = 5.0
    ROUTE_GRASP_REFRESH_INTERVAL_SECONDS = 5.0
    eta_last_refresh_timestamp = None
    route_grasp_last_refresh_timestamp = None
    eta_service = None
    DEFAULT_AMAP_API_KEY = DEFAULT_AMAP_KEY
    eta_service_api_key = DEFAULT_AMAP_API_KEY
    route_grasp_auto_submit_enabled = False
    route_grasp_apply_lock = None
    route_grasp_executor = None
    route_grasp_executor_workers = 4
    route_grasp_inflight = set()
    route_grasp_inflight_lock = threading.Lock()

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
        persistence.record_order_created(order, city_map, status="pooled")
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
                        route_result = CoreDispatcher.refresh_vehicle_route_metadata(global_best_v, city_map)
                        target_o.status = "waiting_pickup"
                        persistence.record_dispatch_assignment(
                            target_o,
                            global_best_v,
                            city_map=city_map,
                            path_result=route_result,
                            details={
                                "cancel_risk_score": best_cancel_risk_score,
                                "priority_score": best_priority_score,
                            },
                        )
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
        persistence.record_order_snapshot(order, status="cancelled")

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
            persistence.record_vehicle_route(vehicle, path_result=path_result)
            persistence.record_vehicle_runtime(vehicle)
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
            persistence.record_vehicle_runtime(vehicle)
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
            persistence.record_vehicle_runtime(vehicle)
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
        vehicle.idle_target_eta_seconds = None
        vehicle.idle_target_eta_time = None
        vehicle.idle_target_eta_status = None
        vehicle.idle_target_eta_error = None
        if not getattr(vehicle, "planned_route", None):
            CoreDispatcher._clear_route_grasp_state(vehicle)

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
        persistence.record_hotspot_forecast(vehicle)
        persistence.record_vehicle_route(vehicle, path_result=result)
        persistence.record_vehicle_runtime(vehicle)
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
    def _vehicle_grasp_route_version(vehicle):
        """生成车辆当前计划路线的纠偏版本签名。

        说明:
            该版本只表达订单/热点路线是否变化，不包含 GPS 所在边和进度。
            GPS 行进只裁剪既有纠偏路线，不触发新的高德纠偏请求。
        """
        parts = [
            str(vehicle.id),
        ]
        if getattr(vehicle, "planned_route", None):
            for step in vehicle.planned_route:
                order = step.get("order")
                request_id = getattr(order, "request_id", "")
                parts.append(f"{step.get('type')}:{request_id}")
        elif getattr(vehicle, "idle_target", None):
            target = vehicle.idle_target or {}
            parts.append(f"IDLE:{target.get('node_id')}:{target.get('generated_at')}")
        else:
            parts.append("EMPTY")
        return "|".join(parts)

    @staticmethod
    def _route_result_to_grasp_raw_segments(result):
        """把当前 A* 路线结果转换成后台纠偏线程可消费的分段快照。"""
        raw_segments = []
        for index, segment in enumerate((result or {}).get("segments", [])):
            points = copy.deepcopy(segment.get("path") or [])
            if not points:
                continue
            step_type = segment.get("type")
            request_id = segment.get("request_id")
            start_node_id = points[0].get("id") if isinstance(points[0], dict) else None
            end_node_id = points[-1].get("id") if isinstance(points[-1], dict) else None
            raw_segment = {
                "index": index,
                "type": step_type,
                "request_id": str(request_id) if request_id is not None else None,
                "startNodeId": start_node_id,
                "endNodeId": end_node_id,
                "endStep": {
                    "type": step_type,
                    "orderId": str(request_id) if request_id is not None else None,
                },
                "target_node": copy.deepcopy(segment.get("target_node")),
                "distance": segment.get("distance"),
                "aStarDistanceM": segment.get("distance"),
                "points": points,
            }
            if "forecast" in segment:
                raw_segment["forecast"] = copy.deepcopy(segment.get("forecast"))
            raw_segments.append(raw_segment)
        return raw_segments

    @staticmethod
    def _clear_route_grasp_state(vehicle):
        """清理车辆路线纠偏与空车热点 ETA 状态。

        Args:
            vehicle (Vehicle): 需要清理纠偏状态的车辆。

        Side Effects:
            清空已纠偏总路线、已纠偏分段、原始分段、纠偏状态和空车热点 ETA。
        """
        vehicle.planned_route_grasped_point = []
        vehicle.planned_route_segment_grasped_point = []
        vehicle.planned_route_segment_raw_point = []
        vehicle.planned_route_grasp_status = None
        vehicle.planned_route_grasp_error = None
        vehicle.planned_route_grasp_route_version = None
        vehicle.idle_target_eta_seconds = None
        vehicle.idle_target_eta_time = None
        vehicle.idle_target_eta_status = None
        vehicle.idle_target_eta_error = None

    @staticmethod
    def _point_distance_m(a, b):
        """计算两个轨迹点之间的球面距离。"""
        return AuxiliaryFunctions.haversine_distance(
            float(a["lon"]),
            float(a["lat"]),
            float(b["lon"]),
            float(b["lat"]),
        )

    @staticmethod
    def _project_point_on_polyline_segment(point, start, end):
        """把一个点近似投影到经纬度折线段上。

        Args:
            point (dict): 待投影点，包含 lon/lat。
            start (dict): 线段起点，包含 lon/lat。
            end (dict): 线段终点，包含 lon/lat。

        Returns:
            dict: 投影点、线段进度和距离信息。
        """
        ax, ay = float(start["lon"]), float(start["lat"])
        bx, by = float(end["lon"]), float(end["lat"])
        px, py = float(point["lon"]), float(point["lat"])
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq <= 0:
            progress = 0.0
        else:
            progress = ((px - ax) * dx + (py - ay) * dy) / length_sq
            progress = max(0.0, min(1.0, progress))
        projected = {
            "lon": ax + dx * progress,
            "lat": ay + dy * progress,
        }
        distance = CoreDispatcher._point_distance_m(point, projected)
        return {
            "point": projected,
            "progress": progress,
            "distance": distance,
        }

    @staticmethod
    def _trim_points_from_position(points, start_point):
        """从旧纠偏轨迹中裁出车辆当前位置之后的剩余轨迹。

        Args:
            points (list[dict]): 旧的已纠偏分段轨迹。
            start_point (dict): 新 GPS 投影点，会作为裁剪后轨迹首点。

        Returns:
            list[dict]: 以 start_point 开头、逐渐驶向原目标点的剩余轨迹。
        """
        normalized = [copy.deepcopy(p) for p in points or [] if p.get("lon") is not None and p.get("lat") is not None]
        if len(normalized) < 2:
            return []

        best = None
        for index in range(len(normalized) - 1):
            projection = CoreDispatcher._project_point_on_polyline_segment(
                start_point,
                normalized[index],
                normalized[index + 1],
            )
            if best is None or projection["distance"] < best["distance"]:
                best = {
                    **projection,
                    "index": index,
                }

        if best is None:
            return []

        snapped_start = copy.deepcopy(start_point)
        snapped_start["lon"] = best["point"]["lon"]
        snapped_start["lat"] = best["point"]["lat"]
        snapped_start["is_grasp_projection"] = True
        snapped_start["distance_to_gps"] = best["distance"]

        trimmed = [snapped_start]
        next_index = best["index"] + 1
        if best["progress"] >= 0.98:
            next_index += 1
        trimmed.extend(copy.deepcopy(normalized[next_index:]))
        if len(trimmed) == 1:
            trimmed.append(copy.deepcopy(normalized[-1]))
        return trimmed

    @staticmethod
    def _route_segment_key(segment):
        """生成路线分段匹配键，用于在新旧 O/D/IDLE 分段之间定位同一目标。"""
        return (
            segment.get("type"),
            str(segment.get("request_id")) if segment.get("request_id") is not None else None,
        )

    @staticmethod
    def _trim_grasped_segments_to_position(grasped_segments, raw_segments, start_point=None):
        """按车辆 GPS 在纠偏路线上的投影点裁剪一组已纠偏分段。

        Args:
            grasped_segments (list[dict]): 已纠偏分段，可能来自车辆当前状态或高德新返回结果。
            raw_segments (list[dict]): GPS 更新后重新生成的原始剩余分段。
            start_point (dict | None): 车辆真实 GPS 点；为空时退回 raw segment 起点。

        Returns:
            list[dict]: 从当前车辆位置开始的已纠偏分段；缺失的分段退回 raw segment。
        """
        previous_by_key = {}
        for segment in grasped_segments or []:
            previous_by_key.setdefault(CoreDispatcher._route_segment_key(segment), segment)

        trimmed_segments = []
        for index, raw_segment in enumerate(raw_segments or []):
            raw_points = copy.deepcopy(raw_segment.get("points") or [])
            if len(raw_points) < 2:
                continue

            previous = previous_by_key.get(CoreDispatcher._route_segment_key(raw_segment))
            previous_points = (previous or {}).get("points") or (previous or {}).get("path") or []
            if previous is not None:
                if index == 0:
                    points = CoreDispatcher._trim_points_from_position(
                        previous_points,
                        start_point or raw_points[0],
                    )
                else:
                    points = copy.deepcopy(previous_points)
            else:
                points = []

            if len(points) < 2:
                points = raw_points
                source = "raw_trim_fallback"
                grasp_meta = {"ok": False, "error": "trim_fallback"}
            else:
                source = f"{previous.get('source', 'grasproad')}_trimmed" if previous is not None else "raw_trim_fallback"
                grasp_meta = copy.deepcopy((previous or {}).get("grasp") or {})
                grasp_meta["trimmed_from_previous"] = previous is not None

            segment = copy.deepcopy(raw_segment)
            segment["points"] = points
            segment["source"] = source
            segment["grasp"] = grasp_meta
            trimmed_segments.append(segment)
        return trimmed_segments

    @staticmethod
    def _trim_vehicle_grasped_route_from_result(vehicle, result, start_point=None):
        """GPS 更新时只裁剪既有纠偏路线，不重新请求高德。

        Args:
            vehicle (Vehicle): GPS 刚更新的车辆。
            result (dict): 本次 GPS 更新后的原始剩余路径结果。
            start_point (dict | None): 车辆真实 GPS 点；用于吸附到既有纠偏路线。

        Returns:
            bool: 成功更新 raw segments 或裁剪纠偏路线返回 True。

        Side Effects:
            更新 planned_route_segment_raw_point，并在已有纠偏路线时同步缩短
            planned_route_segment_grasped_point/planned_route_grasped_point。
        """
        raw_segments = CoreDispatcher._route_result_to_grasp_raw_segments(result)
        if not raw_segments:
            CoreDispatcher._clear_route_grasp_state(vehicle)
            return False

        vehicle.planned_route_segment_raw_point = raw_segments
        if getattr(vehicle, "planned_route_grasp_route_version", None) is None:
            vehicle.planned_route_grasp_route_version = CoreDispatcher._vehicle_grasp_route_version(vehicle)

        grasped_segments = getattr(vehicle, "planned_route_segment_grasped_point", None) or []
        if not grasped_segments:
            return True

        if start_point is None:
            gps = getattr(vehicle, "gps", {}) or {}
            if gps.get("lon") is not None and gps.get("lat") is not None:
                start_point = {"lon": gps["lon"], "lat": gps["lat"], "id": "vehicle_gps"}

        trimmed_segments = CoreDispatcher._trim_grasped_segments_to_position(
            grasped_segments,
            raw_segments,
            start_point=start_point,
        )
        if trimmed_segments:
            vehicle.planned_route_segment_grasped_point = trimmed_segments
            vehicle.planned_route_grasped_point = CoreDispatcher._combine_grasped_segments(trimmed_segments)
        return True

    @classmethod
    def configure_route_grasp_async(cls, state_lock=None, enabled=True, max_workers=None):
        """配置路线更新触发式异步纠偏执行器。

        Args:
            state_lock (RLock | None): 写回车辆状态时复用的全局状态锁。
            enabled (bool): 是否启用路线更新后的自动异步提交。
            max_workers (int | None): 纠偏线程池最大工作线程数；为空时使用默认值。

        Side Effects:
            初始化或复用 ThreadPoolExecutor，并记录写回锁。
        """
        # 纠偏请求在线程池执行；结果写回仍使用全局状态锁，避免与派单/GPS 更新并发写车辆。
        cls.route_grasp_apply_lock = state_lock
        cls.route_grasp_auto_submit_enabled = bool(enabled)
        if max_workers is not None:
            cls.route_grasp_executor_workers = max(1, int(max_workers))
        if cls.route_grasp_auto_submit_enabled and cls.route_grasp_executor is None:
            cls.route_grasp_executor = ThreadPoolExecutor(
                max_workers=cls.route_grasp_executor_workers,
                thread_name_prefix="RouteGraspRequest",
            )

    @classmethod
    def disable_route_grasp_async(cls, wait=False):
        """关闭路线更新触发式异步纠偏。

        Args:
            wait (bool): 是否等待线程池中已提交的纠偏任务结束。

        Side Effects:
            停止继续提交新纠偏任务，并清理正在执行任务的去重标记。
        """
        cls.route_grasp_auto_submit_enabled = False
        executor = cls.route_grasp_executor
        cls.route_grasp_executor = None
        if executor is not None:
            executor.shutdown(wait=wait)
        with cls.route_grasp_inflight_lock:
            cls.route_grasp_inflight.clear()

    @classmethod
    def route_grasp_inflight_count(cls):
        """读取当前正在执行的纠偏任务数量。

        Returns:
            int: 线程池中仍在执行或等待写回的纠偏任务数。
        """
        with cls.route_grasp_inflight_lock:
            return len(cls.route_grasp_inflight)

    @staticmethod
    def _route_grasp_job_from_vehicle(vehicle):
        """从车辆 pending 路线快照构造一次纠偏任务。

        Args:
            vehicle (Vehicle): 已由路线更新逻辑写入 raw segments 的车辆。

        Returns:
            dict | None: 可提交到纠偏线程池的任务快照；状态不满足时返回 None。

        Side Effects:
            如果当前车辆路线版本已经变化，会把纠偏状态置为 stale。
        """
        route_version = getattr(vehicle, "planned_route_grasp_route_version", None)
        raw_segments = getattr(vehicle, "planned_route_segment_raw_point", None) or []
        if getattr(vehicle, "planned_route_grasp_status", None) != "pending":
            return None
        if not route_version or not raw_segments:
            return None
        # 任务生成前先校验版本，防止把旧 raw segments 提交给高德。
        if route_version != CoreDispatcher._vehicle_grasp_route_version(vehicle):
            vehicle.planned_route_grasp_status = "stale"
            vehicle.planned_route_grasp_error = "route_version_changed"
            return None
        return {
            "vehicle_id": str(vehicle.id),
            "route_version": route_version,
            "segments": copy.deepcopy(raw_segments),
        }

    @classmethod
    def _submit_vehicle_route_grasp_async(cls, vehicle):
        """异步提交当前车辆的待纠偏路线任务。

        Args:
            vehicle (Vehicle): 路线刚更新、且纠偏状态为 pending 的车辆。

        Returns:
            bool: 成功提交新任务返回 True；未启用、无任务或重复提交返回 False。

        Side Effects:
            向线程池提交高德纠偏请求；当前调用栈不等待高德返回。
        """
        if not cls.route_grasp_auto_submit_enabled:
            return False

        job = cls._route_grasp_job_from_vehicle(vehicle)
        if not job:
            return False

        # 支持测试或初始化顺序下的懒创建；正常系统启动时会先 configure。
        if cls.route_grasp_executor is None:
            cls.configure_route_grasp_async(
                state_lock=cls.route_grasp_apply_lock,
                enabled=True,
                max_workers=cls.route_grasp_executor_workers,
            )

        job_key = (job["vehicle_id"], job["route_version"])
        with cls.route_grasp_inflight_lock:
            # 同一辆车同一版本只允许存在一个在途纠偏任务，避免重复请求高德。
            if job_key in cls.route_grasp_inflight:
                return False
            cls.route_grasp_inflight.add(job_key)

        cls.route_grasp_last_refresh_timestamp = time.time()
        # 网络请求和路线纠偏都在线程池执行，避免阻塞派单、GPS 更新或接口返回。
        cls.route_grasp_executor.submit(cls._execute_vehicle_route_grasp_job, vehicle, job, job_key)
        return True

    @staticmethod
    def _mark_vehicle_route_grasp_pending(vehicle, result):
        """路线刷新后记录原始分段，并触发异步高德纠偏。

        Args:
            vehicle (Vehicle): 路线刚刷新完成的车辆。
            result (dict): 本地 A* 生成的总路线和分段路线结果。

        Side Effects:
            写入 raw segments、纠偏版本和 pending 状态；如果异步纠偏已启用，会立即提交线程池任务。
        """
        raw_segments = CoreDispatcher._route_result_to_grasp_raw_segments(result)
        if not raw_segments:
            CoreDispatcher._clear_route_grasp_state(vehicle)
            return
        # raw segments 是纠偏线程消费的稳定快照，避免线程读到后续被修改的路线对象。
        vehicle.planned_route_segment_raw_point = raw_segments
        vehicle.planned_route_grasp_route_version = CoreDispatcher._vehicle_grasp_route_version(vehicle)
        vehicle.planned_route_grasp_status = "pending"
        vehicle.planned_route_grasp_error = None
        if not any(segment.get("type") == "IDLE" for segment in raw_segments):
            vehicle.idle_target_eta_seconds = None
            vehicle.idle_target_eta_time = None
            vehicle.idle_target_eta_status = None
            vehicle.idle_target_eta_error = None
        CoreDispatcher._submit_vehicle_route_grasp_async(vehicle)
        persistence.record_vehicle_route(vehicle, path_result=result)
        persistence.record_vehicle_runtime(vehicle)

    @staticmethod
    def _combine_grasped_segments(segments):
        """拼接分段纠偏轨迹为整条路线，去掉相邻段首尾重复点。"""
        points = []
        for segment in segments or []:
            segment_points = segment.get("points") or []
            if points and segment_points:
                points.extend(copy.deepcopy(segment_points[1:]))
            else:
                points.extend(copy.deepcopy(segment_points))
        return points

    @staticmethod
    def refresh_vehicle_route_metadata(vehicle, city_map, start_node=None, submit_grasp=True):
        """刷新车辆当前 GPS 和前端展示所需路径元数据。

        Args:
            vehicle (Vehicle): 需要同步元数据的车辆。
            city_map (CityGraph): 路网对象。
            start_node (Node | None): 指定刷新起点；为空时使用车辆 next_node/last_node。
            submit_grasp (bool): 是否在路线更新后立即提交异步高德纠偏。

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
            CoreDispatcher._clear_route_grasp_state(vehicle)
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
            CoreDispatcher._clear_route_grasp_state(vehicle)
            return None

        vehicle.planned_route_point = result["path"]
        if submit_grasp:
            CoreDispatcher._mark_vehicle_route_grasp_pending(vehicle, result)
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
    def sync_vehicle_route_progress(vehicle, city_map, current_node, current_timestamp=None):
        """根据车辆到达的路网节点同步上下客状态和剩余计划。

        Args:
            vehicle (Vehicle): 需要推进订单状态的车辆。
            city_map (CityGraph): 路网对象，当前函数保留该参数用于接口一致性。
            current_node (Node): 车辆已到达的路网节点。
            current_timestamp (float | None): 真实业务时间戳；为空时使用当前系统时间。

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
        event_time = float(current_timestamp if current_timestamp is not None else time.time())

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
                order.actual_pick_time = order.actual_pick_time or event_time
                order.status = "riding"
                order.estimated_arrival_time = order.actual_pick_time
                order.estimated_arrival_eta_seconds = 0
                action = "pickup"
                persistence.record_order_snapshot(order, status="riding", vehicle=vehicle)
            else:
                vehicle.on_board_orders = [o for o in vehicle.on_board_orders if o.request_id != order.request_id]
                order.status = "completed"
                order.completion_time = order.completion_time or event_time
                order.estimated_dropoff_time = order.completion_time
                order.estimated_dropoff_eta_seconds = 0
                order.eta_status = "completed"
                order.eta_error = None
                if order not in CoreDispatcher.completed_orders_pool:
                    CoreDispatcher.completed_orders_pool.append(order)
                action = "dropoff"
                persistence.record_order_snapshot(order, status="completed", vehicle=vehicle)

            vehicle.planned_route.pop(0)
            changed_steps.append({
                "action": action,
                "type": step["type"],
                "request_id": order.request_id,
                "node": CoreDispatcher._node_to_path_point(target_node),
            })

        return changed_steps

    @staticmethod
    def _apply_reached_route_step(vehicle, step, target_node, current_timestamp=None):
        """应用一个已到达接送点的订单步骤。

        Args:
            vehicle (Vehicle): 被更新上下客状态的车辆。
            step (dict): planned_route 中的步骤，包含 type 和 order。
            target_node (Node): 当前步骤对应的接客或送客节点。
            current_timestamp (float | None): 真实业务时间戳；为空时使用当前系统时间。

        Returns:
            dict: 描述本次 pickup/dropoff 的变更记录。

        Note:
            当前用于前端 GPS 模拟越点判断。实际生产系统中，上下客确认通常由司机端或乘客端事件触发。
        """
        order = step["order"]
        event_time = float(current_timestamp if current_timestamp is not None else time.time())
        if step["type"] == "O":
            if all(o.request_id != order.request_id for o in vehicle.on_board_orders):
                vehicle.on_board_orders.append(order)
            order.actual_pick_time = order.actual_pick_time or event_time
            order.status = "riding"
            order.estimated_arrival_time = order.actual_pick_time
            order.estimated_arrival_eta_seconds = 0
            action = "pickup"
            persistence.record_order_snapshot(order, status="riding", vehicle=vehicle)
        else:
            vehicle.on_board_orders = [o for o in vehicle.on_board_orders if o.request_id != order.request_id]
            order.status = "completed"
            order.completion_time = order.completion_time or event_time
            order.estimated_dropoff_time = order.completion_time
            order.estimated_dropoff_eta_seconds = 0
            order.eta_status = "completed"
            order.eta_error = None
            if order not in CoreDispatcher.completed_orders_pool:
                CoreDispatcher.completed_orders_pool.append(order)
            action = "dropoff"
            persistence.record_order_snapshot(order, status="completed", vehicle=vehicle)

        return {
            "action": action,
            "type": step["type"],
            "request_id": order.request_id,
            "node": CoreDispatcher._node_to_path_point(target_node),
        }

    @staticmethod
    def _sync_nearby_route_target(vehicle, lon, lat, threshold_meters=10.0, current_timestamp=None):
        """GPS 靠近当前下一步接送点时，完成一个上下客步骤。

        Args:
            vehicle (Vehicle): 需要同步上下客状态的车辆。
            lon (float): 车辆当前 GPS 经度。
            lat (float): 车辆当前 GPS 纬度。
            threshold_meters (float): 触发上下客的距离阈值，单位米。
            current_timestamp (float | None): 真实业务时间戳；为空时使用当前系统时间。

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
        changed_step = CoreDispatcher._apply_reached_route_step(
            vehicle,
            step,
            target_node,
            current_timestamp=current_timestamp,
        )
        changed_step["distance_to_target"] = distance_to_target
        return [changed_step]

    @staticmethod
    def rebuild_vehicle_path_from_gps(vehicle, city_map, lon, lat, current_timestamp=None):
        """根据车辆 GPS 坐标和当前任务状态重新计算后续路网轨迹。

        Args:
            vehicle (Vehicle): 需要更新位置和路径的车辆。
            city_map (CityGraph): 路网对象。
            lon (float): 车辆 GPS 经度。
            lat (float): 车辆 GPS 纬度。
            current_timestamp (float | None): 真实业务时间戳；为空时使用当前系统时间。

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
        changed_steps = CoreDispatcher._sync_nearby_route_target(
            vehicle,
            lon,
            lat,
            current_timestamp=current_timestamp,
        )

        # 以吸附后的下一节点为起点重建剩余轨迹；真实 GPS 会作为虚拟起点补回结果首位。
        result = CoreDispatcher.refresh_vehicle_route_metadata(
            vehicle,
            city_map,
            next_node,
            submit_grasp=False,
        )
        if result is None:
            return None

        vehicle.gps = {"lon": lon, "lat": lat}
        vehicle.last_node = projection["edge_u"]
        vehicle.next_node = projection["edge_v"]
        vehicle.progress = projection["progress"]

        projection_point = CoreDispatcher._projection_to_path_point(projection)
        result["path"] = [projection_point] + result["path"]
        if result.get("segments"):
            first_segment = result["segments"][0]
            first_path = first_segment.get("path") or []
            first_segment["path"] = [projection_point] + first_path
            first_segment["startNodeId"] = projection_point["id"]
        result["planned_route_point"] = result["path"]
        vehicle.planned_route_point = result["planned_route_point"]
        if changed_steps or not getattr(vehicle, "planned_route_segment_grasped_point", None):
            # 上下客会改变后续 O/D 队列；没有既有纠偏路线时也需要发起一次高德纠偏。
            CoreDispatcher._mark_vehicle_route_grasp_pending(vehicle, result)
        else:
            # 普通 GPS 前进只裁剪既有纠偏路线，不重新请求高德。
            CoreDispatcher._trim_vehicle_grasped_route_from_result(
                vehicle,
                result,
                start_point={"lon": lon, "lat": lat, "id": "vehicle_gps"},
            )

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
        persistence.record_path_update(
            vehicle,
            result,
            report_time=current_timestamp if current_timestamp is not None else time.time(),
        )
        return result

    # ============================================================
    # 功能九：高德分段 ETA 后台刷新算法
    # 相关方法：refresh_order_etas_if_due、_build_vehicle_eta_job、_apply_order_eta
    # ============================================================

    @classmethod
    def _get_eta_service(cls):
        """懒加载并复用高德轨迹纠偏 ETA 客户端。

        说明:
            API Key 优先从环境变量 AMAP_API_KEY 读取；未配置时沿用当前项目默认 Key。
            缺失或禁用时，ETA 模块会返回 disabled 状态，不影响派单、路径更新或订单状态推进。
        """
        api_key = os.getenv("AMAP_API_KEY") or cls.DEFAULT_AMAP_API_KEY
        if cls.eta_service is None or cls.eta_service_api_key != api_key:
            cls.eta_service = AmapEtaCorrectClient(api_key=api_key)
            cls.eta_service_api_key = api_key
        return cls.eta_service

    @staticmethod
    def _collect_route_grasp_jobs(fleet):
        """采集待高德纠偏的车辆路线快照。

        Args:
            fleet (list[Vehicle] | None): 当前车队。

        Returns:
            list[dict]: 可同步执行的纠偏任务列表。

        Side Effects:
            对版本已过期的车辆，可能把其纠偏状态置为 stale。
        """
        jobs = []
        for vehicle in fleet or []:
            job = CoreDispatcher._route_grasp_job_from_vehicle(vehicle)
            if job:
                jobs.append(job)
        return jobs

    @staticmethod
    def _grasp_route_segment(client, segment):
        """对单个路线分段做高德纠偏。

        Args:
            client (AmapEtaCorrectClient): 高德纠偏/驾车规划客户端。
            segment (dict): 单个 O、D 或 IDLE 原始路线分段。

        Returns:
            dict: 形如 {"ok": bool, "segment": dict, "reason": str | None} 的分段纠偏结果。

        Notes:
            优先使用高德轨迹纠偏；如果失败，再降级使用高德驾车规划 polyline。
        """
        points = copy.deepcopy(segment.get("points") or [])
        if len(points) < 2:
            return {
                "ok": False,
                "reason": "too_few_points",
                "segment": segment,
            }

        if not getattr(client, "enabled", True):
            return {
                "ok": False,
                "reason": "disabled",
                "segment": segment,
            }

        # 第一优先级：使用高德轨迹纠偏接口把 A* 折线吸附到真实道路形态。
        grasp = client.grasp_driving_sync(points, SPEED_MPS)
        if isinstance(grasp, dict) and grasp.get("ok") and len(grasp.get("points") or []) >= 2:
            grasped = copy.deepcopy(segment)
            grasped["points"] = copy.deepcopy(grasp["points"])
            grasped["source"] = "grasproad"
            grasped["grasp"] = {
                "ok": True,
                "distance_m": grasp.get("distance_m"),
                "request_points": grasp.get("request_points"),
                "error": None,
            }
            return {"ok": True, "segment": grasped}

        # 降级路径：轨迹纠偏失败时，尝试用高德驾车规划返回的 polyline 作为展示路线。
        driving = client.driving_eta_sync(points) if hasattr(client, "driving_eta_sync") else {}
        if isinstance(driving, dict) and driving.get("ok") and len(driving.get("polyline") or []) >= 2:
            grasped = copy.deepcopy(segment)
            grasped["points"] = copy.deepcopy(driving["polyline"])
            grasped["source"] = "driving_polyline"
            grasped["grasp"] = {
                "ok": False,
                "distance_m": grasp.get("distance_m") if isinstance(grasp, dict) else None,
                "request_points": grasp.get("request_points") if isinstance(grasp, dict) else None,
                "error": (
                    grasp.get("error")
                    or grasp.get("reason")
                    or grasp.get("errmsg")
                    if isinstance(grasp, dict)
                    else "grasp_failed"
                ),
            }
            return {"ok": True, "segment": grasped}

        reason = "grasp_failed"
        if isinstance(driving, dict):
            reason = driving.get("error") or driving.get("reason") or driving.get("info") or reason
        elif isinstance(grasp, dict):
            reason = grasp.get("error") or grasp.get("reason") or grasp.get("errmsg") or reason
        return {"ok": False, "reason": reason, "segment": segment}

    @staticmethod
    def _run_route_grasp_job(client, job):
        """锁外执行单车路线纠偏任务。

        Args:
            client (AmapEtaCorrectClient): 高德纠偏/驾车规划客户端。
            job (dict): _route_grasp_job_from_vehicle 构造出的任务快照。

        Returns:
            dict: 单车纠偏结果；成功时包含分段纠偏路线和拼接后的完整路线。
        """
        if not getattr(client, "enabled", True):
            return {
                "ok": False,
                "status": "disabled",
                "reason": "missing_api_key",
                "segments": [],
            }

        grasped_segments = []
        errors = []
        for segment in job["segments"]:
            try:
                # 单个分段失败不立即抛出，统一收集错误并返回给车辆状态。
                result = CoreDispatcher._grasp_route_segment(client, segment)
            except Exception as exc:
                result = {"ok": False, "reason": str(exc), "segment": segment}
            if result.get("ok"):
                grasped_segments.append(result["segment"])
            else:
                errors.append(f"{segment.get('type')}:{segment.get('request_id')}:{result.get('reason')}")

        if errors:
            return {
                "ok": False,
                "status": "error",
                "reason": "; ".join(errors),
                "segments": [],
            }
        return {
            "ok": True,
            "status": "ready",
            "segments": grasped_segments,
            "path": CoreDispatcher._combine_grasped_segments(grasped_segments),
        }

    @staticmethod
    def _apply_route_grasp_result(job, result, fleet):
        """在车队中定位目标车辆，并应用纠偏结果。

        Args:
            job (dict): 原纠偏任务快照。
            result (dict): _run_route_grasp_job 返回的纠偏结果。
            fleet (list[Vehicle] | None): 当前车队。

        Returns:
            int: 成功写回或写入错误状态返回 1；车辆不存在或版本不匹配返回 0。
        """
        target_vehicle = None
        for vehicle in fleet or []:
            if str(vehicle.id) == job["vehicle_id"]:
                target_vehicle = vehicle
                break
        if target_vehicle is None:
            return 0
        return CoreDispatcher._apply_route_grasp_result_to_vehicle(target_vehicle, job, result)

    @staticmethod
    def _apply_route_grasp_result_to_vehicle(target_vehicle, job, result):
        """校验版本并把单车纠偏结果写回车辆对象。

        Args:
            target_vehicle (Vehicle): 纠偏任务对应的车辆对象。
            job (dict): 原纠偏任务快照。
            result (dict): _run_route_grasp_job 返回的纠偏结果。

        Returns:
            int: 成功写回或写入错误状态返回 1；版本不匹配返回 0。

        Side Effects:
            更新车辆的已纠偏分段、已纠偏总路线、纠偏状态和错误信息。
        """
        if target_vehicle is None:
            return 0
        if str(target_vehicle.id) != job["vehicle_id"]:
            return 0
        # 写回前再次校验车辆当前路线版本，避免异步返回的旧结果覆盖新路线。
        if CoreDispatcher._vehicle_grasp_route_version(target_vehicle) != job["route_version"]:
            return 0
        if getattr(target_vehicle, "planned_route_grasp_route_version", None) != job["route_version"]:
            return 0

        if isinstance(result, dict) and result.get("ok"):
            # 成功结果同时保留分段路线和拼接总路线，分别服务 ETA 和前端展示。
            segments = copy.deepcopy(result.get("segments") or [])
            raw_segments = getattr(target_vehicle, "planned_route_segment_raw_point", None) or []
            if raw_segments:
                # 高德请求期间车辆可能继续前进；写回前按最新 GPS 起点裁剪，避免路线重新变长。
                gps = getattr(target_vehicle, "gps", {}) or {}
                start_point = None
                if gps.get("lon") is not None and gps.get("lat") is not None:
                    start_point = {"lon": gps["lon"], "lat": gps["lat"], "id": "vehicle_gps"}
                segments = CoreDispatcher._trim_grasped_segments_to_position(
                    segments,
                    raw_segments,
                    start_point=start_point,
                )
            target_vehicle.planned_route_segment_grasped_point = segments
            target_vehicle.planned_route_grasped_point = CoreDispatcher._combine_grasped_segments(segments)
            target_vehicle.planned_route_grasp_status = "ready"
            target_vehicle.planned_route_grasp_error = None
            persistence.record_route_grasp(target_vehicle)
            return 1

        status = result.get("status", "error") if isinstance(result, dict) else "error"
        reason = result.get("reason", status) if isinstance(result, dict) else status
        target_vehicle.planned_route_grasp_status = status
        target_vehicle.planned_route_grasp_error = reason
        persistence.record_route_grasp(target_vehicle)
        return 1

    @classmethod
    def _execute_vehicle_route_grasp_job(cls, vehicle, job, job_key):
        """在线程池中执行一次车辆路线纠偏，并在锁内写回结果。

        Args:
            vehicle (Vehicle): 提交任务时对应的车辆对象。
            job (dict): 原纠偏任务快照。
            job_key (tuple): 用于去重和清理在途任务的 (vehicle_id, route_version)。

        Side Effects:
            锁外请求高德；锁内校验版本并写回车辆纠偏状态。
        """
        try:
            try:
                client = cls._get_eta_service()
                result = cls._run_route_grasp_job(client, job)
            except Exception as exc:
                result = {
                    "ok": False,
                    "status": "error",
                    "reason": str(exc),
                    "segments": [],
                }
            lock_context = cls.route_grasp_apply_lock if cls.route_grasp_apply_lock is not None else nullcontext()
            with lock_context:
                # 写回阶段很短，只做版本校验和对象赋值，避免长时间占用全局状态锁。
                cls._apply_route_grasp_result_to_vehicle(vehicle, job, result)
        finally:
            with cls.route_grasp_inflight_lock:
                # 无论请求成功、失败还是写回被丢弃，都必须释放在途标记。
                cls.route_grasp_inflight.discard(job_key)

    @classmethod
    def refresh_route_grasps_if_due(
        cls,
        fleet,
        state_lock=None,
        *,
        current_timestamp=None,
        force=False,
        service=None,
    ):
        """手动刷新待纠偏车辆路线结果。

        Args:
            fleet (list[Vehicle] | None): 当前车队。
            state_lock (RLock | None): 读取和写回车辆状态时使用的锁。
            current_timestamp (float | None): 本次手动刷新时间戳；为空时取当前系统时间。
            force (bool): 是否忽略 5 秒节流限制。
            service (object | None): 测试用高德纠偏服务桩；为空时使用默认高德客户端。

        Returns:
            int: 本次成功写回或写入错误状态的车辆数量。

        Notes:
            运行时主链路已改为“路径更新即异步提交纠偏”；该函数保留给测试和人工排障使用。
        """
        current_timestamp = float(current_timestamp if current_timestamp is not None else time.time())
        lock_context = state_lock if state_lock is not None else nullcontext()

        with lock_context:
            if fleet is None:
                return 0
            if (
                not force
                and cls.route_grasp_last_refresh_timestamp is not None
                and current_timestamp - cls.route_grasp_last_refresh_timestamp < cls.ROUTE_GRASP_REFRESH_INTERVAL_SECONDS
            ):
                return 0
            cls.route_grasp_last_refresh_timestamp = current_timestamp
            # 持锁阶段只复制待纠偏任务快照，不在锁内请求高德。
            jobs = cls._collect_route_grasp_jobs(fleet)

        if not jobs:
            return 0

        client = service or cls._get_eta_service()
        results = []
        for job in jobs:
            # 网络请求锁外执行，避免阻塞派单、GPS 更新和状态查询。
            results.append((job, cls._run_route_grasp_job(client, job)))

        changed = 0
        with lock_context:
            for job, result in results:
                # 写回时再次校验 route_version，路线已变化的旧结果会被丢弃。
                changed += cls._apply_route_grasp_result(job, result, fleet)
        return changed

    @staticmethod
    def _node_to_eta_point(node):
        """将路网节点转成高德 ETA 模块可读取的点结构。"""
        return {
            "id": node.id,
            "lon": node.lon,
            "lat": node.lat,
            "name": getattr(node, "name", ""),
            "zone": getattr(node, "zone", None),
        }

    @staticmethod
    def _vehicle_position_for_eta(vehicle, city_map):
        """优先使用车辆最新 GPS；没有 GPS 时退回到 next_node/last_node 坐标。"""
        gps = getattr(vehicle, "gps", {}) or {}
        lon = gps.get("lon")
        lat = gps.get("lat")
        if lon is not None and lat is not None:
            return {"lon": float(lon), "lat": float(lat)}

        node = city_map.nodes_map.get(getattr(vehicle, "next_node", None))
        if node is None:
            node = city_map.nodes_map.get(getattr(vehicle, "last_node", None))
        if node is None:
            return None
        return CoreDispatcher._node_to_eta_point(node)

    @staticmethod
    def _vehicle_eta_route_version(vehicle):
        """生成路线版本签名；路线或车辆所在边变化时丢弃旧 ETA 结果。"""
        parts = [
            str(vehicle.id),
            str(getattr(vehicle, "next_node", "")),
            f"{float(getattr(vehicle, 'progress', 0.0) or 0.0):.6f}",
        ]
        for step in getattr(vehicle, "planned_route", []):
            order = step.get("order")
            request_id = getattr(order, "request_id", "")
            parts.append(f"{step.get('type')}:{request_id}")
        return "|".join(parts)

    @staticmethod
    def _build_vehicle_eta_job(vehicle, city_map, current_timestamp):
        """构造单车 ETA 刷新任务快照。

        算法说明:
            ETA 只读取后台纠偏线程已经写回的分段轨迹，不在这里重新请求纠偏。
        """
        if getattr(vehicle, "planned_route_grasp_status", None) != "ready":
            return None
        route_version = CoreDispatcher._vehicle_grasp_route_version(vehicle)
        if getattr(vehicle, "planned_route_grasp_route_version", None) != route_version:
            return None

        grasped_segments = getattr(vehicle, "planned_route_segment_grasped_point", None) or []
        segments = []
        for index, segment in enumerate(grasped_segments):
            step_type = segment.get("type")
            request_id = segment.get("request_id")
            if step_type not in {"O", "D", "IDLE"}:
                continue

            points = segment.get("points") or segment.get("path") or []
            if not points:
                continue

            start_node_id = points[0].get("id") if isinstance(points[0], dict) else None
            end_node_id = points[-1].get("id") if isinstance(points[-1], dict) else None
            segments.append({
                "index": index,
                "startNodeId": start_node_id,
                "endNodeId": end_node_id,
                "endStep": {
                    "type": step_type,
                    "orderId": str(request_id) if request_id is not None else None,
                },
                "points": points,
                "aStarDistanceM": segment.get("aStarDistanceM", segment.get("distance")),
            })
        if not segments:
            return None

        position = CoreDispatcher._vehicle_position_for_eta(vehicle, city_map)
        if position is None:
            return None

        order_ids = []

        def add_order_id(order):
            order_id = str(order.request_id)
            if order_id not in order_ids:
                order_ids.append(order_id)

        if getattr(vehicle, "planned_route", None):
            for order in vehicle.on_board_orders:
                add_order_id(order)
            for step in vehicle.planned_route:
                add_order_id(step["order"])
        is_idle = not getattr(vehicle, "planned_route", None) and bool(getattr(vehicle, "idle_target", None))
        if not order_ids and not is_idle:
            return None

        return {
            "vehicle_id": str(vehicle.id),
            "route_version": route_version,
            "order_ids": order_ids,
            "is_idle": is_idle,
            "payload": {
                "vehicleId": str(vehicle.id),
                "routeVersion": route_version,
                "speedMps": SPEED_MPS,
                "vehiclePosition": position,
                "segments": segments,
            },
            "collected_at": current_timestamp,
        }

    @staticmethod
    def _eta_seconds(eta):
        """安全读取 ETA 秒数。"""
        if isinstance(eta, dict):
            value = eta.get("eta_seconds")
        else:
            value = eta
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _combined_order_eta_status(order_eta, amap_enabled=True, is_on_board=False):
        """把新 ETA pipeline 的单订单结果压缩成展示状态。"""
        if not amap_enabled:
            return "disabled"
        if not isinstance(order_eta, dict):
            return "not_available"

        pickup_seconds = CoreDispatcher._eta_seconds(order_eta.get("pickupEtaSec"))
        dropoff_seconds = CoreDispatcher._eta_seconds(order_eta.get("dropoffEtaSec"))
        if is_on_board:
            return "ready" if dropoff_seconds is not None else "not_available"
        if pickup_seconds is not None and dropoff_seconds is not None:
            return "ready"
        if pickup_seconds is not None or dropoff_seconds is not None:
            return "partial"
        return "not_available"

    @staticmethod
    def _mark_order_eta_error(order, status, message, updated_at):
        """记录 ETA 刷新失败状态，但不清空上一次有效 ETA。"""
        order.eta_updated_at = updated_at
        order.eta_status = status
        order.eta_error = message

    @staticmethod
    def _apply_order_eta(order, order_eta, updated_at, is_on_board, amap_enabled=True):
        """把新 ETA pipeline 的单订单结果写回 Order 对象。

        时间规则:
            ETA 使用后台线程传入的真实业务时间 updated_at，不再依赖车辆仿真时间。
            waiting 订单写入当前车辆到 O 点和 D 点的累计 ETA；riding 订单保留实际上车
            时间，只刷新目的地送达时间。
        """
        status = CoreDispatcher._combined_order_eta_status(order_eta, amap_enabled, is_on_board)
        order.eta_updated_at = updated_at
        order.eta_status = status
        order.eta_error = None if status in {"ready", "partial"} else status

        pickup_seconds = (
            CoreDispatcher._eta_seconds(order_eta.get("pickupEtaSec"))
            if isinstance(order_eta, dict)
            else None
        )
        dropoff_seconds = (
            CoreDispatcher._eta_seconds(order_eta.get("dropoffEtaSec"))
            if isinstance(order_eta, dict)
            else None
        )

        if is_on_board:
            if order.actual_pick_time is not None:
                order.estimated_arrival_time = float(order.actual_pick_time)
                order.estimated_arrival_eta_seconds = 0
            if dropoff_seconds is not None:
                order.estimated_dropoff_eta_seconds = dropoff_seconds
                order.estimated_dropoff_time = updated_at + dropoff_seconds
            return

        if pickup_seconds is not None:
            order.estimated_arrival_eta_seconds = pickup_seconds
            order.estimated_arrival_time = updated_at + pickup_seconds
        if dropoff_seconds is not None:
            order.estimated_dropoff_eta_seconds = dropoff_seconds
            order.estimated_dropoff_time = updated_at + dropoff_seconds

    @staticmethod
    def _current_vehicle_orders(vehicle):
        """读取车辆当前任务中的订单对象，按 request_id 去重。"""
        orders = {}
        for order in vehicle.on_board_orders:
            orders[str(order.request_id)] = order
        for step in vehicle.planned_route:
            order = step["order"]
            orders[str(order.request_id)] = order
        return orders

    @staticmethod
    def _order_status_for_persistence(order):
        """读取订单当前可落库状态；对象未显式设置时根据关键时间推断。"""
        status = getattr(order, "status", None)
        if status:
            return status
        if getattr(order, "completion_time", None) is not None:
            return "completed"
        if getattr(order, "actual_pick_time", None) is not None:
            return "riding"
        return "matched"

    @staticmethod
    def _apply_vehicle_eta_result(job, result, updated_at, fleet):
        """校验路线版本并把单车 ETA 结果写回订单。"""
        target_vehicle = None
        for vehicle in fleet or []:
            if str(vehicle.id) == job["vehicle_id"]:
                target_vehicle = vehicle
                break
        if target_vehicle is None:
            return 0
        if CoreDispatcher._vehicle_grasp_route_version(target_vehicle) != job["route_version"]:
            return 0
        if job.get("is_idle"):
            if not isinstance(result, dict) or not result.get("ok", False):
                reason = (result or {}).get("reason", "eta_error") if isinstance(result, dict) else "eta_error"
                target_vehicle.idle_target_eta_status = reason
                target_vehicle.idle_target_eta_error = reason
                persistence.record_eta_result(target_vehicle)
                return 1

            amap_enabled = bool(result.get("amapEnabled", result.get("enabled", True)))
            idle_eta = CoreDispatcher._eta_seconds(result.get("idleEtaSec"))
            if not amap_enabled:
                target_vehicle.idle_target_eta_status = "disabled"
                target_vehicle.idle_target_eta_error = "disabled"
            elif idle_eta is None:
                target_vehicle.idle_target_eta_status = "not_available"
                target_vehicle.idle_target_eta_error = "missing_idle_eta"
            else:
                target_vehicle.idle_target_eta_seconds = idle_eta
                target_vehicle.idle_target_eta_time = updated_at + idle_eta
                target_vehicle.idle_target_eta_status = "ready"
                target_vehicle.idle_target_eta_error = None
            persistence.record_eta_result(target_vehicle)
            return 1

        current_orders = CoreDispatcher._current_vehicle_orders(target_vehicle)
        on_board_ids = {str(order.request_id) for order in target_vehicle.on_board_orders}

        changed = 0
        if not isinstance(result, dict) or not result.get("ok", False):
            reason = (result or {}).get("reason", "eta_error") if isinstance(result, dict) else "eta_error"
            message = (result or {}).get("message", reason) if isinstance(result, dict) else reason
            for order_id in job["order_ids"]:
                order = current_orders.get(str(order_id))
                if order is not None:
                    CoreDispatcher._mark_order_eta_error(order, reason, message, updated_at)
                    persistence.record_order_snapshot(order, status=CoreDispatcher._order_status_for_persistence(order), vehicle=target_vehicle)
                    changed += 1
            return changed

        amap_enabled = bool(result.get("amapEnabled", result.get("enabled", True)))
        passenger_etas = result.get("passengerEtas", [])
        if not isinstance(passenger_etas, list):
            passenger_etas = []
        by_order_id = {}
        for order_eta in passenger_etas:
            if not isinstance(order_eta, dict):
                continue
            order_id = order_eta.get("orderId", order_eta.get("order_id"))
            if order_id is not None:
                by_order_id[str(order_id)] = order_eta

        for order_id in job["order_ids"]:
            order = current_orders.get(str(order_id))
            if order is None:
                continue
            order_eta = by_order_id.get(str(order_id))
            if order_eta is None:
                status = "disabled" if not amap_enabled else "not_available"
                CoreDispatcher._mark_order_eta_error(order, status, "missing_order_eta", updated_at)
            else:
                CoreDispatcher._apply_order_eta(
                    order,
                    order_eta,
                    updated_at,
                    str(order_id) in on_board_ids,
                    amap_enabled,
                )
            persistence.record_order_snapshot(
                order,
                status=CoreDispatcher._order_status_for_persistence(order),
                vehicle=target_vehicle,
            )
            changed += 1
        persistence.record_vehicle_runtime(target_vehicle)
        return changed

    @staticmethod
    def _collect_eta_refresh_jobs(fleet, city_map, current_timestamp):
        """采集当前车队 ETA 刷新任务快照。"""
        if city_map is None or fleet is None:
            return []

        jobs = []
        for vehicle in fleet:
            job = CoreDispatcher._build_vehicle_eta_job(vehicle, city_map, current_timestamp)
            if job is not None:
                jobs.append(job)
        return jobs

    @classmethod
    def refresh_order_etas_if_due(
        cls,
        fleet,
        city_map,
        state_lock=None,
        *,
        current_timestamp=None,
        force=False,
        service=None,
    ):
        """按 5 秒节流刷新订单 ETA。

        并发约束:
            1. 持锁阶段只采集车辆/订单/路线快照。
            2. 高德网络请求在锁外执行，避免阻塞派单和路径更新。
            3. 写回时再次持锁并校验 route_version，路线变更则丢弃旧结果。
        """
        current_timestamp = float(current_timestamp if current_timestamp is not None else time.time())
        lock_context = state_lock if state_lock is not None else nullcontext()

        with lock_context:
            if city_map is None or fleet is None:
                return 0
            if (
                not force
                and cls.eta_last_refresh_timestamp is not None
                and current_timestamp - cls.eta_last_refresh_timestamp < cls.ETA_REFRESH_INTERVAL_SECONDS
            ):
                return 0
            cls.eta_last_refresh_timestamp = current_timestamp
            jobs = cls._collect_eta_refresh_jobs(fleet, city_map, current_timestamp)

        if not jobs:
            return 0

        eta_client = service or cls._get_eta_service()
        results = []
        for job in jobs:
            try:
                if hasattr(eta_client, "build_eta_pipeline_from_astar"):
                    result = eta_client.build_eta_pipeline_from_astar(job["payload"], now=current_timestamp)
                else:
                    result = build_eta_pipeline_from_astar(job["payload"], amap=eta_client)
            except Exception as exc:
                result = {
                    "ok": False,
                    "amapEnabled": True,
                    "reason": "eta_error",
                    "message": str(exc),
                    "passengerEtas": [],
                }
            results.append((job, result))

        changed = 0
        with lock_context:
            for job, result in results:
                updated_at = float(
                    result.get("builtAtEpoch", current_timestamp)
                    if isinstance(result, dict)
                    else current_timestamp
                )
                changed += cls._apply_vehicle_eta_result(job, result, updated_at, fleet)
        return changed

    # ============================================================
    # 功能十：空车停靠场景入口
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
    # 功能十一：停止接单预测预留入口
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
