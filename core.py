# core.py
"""打车系统的大脑业务算子主控层。
负责派单、重组架构、以及闲置管控等绝对智能内核逻辑。
"""

import time
from models import SPEED_MPS

class CoreDispatcher:
    """提供拼单博弈算力与核心派车路线演算的中枢处理台。"""
    
    # 核心订单池：用于缓存由于运力爆满、或严重绕路(不顺路)而未能及时指派的订单。
    order_pool = []
    
    # [新增] 存放已完成、已结束（或已取消）订单的归档池，内部存储 Order 对象
    completed_orders_pool = []

    @staticmethod
    def evaluate_route(route, vehicle_state, on_board_orders, city_map, capacity=10, v_zone=None):
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
            
        Returns:
            tuple: (可不可行分支True/False, 最终累计积分成本 float)。成本分越低代表更偏向于选择此行程。
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
                return False, float('inf')
                
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
                    return False, float('inf') 
                pickup_times[order.id] = sim_time
            elif step['type'] == 'D':
                current_load -= 1
                if current_load < 0:
                    return False, float('inf')
                arrival_times[order.id] = sim_time

        # ===== 终极综合多目标成本函数架构 (按最新四大维度重构) =====
        
        # 1. 权重定义 (严格按照需求配比)
        W_PASSENGER = 0.40  # 乘客体验 (候车时间、绕行系数、时间窗满意度)
        W_ENTERPRISE = 0.30 # 企业效益 (满载率、单车收入、里程利用率)
        W_SOCIAL = 0.20     # 社会效益 (区域覆盖率、碳排放、道路资源占用)
        W_FAIRNESS = 0.10   # 平台公平 (企业间订单分配基尼系数)

        # 保留原有的核心调优参数
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
                passenger_cost += wait_time * BETA # 候车枯等惩罚
                
                # 时间窗满意度：超出极限接客时间直接否决
                if pickup_times[order.id] > order.max_pickup_time:
                    return False, OMEGA
            else:
                start_service_time = pickup_times.get(order.id) or order.actual_pick_time or vehicle_state['time']
                in_car_time = arrival_times[order.id] - start_service_time
                passenger_cost += in_car_time * GAMMA # 车内绕行惩罚
                
                # 时间窗满意度：超出极限送达时间直接否决
                if arrival_times[order.id] > order.max_arrival_time:
                    return False, OMEGA
            
        # 乘客体验：强制挂载老乘客被绕路的代价
        for order in on_board_orders:
            for step in route:
                if step['type'] == 'D' and step['order'].id == order.id:
                    extra_in_car_time = arrival_times[order.id] - vehicle_state['time']
                    passenger_cost += extra_in_car_time * GAMMA
                    if extra_in_car_time > 180.0:
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

        # ---------------------------------------------------------
        # 维度 C: 社会效益成本 (Social Cost)
        # 总体路权占用、碳排放总长以及跨区调度的惩罚
        total_dist = empty_dist + loaded_dist
        social_cost = total_dist * 1.0 + cross_zone_penalty

        # ---------------------------------------------------------
        # 维度 D: 平台公平成本 (Fairness Cost) 
        # 代理基尼系数：当前车辆负载越大、车上已有订单越多，成本增加。
        # 目的是让派单系统更倾向于把新单分派给比较闲的车队/车辆，促进均衡分配。
        fairness_cost = len(on_board_orders) * 500.0 

        # ---------------------------------------------------------
        # 最终归一化加权求和 Cost
        cost = (W_PASSENGER * passenger_cost + 
                W_ENTERPRISE * enterprise_cost + 
                W_SOCIAL * social_cost + 
                W_FAIRNESS * fairness_cost)
        
        return True, cost

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
        
        for i in range(n + 1):
            temp_route = route[:i] + [p_step] + route[i:]
            for j in range(i + 1, n + 2):
                test_route = temp_route[:j] + [d_step] + temp_route[j:]
                
                is_feasible, cost = CoreDispatcher.evaluate_route(test_route, v_state, vehicle.on_board_orders, city_map, vehicle.capacity, v_zone=vehicle.op_zone)
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
                        is_feasible, cost = CoreDispatcher.evaluate_route(mut_route, v_state, vehicle.on_board_orders, city_map, vehicle.capacity, v_zone=vehicle.op_zone)
                        
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
        print(f"[Core.Dispatcher] 新订单 [单{order.id}] 注入系统统筹池，进入【后悔值扫描】序列等待...")
        CoreDispatcher.order_pool.append(order)
        return False

    @staticmethod
    def process_pool_matching(fleet, city_map):
        """【订单池实时匹配引擎】：核心升级为主流【后悔值插入法(Regret-Based)】。
        
        该函数现在会以 5 秒为周期持续运行，实时监控订单池并进行统筹派发。
        """
        print("[Core.Pool] 订单池匹配引擎已启动，每 5 秒进行一轮后悔值统筹调度...")
        
        while True:
            if not CoreDispatcher.order_pool:
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
                    global_best_v.planned_route = global_best_route
                    assign_count += 1
                    print(f"[Core.Pool] [Match] 后悔值出警：痛点单 {target_o.id} 被 {global_best_v.id} 优先划拨！")
                    
                    # ==========================================
                    # [新增] 打印车辆更新后的轨迹点 (途径站点) 
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
                    print(f"    [明细] 该路线底层共包含 {full_path_node_count} 个路网轨迹点(用于前端高亮连线)")
                    print(f"    [明细] 该路线总里程: {total_path} ")
                else:
                    # 池中剩余订单当前均无法匹配
                    break
                    
            if assign_count > 0:
                print(f"[Core.Pool] 本轮调度完毕：成功释放 {assign_count} 个积压订单。")
            
            # 等待 5 秒进行下一轮匹配
            time.sleep(5)

    @staticmethod
    def idle_parking_scenario(vehicle, city_map):
        """【车辆空单停靠场景】：由于由于车辆空虚或无任务，引导其向热力源滑行的索敌调度。
        
        Args:
            vehicle (Vehicle): 处于闲置待命状态的车辆对象。
            city_map (CityGraph): 引导参考的网格密度路网实例。
            
        Returns:
            bool: 是否成功执行索敌指令下发。
        """
        print(f"[Core.Planner] {vehicle.id} 由于深层待命陷入无主，触发引擎激活 【高热空单停靠索敌规矩】...")
        # 预留待办算法：算出近点高热度蜂窝将车赶过去
        return True

    @staticmethod
    def stop_order_prediction(vehicle):
        """【停止接单预测场景】：根据车辆健康度、疲劳度或电量衰退进行的干预算法。
        
        Args:
            vehicle (Vehicle): 需要进行健康扫描的车辆。
            
        Returns:
            bool: 是否下达强制切断接单信令。
        """
        print(f"[Core.WindControl] 对 {vehicle.id} 下发了疲劳驾驶、晚高峰以及掉电预期寿命扫描...")
        # 预留待办算法：截断车队被推演插入池
        return False
