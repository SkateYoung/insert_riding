# core.py
"""打车系统的大脑业务算子主控层。
负责派单、重组架构、以及闲置管控等绝对智能内核逻辑。
"""

from models import SPEED_MPS

class CoreDispatcher:
    """提供拼单博弈算力与核心派车路线演算的中枢处理台。"""
    
    # 核心订单池：用于缓存由于运力爆满、或严重绕路(不顺路)而未能及时指派的订单。
    order_pool = []

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
            capacity (int, optional): 车辆容量红线。当超载越界时会被直接弹射作废。
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

        # ===== 终极综合多目标成本函数架构 =====
        ALPHA_1 = 2.0    # 空驶里程倍率惩罚 (同步调优：抑制跨城指派)
        ALPHA_2 = 0.5    # 载客有效里程基准 (同步调优：降低绕路敏感度)
        BETA = 4.0       # 站牌下乘客枯等耗时体验折损 (同步调优：显著提升就近优先级)
        GAMMA = 3.0      # 车内乘客被拉着绕路耗时体验折损 (同步调优：鼓励高效并单)
        OMEGA = float('inf') # SLA 红线超额一票否决
        THETA = 1500.0   # 终点强引力防背叛护盾 (对老乘客绕路的极重处罚)
        
        cost = ALPHA_1 * empty_dist + ALPHA_2 * loaded_dist + cross_zone_penalty
        
        for step in route:
            order = step['order']
            if step['type'] == 'P':
                wait_time = pickup_times[order.id] - order.req_time
                cost += BETA * wait_time
                
                # ------ 同步 JS SLA 时间窗拦截 ------
                if pickup_times[order.id] > order.max_pickup_time:
                    return False, OMEGA
            else:
                # 核心修正：如果是已在车上的订单，由于缺失 P 点推演逻辑，其 pickup_times[order.id] 为空。
                # 此处尝试引入 actual_pick_time，若未接到（或处于极端起步状态）则回退到车辆当前时间戳。
                start_service_time = pickup_times.get(order.id) or order.actual_pick_time or vehicle_state['time']
                in_car_time = arrival_times[order.id] - start_service_time
                cost += GAMMA * in_car_time
                
                # ------ 同步 JS SLA 时间窗拦截 ------
                if arrival_times[order.id] > order.max_arrival_time:
                    return False, OMEGA
            
        # ====== 乘客坐牢厚度强制挂载 (老乘客绕路代价) ======
        for order in on_board_orders:
            # 这些乘客已经在车上，计算他们到达各自目的地的时间
            # 找到对应的下客步骤
            for step in route:
                if step['type'] == 'D' and step['order'].id == order.id:
                    extra_in_car_time = arrival_times[order.id] - vehicle_state['time']
                    cost += GAMMA * extra_in_car_time
                    
                    # 强制护盾：使得任何延宕老客越界三分钟的行为遭遇极大的数学阻力
                    if extra_in_car_time > 180.0:
                        cost += THETA
                    break
        
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
                    
        # ====== [新增] 2-Opt 突变反转寻优阶段：同步 JS 逻辑，尝试打破已锁定的旧客排序跨空间重构 TSP 路线 ======
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
            fleet (list): 车队（废弃保留接口签名统一）。
            order (Order): 需要被派发的单例客源订单数据。
            city_map (CityGraph): 地图数据（废弃保留签名）。
            
        Returns:
            bool: 永远返回 False 表示进入池化，切断即时指派避免出现极度绕路。
        """
        print(f"[Core.Dispatcher] 新订单 [单{order.id}] 注入系统统筹池，进入【后悔值扫描】序列等待...")
        CoreDispatcher.order_pool.append(order)
        return False

    @staticmethod
    def process_pool_matching(fleet, city_map):
        """【订单池实时匹配引擎】：核心升级为主流【后悔值插入法(Regret-Based)】。
        
        积累一小批订单通过评估机会成本统一派发，强制约束交规、疲劳，并寻找出“最经不起后悔打击”的痛点订单予以解救。
        
        Args:
            fleet (list): 可调配的 Vehicle 舰队集合。
            city_map (CityGraph): 路网地图实例。
        """
        if not CoreDispatcher.order_pool:
            return
            
        print(f"[Core.Pool] 正在对池中 {len(CoreDispatcher.order_pool)} 个订单执行后悔值统筹调度...")
        
        assign_count = 0
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
                print(f"[Core.Pool] 🏆 【后悔值出警】痛点单 {target_o.id} 被 {global_best_v.id} 优先划拨！")
            else:
                break
                
        if assign_count > 0:
            print(f"[Core.Pool] 本轮沙盘扫描出警完毕：释放 {assign_count} 个积压订单。")

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
