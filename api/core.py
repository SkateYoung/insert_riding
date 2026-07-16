# core.py
"""打车系统的大脑业务算子主控层。
负责派单、重组架构、以及闲置管控等绝对智能内核逻辑。
"""

import copy
import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from datetime import datetime, timedelta
from . import persistence
from . import fleet_push
from .models import MAX_REST_DURATION_SECONDS, MIN_REST_DURATION_SECONDS, SPEED_MPS, business_timestamp
from .auxiliary import AuxiliaryFunctions
from .restrictions import restriction_signature
from forecast import od_forecast_module
from forecast.amap_driving_route_planner import AmapDrivingRoutePlanner
from forecast.amap_eta_correct import DEFAULT_AMAP_KEY, AmapEtaCorrectClient, build_eta_pipeline_from_astar

class CoreDispatcher:
    """提供拼单博弈算力与核心派车路线演算的中枢处理台。"""
    
    # 核心订单池：用于缓存由于运力爆满、或严重绕路(不顺路)而未能及时指派的订单。
    order_pool = []

    # 订单时间窗匹配参数：远期预约单默认 1 小时外暂缓，预计上车前 30 分钟释放匹配。
    ORDER_MATCH_FAR_PICKUP_THRESHOLD_SECONDS = 60 * 60
    ORDER_MATCH_FAR_PICKUP_LEAD_SECONDS = 30 * 60
    ORDER_MATCH_DISPATCH_LEAD_SECONDS = ORDER_MATCH_FAR_PICKUP_LEAD_SECONDS
    MAX_EARLY_PICKUP_WAIT_SECONDS = 3 * 60
    EARLY_PICKUP_WAIT_COST_PER_MIN = 2.0
    LATE_PICKUP_COST_PER_MIN = 8.0
    
    # [新增] 存放已完成、已结束（或已取消）订单的归档池，内部存储 Order 对象
    completed_orders_pool = []

    # 空车热点预测缓存：按运营区分桶，避免多运营区轮询时互相覆盖。
    IDLE_FORECAST_CACHE_SECONDS = 15 * 60
    IDLE_FORECAST_REFRESH_RETRY_SECONDS = 60
    IDLE_MIN_HOTSPOT_DISTANCE_METERS = 800.0

    idle_hotspot_cache = {}
    idle_hotspot_cache_lock = threading.RLock()
    idle_hotspot_refresh_executor = None
    idle_hotspot_refresh_workers = 2
    idle_hotspot_refresh_inflight = set()
    idle_hotspot_refresh_lock = threading.Lock()
    idle_hotspot_refresh_failures = {}

    # 司机端推送相关状态码
    DRIVER_PUSH_UNREACHABLE_REASON = "driver_push_unreachable"
    DRIVER_DECLINED_REASON = "driver_declined"

    #司机端因为网络信号原因未及时接到订单的对该订单匹配的冷却时间(即该订单冷却时间内无法再匹配该车辆)
    DRIVER_PUSH_UNREACHABLE_COOLDOWN_SECONDS = 3 * 60

    # 高德路线规划/ETA 后台刷新配置：ETA 仍由独立线程周期刷新，不参与派单评分。
    ETA_REFRESH_INTERVAL_SECONDS = 5.0
    ETA_REFRESH_MAX_WORKERS = 4
    ROUTE_GRASP_REFRESH_INTERVAL_SECONDS = 5.0
    eta_last_refresh_timestamp = None
    route_grasp_last_refresh_timestamp = None
    eta_service = None
    route_planner_service = None
    DEFAULT_AMAP_API_KEY = DEFAULT_AMAP_KEY
    eta_service_api_key = DEFAULT_AMAP_API_KEY
    route_planner_api_key = DEFAULT_AMAP_API_KEY
    route_grasp_auto_submit_enabled = False
    route_grasp_apply_lock = None
    route_grasp_executor = None
    route_grasp_executor_workers = 4
    route_grasp_inflight = set()
    route_grasp_inflight_lock = threading.Lock()
    operation_restriction_policies_by_area = {}
    operation_restriction_lock = threading.Lock()

    @staticmethod
    def _vehicle_identity(vehicle):
        """返回车辆业务标识，优先使用 vehicle_id。"""
        return str(getattr(vehicle, "vehicle_id", None) or getattr(vehicle, "id", ""))

    @staticmethod
    def _short_route_version(prefix, parts):
        """把路线关键字段压缩成稳定短版本号，避免数据库 route_version 超长。"""
        raw = "|".join(str(part) for part in parts)
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]
        return f"{prefix}:v1:{digest}"

    @classmethod
    def set_operation_restriction_policy(cls, policy, operation_area_id=None):
        """更新指定运营区当前生效的运营禁区策略。"""
        area_id = cls._coerce_operation_area_id(operation_area_id)
        if area_id is None and isinstance(policy, dict):
            area_id = cls._coerce_operation_area_id(policy.get("operation_area_id"))
        with cls.operation_restriction_lock:
            if area_id is None:
                if policy is None:
                    cls.operation_restriction_policies_by_area = {}
                return None
            if policy:
                snapshot = copy.deepcopy(policy)
                snapshot["operation_area_id"] = area_id
                cls.operation_restriction_policies_by_area[area_id] = snapshot
            else:
                cls.operation_restriction_policies_by_area.pop(area_id, None)
        return cls.current_operation_restriction_policy(area_id)

    @classmethod
    def set_operation_restriction_policies(cls, policies):
        """批量替换进程内按运营区生效的禁区策略。"""
        snapshots = {}
        for policy in policies or []:
            area_id = cls._coerce_operation_area_id((policy or {}).get("operation_area_id"))
            if area_id is None:
                continue
            snapshot = copy.deepcopy(policy)
            snapshot["operation_area_id"] = area_id
            snapshots[area_id] = snapshot
        with cls.operation_restriction_lock:
            cls.operation_restriction_policies_by_area = snapshots
        return copy.deepcopy(snapshots)

    @classmethod
    def current_operation_restriction_policy(cls, operation_area_id=None):
        """返回指定运营区禁区策略副本，避免调用方误改全局状态。"""
        area_id = cls._coerce_operation_area_id(operation_area_id)
        if area_id is None:
            return None
        with cls.operation_restriction_lock:
            return copy.deepcopy(cls.operation_restriction_policies_by_area.get(area_id))

    @classmethod
    def current_operation_restriction_signature(cls, operation_area_id=None):
        """返回指定运营区禁区策略签名，用于 A* 路径缓存隔离。"""
        return restriction_signature(cls.current_operation_restriction_policy(operation_area_id))

    @staticmethod
    def _vehicle_restriction_policy(vehicle):
        """返回车辆当前路线携带的禁区策略快照。"""
        return copy.deepcopy(getattr(vehicle, "operation_restriction_policy", None))

    @staticmethod
    def _get_path(city_map, start_node, end_node, restriction_policy=None):
        """在路网支持时带禁区策略调用 CityGraph.get_path。"""
        try:
            return city_map.get_path(start_node, end_node, restriction_policy=restriction_policy)
        except TypeError as exc:
            text = str(exc)
            if "restriction_policy" in text or "unexpected keyword" in text:
                return city_map.get_path(start_node, end_node)
            raise

    @staticmethod
    def _order_time_value_to_timestamp(value, default=None):
        """把订单时间字段统一转为业务时间戳。"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("/", "-"))
        if isinstance(value, datetime):
            return business_timestamp(value)
        return default

    @staticmethod
    def _order_pickup_earliest_timestamp(order):
        """返回订单最早可上车时间戳，缺失时回退到请求时间。"""
        default = float(getattr(order, "req_time", 0.0) or 0.0)
        return CoreDispatcher._order_time_value_to_timestamp(
            getattr(order, "expected_pickup_earliest", None),
            default=default,
        )

    @staticmethod
    def _order_pickup_latest_timestamp(order):
        """返回订单最晚上车时间戳，优先使用已有 max_pickup_time。"""
        default = getattr(order, "max_pickup_time", None)
        if default is not None:
            try:
                return float(default)
            except (TypeError, ValueError):
                pass
        return CoreDispatcher._order_time_value_to_timestamp(
            getattr(order, "expected_pickup_latest", None),
            default=float("inf"),
        )

    @staticmethod
    def _order_can_enter_matching_window(order, current_timestamp):
        """判断订单是否已进入可参与车辆匹配的时间窗口。

        只有期望上车时间距离当前时间超过远期阈值时才暂缓匹配；
        远期订单到达“期望上车时间 - 提前释放时间”后重新参与匹配。
        """
        earliest_ts = CoreDispatcher._order_pickup_earliest_timestamp(order)
        current_ts = float(current_timestamp)
        request_ts = float(getattr(order, "req_time", current_ts) or current_ts)
        request_to_earliest = earliest_ts - request_ts
        if request_to_earliest <= CoreDispatcher.ORDER_MATCH_FAR_PICKUP_THRESHOLD_SECONDS:
            return True
        return current_ts >= earliest_ts - CoreDispatcher.ORDER_MATCH_FAR_PICKUP_LEAD_SECONDS

    @classmethod
    def matching_window_config(cls):
        """返回订单池远期订单匹配窗口配置。"""
        return {
            "far_pickup_threshold_seconds": float(cls.ORDER_MATCH_FAR_PICKUP_THRESHOLD_SECONDS),
            "far_pickup_match_lead_seconds": float(cls.ORDER_MATCH_FAR_PICKUP_LEAD_SECONDS),
        }

    @classmethod
    def configure_matching_window(cls, far_pickup_threshold_seconds=None, far_pickup_match_lead_seconds=None):
        """运行时更新远期订单匹配窗口配置。"""
        if far_pickup_threshold_seconds is not None:
            threshold = float(far_pickup_threshold_seconds)
            if threshold < 0:
                raise ValueError("far_pickup_threshold_seconds 必须大于或等于 0")
            cls.ORDER_MATCH_FAR_PICKUP_THRESHOLD_SECONDS = threshold
        if far_pickup_match_lead_seconds is not None:
            lead = float(far_pickup_match_lead_seconds)
            if lead < 0:
                raise ValueError("far_pickup_match_lead_seconds 必须大于或等于 0")
            cls.ORDER_MATCH_FAR_PICKUP_LEAD_SECONDS = lead
            cls.ORDER_MATCH_DISPATCH_LEAD_SECONDS = lead
        return cls.matching_window_config()

    @staticmethod
    def _mark_fleet_push_pending(vehicle, event=None):
        """记录车辆路线变更后的待推送事件，等待高德规划成功后发送。"""
        if vehicle is None or not event:
            return None
        route_version = getattr(vehicle, "planned_route_grasp_route_version", None)
        if not route_version:
            return None
        pending_event = {
            "event_type": "fleet_route_changed",
            "event_reason": event.get("event_reason"),
            "vehicle_id": CoreDispatcher._vehicle_identity(vehicle),
            "request_id": event.get("request_id"),
            "route_version": route_version,
            "created_at": datetime.now().replace(microsecond=0),
        }
        events = CoreDispatcher._vehicle_fleet_push_pending_events(vehicle, create=True)
        events.append(pending_event)
        vehicle.fleet_push_pending_event = pending_event
        CoreDispatcher._refresh_pending_driver_push_route_versions(vehicle, route_version)
        return pending_event

    @staticmethod
    def _submit_pending_fleet_push_if_ready(vehicle):
        """高德路线 ready 后提交当前版本的待推送单车导航快照。"""
        events = CoreDispatcher._vehicle_fleet_push_pending_events(vehicle)
        if not events:
            return False
        route_version = getattr(vehicle, "planned_route_grasp_route_version", None)
        if getattr(vehicle, "planned_route_grasp_status", None) != "ready":
            return False
        submitted_any = False
        remaining = []
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("route_version") != route_version:
                continue
            submitted = fleet_push.submit_vehicle_navigation(vehicle, event)
            submitted_any = submitted_any or submitted
            if not submitted:
                remaining.append(event)
        CoreDispatcher._set_vehicle_fleet_push_pending_events(vehicle, remaining)
        return submitted_any

    @staticmethod
    def _vehicle_fleet_push_pending_events(vehicle, create=False):
        """读取车辆待推送事件队列，并兼容旧的单事件字段。"""
        if vehicle is None:
            return []
        events = getattr(vehicle, "fleet_push_pending_events", None)
        if isinstance(events, list):
            return events
        legacy_event = getattr(vehicle, "fleet_push_pending_event", None)
        if isinstance(legacy_event, dict):
            events = [legacy_event]
        else:
            events = []
        if create or events:
            vehicle.fleet_push_pending_events = events
        return events

    @staticmethod
    def _set_vehicle_fleet_push_pending_events(vehicle, events):
        """写回车辆待推送事件队列，并维护旧字段兼容。"""
        if vehicle is None:
            return
        clean_events = [event for event in (events or []) if isinstance(event, dict)]
        vehicle.fleet_push_pending_events = clean_events
        vehicle.fleet_push_pending_event = clean_events[-1] if clean_events else None

    @staticmethod
    def _remove_vehicle_fleet_push_events(vehicle, request_id):
        """移除指定订单对应的待推送事件。"""
        if vehicle is None:
            return
        request_id = str(request_id or "")
        events = [
            event for event in CoreDispatcher._vehicle_fleet_push_pending_events(vehicle)
            if str(event.get("request_id") or "") != request_id
        ]
        CoreDispatcher._set_vehicle_fleet_push_pending_events(vehicle, events)

    @staticmethod
    def _vehicle_driver_push_pending_map(vehicle, create=False):
        """读取车辆上的订单级司机端待确认索引。"""
        if vehicle is None:
            return {}
        pending = getattr(vehicle, "driver_push_pending_orders", None)
        if isinstance(pending, dict):
            return pending
        pending = {}
        request_id = getattr(vehicle, "driver_push_pending_request_id", None)
        if request_id:
            pending[str(request_id)] = {
                "request_id": str(request_id),
                "route_version": getattr(vehicle, "driver_push_route_version", None),
                "created_at": None,
            }
        if create or pending:
            vehicle.driver_push_pending_orders = pending
        return pending

    @staticmethod
    def _sync_vehicle_driver_push_pending_flag(vehicle):
        """根据订单级待确认索引刷新车辆汇总标记。"""
        if vehicle is None:
            return
        pending = CoreDispatcher._vehicle_driver_push_pending_map(vehicle)
        vehicle.driver_push_pending = bool(pending)
        vehicle.driver_push_pending_request_id = next(iter(pending), None)
        vehicle.driver_push_route_version = None
        if pending:
            first = pending.get(vehicle.driver_push_pending_request_id) or {}
            vehicle.driver_push_route_version = first.get("route_version")

    @staticmethod
    def _refresh_pending_driver_push_route_versions(vehicle, route_version):
        """车辆路线版本变化时，把未确认订单和待推送事件绑定到最新版本。"""
        if vehicle is None or not route_version:
            return
        pending = CoreDispatcher._vehicle_driver_push_pending_map(vehicle, create=True)
        for step in getattr(vehicle, "planned_route", []) or []:
            order = step.get("order") if isinstance(step, dict) else None
            if order is None:
                continue
            if not (getattr(order, "driver_push_pending", False) or getattr(order, "status", None) == "matched"):
                continue
            request_id = str(getattr(order, "request_id", ""))
            if not request_id:
                continue
            order.driver_push_route_version = route_version
            pending.setdefault(request_id, {"request_id": request_id})["route_version"] = route_version
        for event in CoreDispatcher._vehicle_fleet_push_pending_events(vehicle):
            request_id = str(event.get("request_id") or "")
            if request_id in pending:
                event["route_version"] = route_version
                event["driver_push_route_version"] = route_version
        CoreDispatcher._sync_vehicle_driver_push_pending_flag(vehicle)

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
        operation_area_id = CoreDispatcher._coerce_operation_area_id(vehicle_state.get("operation_area_id"))
        if operation_area_id is None and route:
            operation_area_id = CoreDispatcher._order_operation_area_id(route[0].get("order"))
        restriction_policy = CoreDispatcher.current_operation_restriction_policy(operation_area_id)
        
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
        pickup_arrival_times = {}
        arrival_times = {}
        early_pickup_wait_seconds = {}
        total_early_pickup_wait_seconds = 0.0
        
        for step in route:
            order = step['order']
            target_node = order.o_node if step['type'] == 'O' else order.d_node
            
            dist, path = CoreDispatcher._get_path(
                city_map,
                city_map.nodes_map[sim_next_node],
                target_node,
                restriction_policy=restriction_policy,
            )
            
            if dist == float('inf'):
                return _result(False, float('inf'), None, {"infeasible_reason": "path_unreachable"})
                
            if current_load == 0:
                empty_dist += dist
            else:
                loaded_dist += dist
                
            sim_time += dist / speed
            sim_next_node = target_node.id
            
            if step['type'] == 'O':
                pickup_arrival_times[order.request_id] = sim_time
                earliest_pickup_time = CoreDispatcher._order_pickup_earliest_timestamp(order)
                early_wait_seconds = max(0.0, earliest_pickup_time - sim_time)
                if early_wait_seconds > CoreDispatcher.MAX_EARLY_PICKUP_WAIT_SECONDS:
                    return _result(False, float('inf'), None, {
                        "infeasible_reason": "pickup_too_early",
                        "request_id": order.request_id,
                        "early_wait_seconds": early_wait_seconds,
                    })
                if early_wait_seconds > 0.0:
                    sim_time = earliest_pickup_time
                    early_pickup_wait_seconds[order.request_id] = early_wait_seconds
                    total_early_pickup_wait_seconds += early_wait_seconds

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
        EARLY_PICKUP_WAIT_COST_PER_MIN = CoreDispatcher.EARLY_PICKUP_WAIT_COST_PER_MIN
        LATE_PICKUP_COST_PER_MIN = CoreDispatcher.LATE_PICKUP_COST_PER_MIN
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
        early_pickup_wait_cost = 0.0
        late_pickup_cost = 0.0
        in_car_cost = 0.0
        late_arrival_cost = 0.0
        old_passenger_delay_cost = 0.0
        old_passenger_severe_delay_cost = 0.0
        for step in route:
            order = step['order']
            if step['type'] == 'O':
                wait_start_time = max(
                    float(getattr(order, "req_time", 0.0) or 0.0),
                    CoreDispatcher._order_pickup_earliest_timestamp(order),
                )
                wait_minutes = max(0.0, pickup_times[order.request_id] - wait_start_time) / SECONDS_PER_MINUTE
                wait_cost += wait_minutes * WAIT_COST_PER_MIN

                early_wait_minutes = early_pickup_wait_seconds.get(order.request_id, 0.0) / SECONDS_PER_MINUTE
                early_pickup_wait_cost += early_wait_minutes * EARLY_PICKUP_WAIT_COST_PER_MIN
                
                # 时间窗满意度：超出期望上车时间不再一票否决，改为有限惩罚，允许积压订单继续派单。
                latest_pickup_time = CoreDispatcher._order_pickup_latest_timestamp(order)
                late_pickup_minutes = max(0.0, pickup_times[order.request_id] - latest_pickup_time) / SECONDS_PER_MINUTE
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
            + early_pickup_wait_cost
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
            "early_pickup_wait_cost": early_pickup_wait_cost,
            "late_pickup_cost": late_pickup_cost,
            "time_window_cost": early_pickup_wait_cost + late_pickup_cost,
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
                "pickup_arrival_times": pickup_arrival_times,
                "arrival_times": arrival_times,
                "early_pickup_wait_seconds": early_pickup_wait_seconds,
                "total_early_pickup_wait_seconds": total_early_pickup_wait_seconds,
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
            'progress': vehicle.progress,
            'operation_area_id': getattr(vehicle, "operation_area_id", None),
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
            'progress': vehicle.progress,
            'operation_area_id': getattr(vehicle, "operation_area_id", None),
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
    def _driver_push_failure_mode(reason):
        """根据平台回传原因判断订单对原车辆的排除方式。

        这里只识别两个平台约定值：
        - driver_push_unreachable：网络或超时导致司机端未及时收到，临时冷却。
        - driver_declined：司机主动拒单，对该订单永久排除该车辆。
        未知值按网络未达处理，避免因为平台字符串异常而误永久排除。
        """
        normalized = str(reason or "").strip()
        if normalized == CoreDispatcher.DRIVER_DECLINED_REASON:
            return "permanent"
        return "cooldown"

    @staticmethod
    def _record_driver_push_vehicle_exclusion(order, vehicle, reason, current_timestamp=None):
        """记录某订单在重新匹配时需要排除的原车辆。

        排除维度是“订单 + 车辆”，不会影响该车辆继续接其他订单。
        网络未达写入 3 分钟冷却；司机主动拒单写入永久排除。
        """
        if order is None or vehicle is None:
            return None
        vehicle_id = str(CoreDispatcher._vehicle_identity(vehicle) or getattr(vehicle, "id", "") or "")
        if not vehicle_id:
            return None
        now_ts = CoreDispatcher._event_timestamp(current_timestamp)
        mode = CoreDispatcher._driver_push_failure_mode(reason)
        until_ts = None
        if mode == "cooldown":
            until_ts = now_ts + CoreDispatcher.DRIVER_PUSH_UNREACHABLE_COOLDOWN_SECONDS
            normalized_reason = CoreDispatcher.DRIVER_PUSH_UNREACHABLE_REASON
        else:
            normalized_reason = CoreDispatcher.DRIVER_DECLINED_REASON

        exclusions = getattr(order, "driver_push_vehicle_exclusions", None)
        if not isinstance(exclusions, dict):
            exclusions = {}
            order.driver_push_vehicle_exclusions = exclusions
        exclusions[vehicle_id] = {
            "mode": mode,
            "reason": normalized_reason,
            "until_ts": until_ts,
            "created_at": now_ts,
        }
        return exclusions[vehicle_id]

    @staticmethod
    def _vehicle_excluded_for_order(order, vehicle, current_timestamp=None):
        """判断某订单当前是否应跳过指定车辆。

        冷却排除到期后会自动清理；永久排除会一直保留在订单内存对象上。
        """
        exclusions = getattr(order, "driver_push_vehicle_exclusions", None)
        if not isinstance(exclusions, dict) or vehicle is None:
            return False
        vehicle_id = str(CoreDispatcher._vehicle_identity(vehicle) or getattr(vehicle, "id", "") or "")
        if not vehicle_id:
            return False
        rule = exclusions.get(vehicle_id)
        if not isinstance(rule, dict):
            return False
        if rule.get("mode") == "permanent":
            return True

        until_ts = rule.get("until_ts")
        try:
            until_ts = float(until_ts)
        except (TypeError, ValueError):
            exclusions.pop(vehicle_id, None)
            return False
        if CoreDispatcher._event_timestamp(current_timestamp) < until_ts:
            return True
        exclusions.pop(vehicle_id, None)
        return False

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
    def _coerce_operation_area_id(value):
        """把运营区 ID 统一转换为整数。"""
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _operation_area_id_of(obj):
        """读取订单或车辆所属运营区 ID。"""
        return CoreDispatcher._coerce_operation_area_id(getattr(obj, "operation_area_id", None))

    @staticmethod
    def _order_operation_area_id(order):
        """读取订单运营区 ID；为空时不再按默认运营区参与匹配。"""
        return CoreDispatcher._operation_area_id_of(order)

    @staticmethod
    def _process_pool_matching_area_cycle(fleet, city_map, operation_area_id=None):
        """对单个运营区执行一轮订单池匹配。"""
        area_id = CoreDispatcher._coerce_operation_area_id(operation_area_id)
        
        area_fleet = [
            vehicle for vehicle in (fleet or [])
            if area_id is None or CoreDispatcher._operation_area_id_of(vehicle) == area_id
        ]
        area_order_indices = [
            index for index, order in enumerate(CoreDispatcher.order_pool)
            if area_id is None or CoreDispatcher._order_operation_area_id(order) == area_id
        ]
        # 需要解决的地方：空车预测会阻塞接口
        if not area_order_indices:
            CoreDispatcher.assign_idle_parking_targets(area_fleet, city_map, operation_area_id=area_id)
            return 0

        assign_count = 0
        while True:
            area_order_indices = [
                index for index, order in enumerate(CoreDispatcher.order_pool)
                if area_id is None or CoreDispatcher._order_operation_area_id(order) == area_id
            ]
            
            if not area_order_indices:
                break

            best_o_idx = -1
            global_best_v = None
            global_best_route = None
            best_priority_score = 0.0
            best_cancel_risk_score = 0.0
            order_candidates = []
            current_timestamp = max(
                (getattr(v, "time", 0.0) for v in area_fleet),
                default=time.time(),
            ) or time.time()

            for i in area_order_indices:
                order = CoreDispatcher.order_pool[i]
                if not CoreDispatcher._order_can_enter_matching_window(order, current_timestamp):
                    continue

                c1, c2 = float("inf"), float("inf")
                v1, r1 = None, None

                for v in area_fleet:
                    if CoreDispatcher._vehicle_excluded_for_order(order, v, current_timestamp):
                        continue
                    if not CoreDispatcher._vehicle_has_capacity_for_order(v, order):
                        continue
                    if not CoreDispatcher._vehicle_can_accept_order(v):
                        continue

                    original_cost = CoreDispatcher._evaluate_vehicle_current_route_cost(v, city_map)
                    route, absolute_cost = CoreDispatcher._try_insert_order(v, order, city_map)
                    is_idle = len(v.on_board_orders) == 0 and len(v.planned_route) == 0
                    cost = (
                        absolute_cost - original_cost
                        if route is not None and absolute_cost != float("inf")
                        else float("inf")
                    )
                    if not is_idle and absolute_cost > 200.0:
                        cost = float("inf")
                    if cost < c1:
                        c2 = c1
                        c1 = cost
                        v1 = v
                        r1 = route
                    elif cost < c2:
                        c2 = cost

                if c1 == float("inf"):
                    continue

                regret = None if c2 == float("inf") else max(0.0, c2 - c1)
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

            if best_o_idx == -1:
                break

            target_o = CoreDispatcher.order_pool.pop(best_o_idx)
            CoreDispatcher._assign_order_to_vehicle_pending_confirmation(
                target_o,
                global_best_v,
                global_best_route,
                city_map,
                details={
                    "cancel_risk_score": best_cancel_risk_score,
                    "priority_score": best_priority_score,
                },
            )
            assign_count += 1
            print(
                f"[Core.Pool] [Match] 运营区 {area_id or 'default'} 订单 {target_o.request_id} "
                f"划拨给 {global_best_v.id}，风险分={best_cancel_risk_score:.1f}，综合优先级={best_priority_score:.1f}"
            )

        return assign_count

    @staticmethod
    def _assign_order_to_vehicle_pending_confirmation(order, vehicle, route, city_map, details=None):
        """把订单临时派给车辆，并等待平台确认司机端收到后再转 waiting_pickup。"""
        was_idle_before_assignment = (
            len(getattr(vehicle, "on_board_orders", []) or []) == 0
            and len(getattr(vehicle, "planned_route", []) or []) == 0
        )
        event_reason = "order_assigned" if was_idle_before_assignment else "order_inserted"
        CoreDispatcher._clear_idle_parking(vehicle)
        vehicle.planned_route = route
        order.status = "matched"
        route_result = CoreDispatcher.refresh_vehicle_route_metadata(
            vehicle,
            city_map,
            fleet_push_event={
                "event_reason": event_reason,
                "request_id": order.request_id,
            },
        )
        CoreDispatcher._set_driver_push_pending(
            order,
            vehicle,
            event_reason=event_reason,
        )
        persistence.record_order_matched_pending(
            order,
            vehicle,
            city_map=city_map,
            path_result=route_result,
            details={
                **(details or {}),
                "driver_push_pending": True,
            },
        )
        return route_result

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
        if isinstance(city_map, dict):
            while True:
                if not CoreDispatcher.order_pool:
                    print(f"[Core.Pool] 池中暂无订单...")
                if CoreDispatcher.order_pool:
                    print(f"[Core.Pool] 正在对池中 {len(CoreDispatcher.order_pool)} 个订单执行后悔值统筹调度...")
                with lock_context:
                    assign_count = 0
                    for operation_area_id, area_city in city_map.items():
                        area_fleet = [
                            vehicle for vehicle in (fleet or [])
                            if CoreDispatcher._operation_area_id_of(vehicle) == operation_area_id
                        ]
                        CoreDispatcher.refresh_scheduled_rest_requests(area_fleet, area_city)
                        assign_count += CoreDispatcher._process_pool_matching_area_cycle(
                            area_fleet,
                            area_city,
                            operation_area_id=operation_area_id,
                        )
                    if assign_count > 0:
                        print(f"[Core.Pool] 多运营区本轮调度完毕：成功释放 {assign_count} 个积压订单。")
                time.sleep(5)

        while True:
            with lock_context:
                CoreDispatcher.refresh_scheduled_rest_requests(fleet, city_map)

                if not CoreDispatcher.order_pool:
                    print(f"[Core.Pool] 池中暂无订单...")
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
                        if not CoreDispatcher._order_can_enter_matching_window(order, current_timestamp):
                            continue

                        c1, c2 = float('inf'), float('inf')
                        v1, r1 = None, None

                        for v in fleet:
                            if CoreDispatcher._vehicle_excluded_for_order(order, v, current_timestamp):
                                continue
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
                        CoreDispatcher._assign_order_to_vehicle_pending_confirmation(
                            target_o,
                            global_best_v,
                            global_best_route,
                            city_map=city_map,
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
    def _event_timestamp(value=None):
        """把接口或内部传入时间统一转为时间戳。"""
        if value is None:
            return time.time()
        if isinstance(value, datetime):
            return value.timestamp()
        try:
            return float(value)
        except (TypeError, ValueError):
            return time.time()

    @staticmethod
    def _event_datetime(value=None):
        """把接口或内部传入时间统一转为 datetime。"""
        if isinstance(value, datetime):
            return value.replace(microsecond=0)
        return datetime.fromtimestamp(CoreDispatcher._event_timestamp(value)).replace(microsecond=0)

    @staticmethod
    def _route_version_matches(expected, actual):
        """校验平台回调的路线版本；为空时允许兼容旧平台。"""
        if expected in (None, "") or actual in (None, ""):
            return True
        return str(expected) == str(actual)

    @staticmethod
    def _set_driver_push_pending(order, vehicle, event_reason=None, current_timestamp=None):
        """订单匹配成功后设置司机端接收待确认标记。"""
        now_ts = CoreDispatcher._event_timestamp(current_timestamp)
        route_version = getattr(vehicle, "planned_route_grasp_route_version", None)
        vehicle_id = CoreDispatcher._vehicle_identity(vehicle)
        request_id = str(getattr(order, "request_id", ""))

        order.status = "matched"
        order.driver_push_pending = True
        order.driver_push_vehicle_id = vehicle_id
        order.driver_push_route_version = route_version
        order.driver_push_attempt = int(getattr(order, "driver_push_attempt", 0) or 0) + 1
        order.driver_push_reason = event_reason or "order_assigned"
        order.driver_push_created_at = now_ts
        order.driver_push_confirmed_at = None
        order.driver_push_failed_reason = None

        pending = CoreDispatcher._vehicle_driver_push_pending_map(vehicle, create=True)
        pending[request_id] = {
            "request_id": request_id,
            "route_version": route_version,
            "event_reason": event_reason or "order_assigned",
            "created_at": now_ts,
        }

        for pending_event in CoreDispatcher._vehicle_fleet_push_pending_events(vehicle):
            if not isinstance(pending_event, dict) or str(pending_event.get("request_id") or "") != request_id:
                continue
            pending_event.update({
                "driver_push_confirmation_required": True,
                "confirmation_request_id": request_id,
                "driver_push_route_version": route_version,
            })
        CoreDispatcher._sync_vehicle_driver_push_pending_flag(vehicle)
        return route_version

    @staticmethod
    def _clear_driver_push_pending(order=None, vehicle=None):
        """清理订单和车辆上的司机端待确认标记。"""
        request_id = str(getattr(order, "request_id", "") or "") if order is not None else None
        if order is not None:
            order.driver_push_pending = False
            order.driver_push_vehicle_id = None
            order.driver_push_route_version = None
            order.driver_push_reason = None
            order.driver_push_created_at = None
        if vehicle is not None:
            pending = CoreDispatcher._vehicle_driver_push_pending_map(vehicle)
            if request_id:
                pending.pop(request_id, None)
                CoreDispatcher._remove_vehicle_fleet_push_events(vehicle, request_id)
            CoreDispatcher._sync_vehicle_driver_push_pending_flag(vehicle)

    @staticmethod
    def _find_vehicle_pending_order(vehicle, request_id):
        """从车辆计划路线中查找指定待确认订单。"""
        request_id = str(request_id)
        for step in getattr(vehicle, "planned_route", []) or []:
            order = step.get("order")
            if order is not None and str(getattr(order, "request_id", "")) == request_id:
                return order
        return None

    @staticmethod
    def _find_pending_driver_push(request_id, fleet):
        """根据订单号在车队中查找司机端待确认订单和车辆。"""
        request_id = str(request_id)
        for vehicle in fleet or []:
            order = CoreDispatcher._find_vehicle_pending_order(vehicle, request_id)
            if order is None:
                continue
            if getattr(order, "driver_push_pending", False) or getattr(order, "status", None) == "matched":
                return order, vehicle
        return None, None

    @staticmethod
    def _remove_order_from_vehicle_route(vehicle, request_id):
        """从车辆后续路线中移除某订单的 O/D 步骤。"""
        request_id = str(request_id)
        before = len(getattr(vehicle, "planned_route", []) or [])
        vehicle.planned_route = [
            step for step in getattr(vehicle, "planned_route", []) or []
            if str(getattr(step.get("order"), "request_id", "")) != request_id
        ]
        return before - len(vehicle.planned_route)

    @staticmethod
    def _requeue_driver_push_order(order, vehicle, city_map, reason="driver_push_failed"):
        """司机端未收到或超时时撤销派车，并把订单退回池中。"""
        request_id = str(getattr(order, "request_id", ""))
        exclusion = CoreDispatcher._record_driver_push_vehicle_exclusion(order, vehicle, reason)
        removed_steps = CoreDispatcher._remove_order_from_vehicle_route(vehicle, request_id)
        order.status = "pooled"
        order.driver_push_failed_reason = (exclusion or {}).get("reason") or reason
        CoreDispatcher._clear_driver_push_pending(order, vehicle)
        if all(str(getattr(existing, "request_id", "")) != request_id for existing in CoreDispatcher.order_pool):
            CoreDispatcher.order_pool.append(order)

        path_result = CoreDispatcher.refresh_vehicle_route_metadata(
            vehicle,
            city_map,
            fleet_push_event=None,
        )
        CoreDispatcher._refresh_pending_driver_push_route_versions(
            vehicle,
            getattr(vehicle, "planned_route_grasp_route_version", None),
        )
        persistence.record_order_requeued_after_push_failure(order, reason=order.driver_push_failed_reason)
        persistence.record_vehicle_route(vehicle, path_result=path_result)
        persistence.record_vehicle_runtime(vehicle)
        return {
            "status": "requeued",
            "request_id": request_id,
            "vehicle_id": CoreDispatcher._vehicle_identity(vehicle),
            "removed_steps": removed_steps,
            "reason": order.driver_push_failed_reason,
            "vehicle_exclusion": exclusion,
            "pool_size": len(CoreDispatcher.order_pool),
        }

    @staticmethod
    def _confirm_driver_push_received(order, vehicle, occurred_at=None):
        """平台确认司机端收到派单后，订单正式进入 waiting_pickup。"""
        if getattr(order, "status", None) == "waiting_pickup" and not getattr(order, "driver_push_pending", False):
            return {
                "status": "waiting_pickup",
                "request_id": str(getattr(order, "request_id", "")),
                "vehicle_id": CoreDispatcher._vehicle_identity(vehicle),
                "idempotent": True,
            }
        confirm_time = CoreDispatcher._event_datetime(occurred_at)
        order.status = "waiting_pickup"
        order.driver_push_confirmed_at = confirm_time
        if getattr(order, "answer_time", None) is None:
            order.answer_time = confirm_time
        CoreDispatcher._clear_driver_push_pending(order, vehicle)
        persistence.record_order_driver_push_confirmed(order, vehicle)
        persistence.record_vehicle_runtime(vehicle)
        return {
            "status": "waiting_pickup",
            "request_id": str(getattr(order, "request_id", "")),
            "vehicle_id": CoreDispatcher._vehicle_identity(vehicle),
            "answer_time": order.answer_time.isoformat(sep=" ") if isinstance(order.answer_time, datetime) else order.answer_time,
        }

    @staticmethod
    def expire_driver_push_confirmations(fleet, city_map, current_timestamp=None):
        """平台负责超时判断，算法侧不再自动退回 matched 订单。"""
        return []

    @staticmethod
    def confirm_driver_push_delivery(request_id, fleet, city_map, received=True, vehicle_id=None, route_version=None, reason=None, occurred_at=None):
        """平台回调司机端是否收到派单信息。"""
        request_id = str(request_id)
        matched_vehicle = None
        matched_order = None
        for vehicle in fleet or []:
            order = CoreDispatcher._find_vehicle_pending_order(vehicle, request_id)
            if order is None:
                continue
            matched_vehicle = vehicle
            matched_order = order
            break

        if matched_order is None:
            return {
                "ok": False,
                "status_code": 409,
                "error": "stale_confirmation",
                "request_id": request_id,
                "message": "订单不在当前待确认车辆路线中，可能已超时退回、取消或改派。",
            }

        current_vehicle_id = str(CoreDispatcher._vehicle_identity(matched_vehicle) or "")
        if vehicle_id not in (None, "") and str(vehicle_id) != current_vehicle_id:
            return {
                "ok": False,
                "status_code": 409,
                "error": "stale_confirmation",
                "request_id": request_id,
                "vehicle_id": vehicle_id,
                "current_vehicle_id": current_vehicle_id,
            }
        if getattr(matched_order, "status", None) == "waiting_pickup" and not getattr(matched_order, "driver_push_pending", False):
            result = CoreDispatcher._confirm_driver_push_received(matched_order, matched_vehicle, occurred_at=occurred_at)
            result["ok"] = True
            return result

        if not received:
            result = CoreDispatcher._requeue_driver_push_order(
                matched_order,
                matched_vehicle,
                city_map,
                reason=reason or CoreDispatcher.DRIVER_PUSH_UNREACHABLE_REASON,
            )
            result["ok"] = True
            return result

        result = CoreDispatcher._confirm_driver_push_received(matched_order, matched_vehicle, occurred_at=occurred_at)
        result["ok"] = True
        return result

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
                    "vehicle_id": CoreDispatcher._vehicle_identity(vehicle),
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
                    "vehicle_id": CoreDispatcher._vehicle_identity(vehicle),
                    "message": "订单已进入上车后的送达阶段，无法按乘客未上车取消处理。",
                }

            cancelled_order = matched_steps[0]["order"]
            vehicle.planned_route = [
                step for step in vehicle.planned_route
                if str(step["order"].request_id) != request_id
            ]
            if getattr(cancelled_order, "driver_push_pending", False):
                CoreDispatcher._clear_driver_push_pending(cancelled_order, vehicle)
            CoreDispatcher._archive_cancelled_order(cancelled_order, cancel_time=cancel_time)
            path_result = CoreDispatcher.refresh_vehicle_route_metadata(
                vehicle,
                city_map,
                fleet_push_event={
                    "event_reason": "order_cancelled",
                    "request_id": request_id,
                },
            )
            CoreDispatcher._start_rest_if_ready(vehicle)
            persistence.record_vehicle_route(vehicle, path_result=path_result)
            persistence.record_vehicle_runtime(vehicle)
            return {
                "status": "cancelled",
                "request_id": request_id,
                "source": "vehicle_route",
                "vehicle_id": CoreDispatcher._vehicle_identity(vehicle),
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
            dist, _ = CoreDispatcher._get_path(
                city_map,
                current_node,
                target["node"],
                restriction_policy=CoreDispatcher._vehicle_restriction_policy(vehicle),
            )
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
                "amap_target_point": CoreDispatcher._order_original_path_point(order, step["type"], target_node),
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
    def _order_original_path_point(order, step_type, fallback_node=None):
        """生成订单原始 O/D 坐标点，供高德驾车规划请求使用。"""
        if step_type == "O":
            lon = getattr(order, "o_lon", None)
            lat = getattr(order, "o_lat", None)
        else:
            lon = getattr(order, "d_lon", None)
            lat = getattr(order, "d_lat", None)

        if lon is None or lat is None:
            return CoreDispatcher._node_to_path_point(fallback_node) if fallback_node is not None else None

        point = {
            "id": f"order:{getattr(order, 'request_id', '')}:{step_type}:raw",
            "lon": float(lon),
            "lat": float(lat),
            "name": getattr(fallback_node, "name", None) or ("上车点" if step_type == "O" else "下车点"),
            "zone": getattr(fallback_node, "zone", None),
            "source": "order_original_coord",
        }
        if fallback_node is not None:
            point["snapped_node_id"] = fallback_node.id
            point["snapped_lon"] = fallback_node.lon
            point["snapped_lat"] = fallback_node.lat
        return point

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
    def _forecast_sample_request_id(order):
        """读取预测样本 ID，兼容数据库 dict 样本和内存 Order 对象。"""
        if isinstance(order, dict):
            return order.get("request_id")
        return getattr(order, "request_id", None)

    @staticmethod
    def _forecast_sample_request_time(order):
        """读取预测样本时间，兼容数据库 dict 样本和内存 Order 对象。"""
        if isinstance(order, dict):
            request_time = order.get("request_time")
            if request_time is not None:
                return request_time
            completion_time = order.get("completion_time")
            if completion_time is not None:
                return completion_time
            return order.get("req_time")

        request_time = getattr(order, "request_time", None)
        if request_time is not None:
            return request_time
        completion_time = getattr(order, "completion_time", None)
        if completion_time is not None:
            return completion_time
        return getattr(order, "req_time", None)

    @staticmethod
    def _forecast_history_unavailable_reason():
        """给空车预测样本为空的情况生成可读原因。"""
        db_status = persistence.status()
        if not db_status.get("enabled"):
            return "数据库持久化未启用"
        if db_status.get("last_error"):
            return f"数据库读写异常：{db_status.get('last_error')}"
        forecast_read = db_status.get("last_forecast_read") or {}
        if forecast_read:
            if not forecast_read.get("ok"):
                return forecast_read.get("reason") or "预测历史订单读取失败"
            matched_count = int(forecast_read.get("matched_row_count") or 0)
            usable_count = int(forecast_read.get("usable_order_count") or 0)
            dropped_count = int(forecast_read.get("dropped_invalid_count") or 0)
            if matched_count == 0:
                status_groups = forecast_read.get("status_groups_when_no_match") or []
                if status_groups:
                    return (
                        f"当前读取 database={forecast_read.get('database')}, "
                        f"tenant_id={forecast_read.get('tenant_id')} 未命中；"
                        f"其他完成订单分布={status_groups}"
                    )
                return (
                    f"当前读取 database={forecast_read.get('database')}, "
                    f"tenant_id={forecast_read.get('tenant_id')}，没有匹配完成订单"
                )
            if usable_count == 0 and dropped_count > 0:
                return (
                    f"查询到 {matched_count} 条完成订单，但均缺少 request_id 或 OD 经纬度字段，"
                    "已被预测输入转换过滤"
                )
        return "bus_order 中没有 status 为 completed/complete 的有效订单"

    @staticmethod
    def _collect_forecast_orders(fleet=None, operation_area_id=None):
        """收集可供 OD 预测使用的已完成订单样本。

        Args:
            fleet (list[Vehicle] | None): 保留兼容参数；预测样本以数据库已完成订单为主。

        Returns:
            list[Order|dict]: 去重后的订单样本列表。
        """
        area_id = CoreDispatcher._coerce_operation_area_id(operation_area_id)
        orders = []
        seen_ids = set()

        def order_area_matches(order):
            """判断内存样本是否属于当前运营区。"""
            if area_id is None:
                return True
            if isinstance(order, dict):
                order_area_id = order.get("operation_area_id")
            else:
                order_area_id = getattr(order, "operation_area_id", None)
            return CoreDispatcher._coerce_operation_area_id(order_area_id) == area_id

        def add_order(order):
            """按订单 ID 去重后加入预测样本集合。"""
            if not order_area_matches(order):
                return
            request_id = CoreDispatcher._forecast_sample_request_id(order)
            key = str(request_id) if request_id is not None else id(order)
            if key in seen_ids:
                return
            seen_ids.add(key)
            orders.append(order)

        for order in persistence.fetch_completed_orders_for_forecast(operation_area_id=area_id):
            add_order(order)
        for order in list(CoreDispatcher.completed_orders_pool):
            add_order(order)

        return orders

    @staticmethod
    def _forecast_order_signature(orders):
        """生成预测样本签名，用于判断热点缓存是否仍可复用。"""
        latest_time = 0.0
        for order in orders:
            request_time = CoreDispatcher._forecast_sample_request_time(order)
            if isinstance(request_time, datetime):
                order_time = request_time.timestamp()
            else:
                try:
                    order_time = float(request_time or 0.0)
                except (TypeError, ValueError):
                    order_time = 0.0
            latest_time = max(latest_time, order_time)
        return len(orders), latest_time

    @staticmethod
    def _idle_forecast_time_slot(now_ts):
        """计算当前系统时间对应的空车热点预测窗口。"""
        return od_forecast_module._slot_floor(
            datetime.fromtimestamp(now_ts) + timedelta(minutes=15)
        )

    @staticmethod
    def _idle_hotspot_cache_key(operation_area_id, city_map):
        """生成空车热点预测缓存分桶键。"""
        area_id = CoreDispatcher._coerce_operation_area_id(operation_area_id)
        if area_id is not None:
            return f"operation_area:{area_id}"
        return f"city_map:{id(city_map)}"

    @staticmethod
    def _idle_hotspot_cache_store():
        """读取空车热点预测缓存池，并兼容旧的单缓存结构。"""
        with CoreDispatcher.idle_hotspot_cache_lock:
            cache_store = CoreDispatcher.idle_hotspot_cache
            if not isinstance(cache_store, dict) or "hotspots" in cache_store:
                cache_store = {}
                CoreDispatcher.idle_hotspot_cache = cache_store
            return cache_store

    @staticmethod
    def _idle_forecast_cache_is_valid(cache, city_map, order_signature, now_ts):
        """判断空车热点预测缓存是否仍在有效期内。"""
        return (
            cache
            and cache.get("city_map_id") == id(city_map)
            and cache.get("order_signature") == order_signature
            and cache.get("forecast_time") == CoreDispatcher._idle_forecast_time_slot(now_ts)
            and float(cache.get("expires_at", 0.0)) > now_ts
        )

    @staticmethod
    def _idle_forecast_cache_can_serve(cache, city_map):
        """判断缓存是否可直接服务空车分配，不在接口路径上强制重算签名。"""
        return (
            cache
            and cache.get("city_map_id") == id(city_map)
            and bool(cache.get("hotspots"))
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
    def _build_idle_hotspot_cache(orders, order_signature, city_map, now_ts, operation_area_id=None, cache_key=None):
        """刷新未来 15 分钟空车热点预测缓存。"""
        try:
            clean_orders = od_forecast_module.orders_from_insert_riding(
                orders,
                city_map=None,
                base_datetime=datetime.fromtimestamp(0),
                speed_mps=SPEED_MPS,
            )
        except Exception as exc:
            print(f"[Core.Planner] 订单预测输入转换失败：{exc}")
            return None
        if not clean_orders:
            print("[Core.Planner] 已完成订单样本无法转换为预测输入，空车热点预测跳过。")
            return None

        # 使用当前系统时间之后的 15 分钟窗口，避免历史最新订单时间影响在线热点预测。
        forecast_time = CoreDispatcher._idle_forecast_time_slot(now_ts)
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
            print("[Core.Planner] 已完成订单样本不足或分布过稀，未生成空车热点预测结果。")
            return None

        hotspots = CoreDispatcher._build_idle_hotspot_candidates(predictions, metrics, city_map)
        if not hotspots:
            print("[Core.Planner] 预测结果没有可用热点候选，空车热点预测跳过。")
            return None

        generated_at_text = datetime.fromtimestamp(now_ts).isoformat(sep=" ", timespec="seconds")
        area_id = CoreDispatcher._coerce_operation_area_id(operation_area_id)
        cache_key = cache_key or CoreDispatcher._idle_hotspot_cache_key(area_id, city_map)
        cache = {
            "cache_key": cache_key,
            "operation_area_id": area_id,
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
        with CoreDispatcher.idle_hotspot_cache_lock:
            CoreDispatcher._idle_hotspot_cache_store()[cache_key] = cache
        area_text = f"运营区 {area_id}" if area_id is not None else f"地图 {id(city_map)}"
        print(f"[Core.Planner] 已刷新{area_text}空车热点预测缓存，候选热点 {len(hotspots)} 个。")
        return cache

    @classmethod
    def _idle_hotspot_executor(cls):
        """延迟创建空车热点预测线程池。"""
        with cls.idle_hotspot_refresh_lock:
            if cls.idle_hotspot_refresh_executor is None:
                cls.idle_hotspot_refresh_executor = ThreadPoolExecutor(
                    max_workers=cls.idle_hotspot_refresh_workers,
                    thread_name_prefix="IdleHotspotForecast",
                )
            return cls.idle_hotspot_refresh_executor

    @classmethod
    def _idle_hotspot_refresh_failed_recently(cls, cache_key, now_ts):
        """判断指定缓存桶是否刚刷新失败，避免空样本或数据库异常时刷屏重试。"""
        last_failed_at = float(cls.idle_hotspot_refresh_failures.get(cache_key, 0.0) or 0.0)
        return now_ts - last_failed_at < cls.IDLE_FORECAST_REFRESH_RETRY_SECONDS

    @classmethod
    def _refresh_idle_hotspot_cache_job(cls, city_map, operation_area_id, cache_key):
        """在线程池中刷新空车热点预测缓存，避免阻塞接口共享锁。"""
        try:
            orders = cls._collect_forecast_orders(operation_area_id=operation_area_id)
            if not orders:
                print(
                    "[Core.Planner] 未找到可用已完成订单预测样本，空车热点预测跳过："
                    f"{cls._forecast_history_unavailable_reason()}。"
                )
                cls.idle_hotspot_refresh_failures[cache_key] = time.time()
                return None

            now_ts = time.time()
            order_signature = cls._forecast_order_signature(orders)
            with cls.idle_hotspot_cache_lock:
                cache = cls._idle_hotspot_cache_store().get(cache_key)
            if cls._idle_forecast_cache_is_valid(cache, city_map, order_signature, now_ts):
                return cache

            cache = cls._build_idle_hotspot_cache(
                orders,
                order_signature,
                city_map,
                now_ts,
                operation_area_id=operation_area_id,
                cache_key=cache_key,
            )
            if cache:
                cls.idle_hotspot_refresh_failures.pop(cache_key, None)
            else:
                cls.idle_hotspot_refresh_failures[cache_key] = time.time()
            return cache
        except Exception as exc:
            cls.idle_hotspot_refresh_failures[cache_key] = time.time()
            print(f"[Core.Planner] 空车热点预测后台刷新失败：{exc}")
            return None
        finally:
            with cls.idle_hotspot_refresh_lock:
                cls.idle_hotspot_refresh_inflight.discard(cache_key)

    @classmethod
    def _schedule_idle_hotspot_cache_refresh(cls, city_map, operation_area_id=None, cache_key=None):
        """提交空车热点预测缓存刷新任务；已有任务在途时直接复用。"""
        cache_key = cache_key or cls._idle_hotspot_cache_key(operation_area_id, city_map)
        now_ts = time.time()
        with cls.idle_hotspot_refresh_lock:
            if cache_key in cls.idle_hotspot_refresh_inflight:
                return False
            if cls._idle_hotspot_refresh_failed_recently(cache_key, now_ts):
                return False
            cls.idle_hotspot_refresh_inflight.add(cache_key)

        executor = cls._idle_hotspot_executor()
        executor.submit(
            cls._refresh_idle_hotspot_cache_job,
            city_map,
            cls._coerce_operation_area_id(operation_area_id),
            cache_key,
        )
        return True

    @staticmethod
    def _get_idle_hotspot_cache(fleet, city_map, operation_area_id=None, refresh_mode="sync"):
        """读取或刷新车队级空车热点预测缓存。"""
        cache_key = CoreDispatcher._idle_hotspot_cache_key(operation_area_id, city_map)
        with CoreDispatcher.idle_hotspot_cache_lock:
            cache = CoreDispatcher._idle_hotspot_cache_store().get(cache_key)

        if refresh_mode == "async":
            now_ts = time.time()
            if (
                CoreDispatcher._idle_forecast_cache_can_serve(cache, city_map)
                and cache.get("forecast_time") == CoreDispatcher._idle_forecast_time_slot(now_ts)
                and float(cache.get("expires_at", 0.0) or 0.0) > now_ts
            ):
                return cache

            CoreDispatcher._schedule_idle_hotspot_cache_refresh(
                city_map,
                operation_area_id=operation_area_id,
                cache_key=cache_key,
            )
            if (
                CoreDispatcher._idle_forecast_cache_can_serve(cache, city_map)
                and cache.get("forecast_time") == CoreDispatcher._idle_forecast_time_slot(now_ts)
            ):
                return cache
            return None

        orders = CoreDispatcher._collect_forecast_orders(
            fleet,
            operation_area_id=operation_area_id,
        )
        if not orders:
            print(
                "[Core.Planner] 未找到可用已完成订单预测样本，空车热点预测跳过："
                f"{CoreDispatcher._forecast_history_unavailable_reason()}。"
            )
            return None

        now_ts = time.time()
        order_signature = CoreDispatcher._forecast_order_signature(orders)
        with CoreDispatcher.idle_hotspot_cache_lock:
            cache = CoreDispatcher._idle_hotspot_cache_store().get(cache_key)
        if CoreDispatcher._idle_forecast_cache_is_valid(cache, city_map, order_signature, now_ts):
            return cache

        return CoreDispatcher._build_idle_hotspot_cache(
            orders,
            order_signature,
            city_map,
            now_ts,
            operation_area_id=operation_area_id,
            cache_key=cache_key,
        )

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
        forecast = getattr(vehicle, "idle_forecast", None) or {}
        return (
            getattr(vehicle, "idle_target", None)
            and getattr(vehicle, "planned_route_point", None)
            and forecast.get("forecast_cache_key") == cache.get("cache_key")
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
    def _write_idle_hotspot_to_vehicle(vehicle, city_map, cache, hotspot, assignment_rank, fleet=None):
        """把一个热点写入车辆"""
        start_node = city_map.nodes_map.get(vehicle.next_node) or city_map.nodes_map.get(vehicle.last_node)
        if start_node is None:
            return False

        row = hotspot["row"]
        target_node = hotspot["node"]
        vehicle.idle_forecast = {
            "operation_area_id": cache.get("operation_area_id"),
            "forecast_cache_key": cache.get("cache_key"),
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

        result = CoreDispatcher.refresh_vehicle_route_metadata(
            vehicle,
            city_map,
            start_node,
            fleet_push_event={
                "event_reason": "idle_hotspot_assigned",
                "request_id": None,
            },
        )
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
    def assign_idle_parking_targets(fleet, city_map, target_vehicle=None, operation_area_id=None):
        """按车队级预测热点池为空车分散分配停靠目标。

        Args:
            fleet (list[Vehicle]): 当前车队。
            city_map (CityGraph): 路网对象。
            target_vehicle (Vehicle | None): 兼容单车入口；为空时批量处理全部空车。
            operation_area_id (int | str | None): 当前运营区 ID，用于隔离预测缓存。

        Returns:
            int: 本次新分配成功的车辆数量。
        """
        if operation_area_id is None and target_vehicle is not None:
            operation_area_id = getattr(target_vehicle, "operation_area_id", None)

        idle_vehicles = [v for v in fleet if CoreDispatcher._is_idle_vehicle_available(v)]
        if target_vehicle is not None and target_vehicle not in idle_vehicles:
            return 0
        if not idle_vehicles:
            return 0

        cache = CoreDispatcher._get_idle_hotspot_cache(
            fleet,
            city_map,
            operation_area_id=operation_area_id,
            refresh_mode="async",
        )
        if not cache or not cache.get("hotspots"):
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
                if CoreDispatcher._write_idle_hotspot_to_vehicle(vehicle, city_map, cache, hotspot, assignment_rank, fleet=fleet):
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
    def _build_idle_route_from_node(vehicle, city_map, start_node, restriction_policy=None):
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

        dist, path = CoreDispatcher._get_path(
            city_map,
            start_node,
            target_node,
            restriction_policy=restriction_policy,
        )
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
    def rebuild_vehicle_path_from_node(vehicle, city_map, start_node, restriction_policy=None):
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
        current_amap_point = CoreDispatcher._node_to_path_point(start_node)
        total_distance = 0.0

        for target in CoreDispatcher._planned_route_targets(vehicle):
            dist, path = CoreDispatcher._get_path(
                city_map,
                current_node,
                target["node"],
                restriction_policy=restriction_policy,
            )
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
                "amap_request_points": [
                    copy.deepcopy(current_amap_point),
                    copy.deepcopy(target.get("amap_target_point") or CoreDispatcher._node_to_path_point(target["node"])),
                ],
            })
            total_distance += dist
            current_node = target["node"]
            current_amap_point = target.get("amap_target_point") or CoreDispatcher._node_to_path_point(target["node"])

        return {
            "start_node": CoreDispatcher._node_to_path_point(start_node),
            "planned_route_size": len(vehicle.planned_route),
            "total_distance": total_distance,
            "path": path_points,
            "segments": route_segments,
        }

    @staticmethod
    def _vehicle_grasp_route_version(vehicle):
        """生成车辆当前计划路线的规划版本签名。

        说明:
            该版本只表达订单/热点路线是否变化，不包含 GPS 所在边和进度。
            GPS 行进只裁剪既有规划路线，不触发新的高德规划请求。
        """
        parts = [
            CoreDispatcher._vehicle_identity(vehicle),
            f"RESTRICT:{getattr(vehicle, 'operation_restriction_policy_signature', None) or 'none'}",
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
        return CoreDispatcher._short_route_version("grasp", parts)

    @staticmethod
    def _route_result_to_grasp_raw_segments(result):
        """把当前 A* 路线结果转换成后台规划线程可消费的分段快照。"""
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
            amap_request_points = copy.deepcopy(segment.get("amap_request_points") or [])
            if len(amap_request_points) >= 2:
                raw_segment["amap_request_points"] = [amap_request_points[0], amap_request_points[-1]]
            if "forecast" in segment:
                raw_segment["forecast"] = copy.deepcopy(segment.get("forecast"))
            raw_segments.append(raw_segment)
        return raw_segments

    @staticmethod
    def _clear_route_grasp_state(vehicle):
        """清理车辆路线规划与空车热点 ETA 状态。

        Args:
            vehicle (Vehicle): 需要清理规划状态的车辆。

        Side Effects:
            清空已规划总路线、已规划分段、原始分段、规划状态和空车热点 ETA。
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
    def _path_distance_m(points):
        """计算轨迹点列表的折线总距离，单位为米。"""
        distance = 0.0
        normalized = [
            point
            for point in points or []
            if isinstance(point, dict)
            and point.get("lon") is not None
            and point.get("lat") is not None
        ]
        for index in range(1, len(normalized)):
            distance += CoreDispatcher._point_distance_m(normalized[index - 1], normalized[index])
        return distance

    @staticmethod
    def _path_point_id(point):
        """读取轨迹点或节点字典中的稳定 ID。"""
        if not isinstance(point, dict):
            return None
        value = point.get("id") or point.get("nodeId") or point.get("node_id")
        return str(value) if value is not None else None

    @staticmethod
    def _segments_share_same_stop(segment, reference_segment, tolerance_m=2.0):
        """判断当前短分段是否与上一段终点代表同一个 O/D 停靠点。"""
        if not isinstance(reference_segment, dict):
            return False

        points = segment.get("points") or segment.get("path") or []
        current_point = points[-1] if points else segment.get("target_node")
        reference_target = reference_segment.get("target_node")
        reference_points = reference_segment.get("points") or reference_segment.get("path") or []
        reference_point = reference_target or (reference_points[-1] if reference_points else None)

        current_id = (
            segment.get("endNodeId")
            or CoreDispatcher._path_point_id(segment.get("target_node"))
            or CoreDispatcher._path_point_id(current_point)
        )
        reference_id = (
            reference_segment.get("endNodeId")
            or CoreDispatcher._path_point_id(reference_target)
            or CoreDispatcher._path_point_id(reference_point)
        )
        if current_id is not None and reference_id is not None and str(current_id) == str(reference_id):
            return True

        if (
            isinstance(current_point, dict)
            and isinstance(reference_point, dict)
            and current_point.get("lon") is not None
            and current_point.get("lat") is not None
            and reference_point.get("lon") is not None
            and reference_point.get("lat") is not None
        ):
            return CoreDispatcher._point_distance_m(current_point, reference_point) <= tolerance_m
        return False

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
        """从旧规划轨迹中裁出车辆当前位置之后的剩余轨迹。

        Args:
            points (list[dict]): 旧的已规划分段轨迹。
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
        """按车辆 GPS 在规划路线上的投影点裁剪一组已规划分段。

        Args:
            grasped_segments (list[dict]): 已规划分段，可能来自车辆当前状态或高德新返回结果。
            raw_segments (list[dict]): GPS 更新后重新生成的原始剩余分段。
            start_point (dict | None): 车辆真实 GPS 点；为空时退回 raw segment 起点。

        Returns:
            list[dict]: 从当前车辆位置开始的已规划分段；缺失的分段退回 raw segment。
        """
        previous_by_key = {}
        for segment in grasped_segments or []:
            previous_by_key.setdefault(CoreDispatcher._route_segment_key(segment), segment)

        trimmed_segments = []
        for index, raw_segment in enumerate(raw_segments or []):
            raw_points = copy.deepcopy(raw_segment.get("points") or [])
            if len(raw_points) < 2:
                previous = previous_by_key.get(CoreDispatcher._route_segment_key(raw_segment))
                if previous is not None:
                    segment = copy.deepcopy(previous)
                    segment["source"] = f"{previous.get('source', 'short_segment_skip_grasp')}_trimmed"
                    segment_grasp = copy.deepcopy(previous.get("grasp") or {})
                    segment_grasp["trimmed_from_previous"] = True
                    segment["grasp"] = segment_grasp
                else:
                    reference_segment = trimmed_segments[-1] if trimmed_segments else None
                    segment = CoreDispatcher._overlap_stop_grasp_segment(raw_segment, reference_segment)
                trimmed_segments.append(segment)
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
                source = (
                    f"driving_plan_trimmed"
                    if previous is not None
                    else "Amap_Driving"
                )
                grasp_meta = copy.deepcopy((previous or {}).get("grasp") or {})
                grasp_meta["trimmed_from_previous"] = previous is not None

            segment = copy.deepcopy(raw_segment)
            segment["points"] = points
            segment["source"] = source
            segment["grasp"] = grasp_meta
            if previous is not None and len(points) >= 2:
                previous_points = previous.get("points") or previous.get("path") or []
                raw_previous_distance = previous.get("distance_m") or previous.get("distance")
                try:
                    previous_distance = float(raw_previous_distance)
                except (TypeError, ValueError):
                    previous_distance = CoreDispatcher._path_distance_m(previous_points)
                trimmed_distance = CoreDispatcher._path_distance_m(points)
                previous_duration = previous.get("duration_sec")
                trimmed_duration = None
                if previous_duration is not None and previous_distance and previous_distance > 0:
                    try:
                        ratio = max(0.0, min(1.0, trimmed_distance / previous_distance))
                        trimmed_duration = float(previous_duration) * ratio
                        segment["duration_sec"] = trimmed_duration
                    except (TypeError, ValueError):
                        pass
                elif previous_duration is not None:
                    try:
                        trimmed_duration = float(previous_duration)
                        segment["duration_sec"] = trimmed_duration
                    except (TypeError, ValueError):
                        pass
                if previous.get("traffic_status") is not None:
                    segment["traffic_status"] = previous.get("traffic_status")
                segment["distance_m"] = trimmed_distance
                grasp_meta["distance_m"] = trimmed_distance
                if trimmed_duration is not None:
                    grasp_meta["duration_sec"] = trimmed_duration
                if segment.get("traffic_status") is not None:
                    grasp_meta["traffic_status"] = segment.get("traffic_status")
            trimmed_segments.append(segment)
        return trimmed_segments

    @staticmethod
    def _trim_vehicle_grasped_route_from_result(vehicle, result, start_point=None):
        """GPS 更新时只裁剪既有规划路线，不重新请求高德。

        Args:
            vehicle (Vehicle): GPS 刚更新的车辆。
            result (dict): 本次 GPS 更新后的原始剩余路径结果。
            start_point (dict | None): 车辆真实 GPS 点；用于吸附到既有规划路线。

        Returns:
            bool: 成功更新 raw segments 或裁剪规划路线返回 True。

        Side Effects:
            更新 planned_route_segment_raw_point，并在已有规划路线时同步缩短
            planned_route_segment_grasped_point/planned_route_grasped_point，
            同时把裁剪后的分段路线写入 bus_vehicle_runtime.segment_route。
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
            persistence.record_vehicle_runtime(vehicle)
        return True

    @classmethod
    def configure_route_grasp_async(cls, state_lock=None, enabled=True, max_workers=None):
        """配置路线更新触发式异步驾车规划执行器。

        Args:
            state_lock (RLock | None): 写回车辆状态时复用的全局状态锁。
            enabled (bool): 是否启用路线更新后的自动异步提交。
            max_workers (int | None): 规划线程池最大工作线程数；为空时使用默认值。

        Side Effects:
            初始化或复用 ThreadPoolExecutor，并记录写回锁。
        """
        # 高德规划请求在线程池执行；结果写回仍使用全局状态锁，避免与派单/GPS 更新并发写车辆。
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
        """关闭路线更新触发式异步驾车规划。

        Args:
            wait (bool): 是否等待线程池中已提交的规划任务结束。

        Side Effects:
            停止继续提交新规划任务，并清理正在执行任务的去重标记。
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
        """读取当前正在执行的规划任务数量。

        Returns:
            int: 线程池中仍在执行或等待写回的规划任务数。
        """
        with cls.route_grasp_inflight_lock:
            return len(cls.route_grasp_inflight)

    @staticmethod
    def _route_grasp_job_from_vehicle(vehicle):
        """从车辆 pending 路线快照构造一次驾车规划任务。

        Args:
            vehicle (Vehicle): 已由路线更新逻辑写入 raw segments 的车辆。

        Returns:
            dict | None: 可提交到规划线程池的任务快照；状态不满足时返回 None。

        Side Effects:
            如果当前车辆路线版本已经变化，会把规划状态置为 stale。
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
            "vehicle_id": CoreDispatcher._vehicle_identity(vehicle),
            "route_version": route_version,
            "segments": copy.deepcopy(raw_segments),
            "restriction_policy": CoreDispatcher._vehicle_restriction_policy(vehicle),
            "restriction_signature": getattr(vehicle, "operation_restriction_policy_signature", None) or "none",
        }

    @classmethod
    def _submit_vehicle_route_grasp_async(cls, vehicle):
        """异步提交当前车辆的待驾车规划路线任务。

        Args:
            vehicle (Vehicle): 路线刚更新、且规划状态为 pending 的车辆。

        Returns:
            bool: 成功提交新任务返回 True；未启用、无任务或重复提交返回 False。

        Side Effects:
            向线程池提交高德驾车规划请求；当前调用栈不等待高德返回。
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
            # 同一辆车同一版本只允许存在一个在途规划任务，避免重复请求高德。
            if job_key in cls.route_grasp_inflight:
                return False
            cls.route_grasp_inflight.add(job_key)

        cls.route_grasp_last_refresh_timestamp = time.time()
        # 网络请求和路线规划都在线程池执行，避免阻塞派单、GPS 更新或接口返回。
        cls.route_grasp_executor.submit(cls._execute_vehicle_route_grasp_job, vehicle, job, job_key)
        return True

    @staticmethod
    def _mark_vehicle_route_grasp_pending(vehicle, result, fleet_push_event=None):
        """路线刷新后记录原始分段，并触发异步高德驾车规划。

        Args:
            vehicle (Vehicle): 路线刚刷新完成的车辆。
            result (dict): 本地 A* 生成的总路线和分段路线结果。
            fleet_push_event (dict | None): 路线变化后待推送事件。
        Side Effects:
            写入 raw segments、规划版本和 pending 状态；如果异步规划已启用，会立即提交线程池任务。
        """
        raw_segments = CoreDispatcher._route_result_to_grasp_raw_segments(result)
        if not raw_segments:
            CoreDispatcher._clear_route_grasp_state(vehicle)
            return
        # raw segments 是规划线程消费的稳定快照，避免线程读到后续被修改的路线对象。
        vehicle.planned_route_segment_raw_point = raw_segments
        vehicle.planned_route_grasp_route_version = CoreDispatcher._vehicle_grasp_route_version(vehicle)
        vehicle.planned_route_grasp_status = "pending"
        vehicle.planned_route_grasp_error = None
        if not any(segment.get("type") == "IDLE" for segment in raw_segments):
            vehicle.idle_target_eta_seconds = None
            vehicle.idle_target_eta_time = None
            vehicle.idle_target_eta_status = None
            vehicle.idle_target_eta_error = None
        if fleet_push_event:
            CoreDispatcher._mark_fleet_push_pending(
                vehicle,
                event=fleet_push_event,
            )
        CoreDispatcher._submit_vehicle_route_grasp_async(vehicle)
        persistence.record_vehicle_route(vehicle, path_result=result)
        persistence.record_vehicle_runtime(vehicle)

    @staticmethod
    def _combine_grasped_segments(segments):
        """拼接分段规划轨迹为整条路线，去掉相邻段首尾重复点。"""
        points = []
        for segment in segments or []:
            segment_points = segment.get("points") or []
            if points and segment_points:
                points.extend(copy.deepcopy(segment_points[1:]))
            else:
                points.extend(copy.deepcopy(segment_points))
        return points

    @staticmethod
    def _short_segment_skip_grasp(segment, reason="too_few_points"):
        """把零长度或单点 O/D/IDLE 分段标记为无需高德规划的成功分段。"""
        points = copy.deepcopy(segment.get("points") or segment.get("path") or [])
        if not points and isinstance(segment.get("target_node"), dict):
            target = segment["target_node"]
            if target.get("lon") is not None and target.get("lat") is not None:
                points = [copy.deepcopy(target)]

        grasped = copy.deepcopy(segment)
        grasped["points"] = points
        grasped["source"] = "short_segment_skip_grasp"
        grasped["duration_sec"] = 0.0
        grasped["distance_m"] = segment.get("distance", segment.get("aStarDistanceM", 0.0)) or 0.0
        grasped["grasp"] = {
            "ok": True,
            "skipped": True,
            "reason": reason,
            "distance_m": grasped["distance_m"],
            "request_points": len(points),
        }
        return grasped

    @staticmethod
    def _overlap_stop_grasp_segment(segment, reference_segment=None):
        """把与上一停靠点重合的 O/D 分段绑定到上一段规划终点。"""
        if (
            reference_segment is not None
            and CoreDispatcher._segments_share_same_stop(segment, reference_segment)
        ):
            reference_points = reference_segment.get("points") or reference_segment.get("path") or []
            if reference_points:
                grasped = copy.deepcopy(segment)
                grasped["points"] = [copy.deepcopy(reference_points[-1])]
                grasped["source"] = "overlap_stop_same_point"
                grasped["duration_sec"] = 0.0
                grasped["distance_m"] = 0.0
                grasped["grasp"] = {
                    "ok": True,
                    "skipped": True,
                    "reason": "overlap_stop_same_point",
                    "overlap_with_previous_stop": True,
                    "distance_m": 0.0,
                    "request_points": len(segment.get("points") or segment.get("path") or []),
                }
                return grasped
        return CoreDispatcher._short_segment_skip_grasp(segment)

    @staticmethod
    def refresh_vehicle_route_metadata(
        vehicle,
        city_map,
        start_node=None,
        submit_grasp=True,
        fleet_push_event=None,
    ):
        """刷新车辆当前 GPS 和前端展示所需路径元数据。

        Args:
            vehicle (Vehicle): 需要同步元数据的车辆。
            city_map (CityGraph): 路网对象。
            start_node (Node | None): 指定刷新起点；为空时使用车辆 next_node/last_node。
            submit_grasp (bool): 是否在路线更新后立即提交异步高德驾车规划。
            fleet_push_event (dict | None): 需要在高德 ready 后推送的业务事件。
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
        restriction_policy = CoreDispatcher.current_operation_restriction_policy(
            getattr(vehicle, "operation_area_id", None)
        )
        if not vehicle.planned_route and vehicle.idle_target:
            result = CoreDispatcher._build_idle_route_from_node(
                vehicle,
                city_map,
                start_node,
                restriction_policy=restriction_policy,
            )
        else:
            result = CoreDispatcher.rebuild_vehicle_path_from_node(
                vehicle,
                city_map,
                start_node,
                restriction_policy=restriction_policy,
            )
        if result is None:
            vehicle.planned_route_point = []
            CoreDispatcher._clear_route_grasp_state(vehicle)
            return None

        vehicle.operation_restriction_policy = copy.deepcopy(restriction_policy) if restriction_policy else None
        vehicle.operation_restriction_policy_signature = restriction_signature(restriction_policy)
        vehicle.planned_route_point = result["path"]
        if submit_grasp:
            CoreDispatcher._mark_vehicle_route_grasp_pending(
                vehicle,
                result,
                fleet_push_event=fleet_push_event,
            )
        return result

    @staticmethod
    def _projection_to_path_point(projection):
        """将道路投影点转成接口轨迹点。

        Args:
            projection (dict): _nearest_road_projection 返回的投影结果。

        Returns:
            dict: 可直接拼接到 planned_route_point 的虚拟轨迹点。
        """
        next_node = projection.get("next_node")
        zone = getattr(next_node, "zone", None) if next_node is not None else projection.get("zone")
        return {
            "id": projection.get("id") or f"{projection.get('edge_u')}|{projection.get('edge_v')}@{projection.get('progress', 0.0):.6f}",
            "lon": projection["lon"],
            "lat": projection["lat"],
            "name": projection.get("name") or "车辆当前位置",
            "zone": zone,
            "edge_u": projection.get("edge_u"),
            "edge_v": projection.get("edge_v"),
            "progress": projection.get("progress", 0.0),
            "is_projection": True,
            "is_grasp_projection": projection.get("snap_source") == "amap_grasped_route",
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
            if step["type"] == "O" and getattr(order, "status", None) == "matched":
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
    def _remaining_route_steps_payload(vehicle):
        """把车辆剩余 O/D 计划转成接口返回结构。"""
        return [
            {
                "type": step["type"],
                "request_id": step["order"].request_id,
                "target_node": CoreDispatcher._node_to_path_point(
                    step["order"].o_node if step["type"] == "O" else step["order"].d_node
                ),
            }
            for step in getattr(vehicle, "planned_route", []) or []
        ]

    @staticmethod
    def _raw_segments_to_result_segments(raw_segments):
        """把 raw segment 快照转成 /path 响应复用的 segments 结构。"""
        segments = []
        for segment in raw_segments or []:
            path = copy.deepcopy(segment.get("points") or segment.get("path") or [])
            if not path:
                continue
            item = copy.deepcopy(segment)
            item["path"] = path
            item["distance"] = segment.get("distance", segment.get("aStarDistanceM", 0.0))
            segments.append(item)
        return segments

    @staticmethod
    def _combine_raw_segment_points(raw_segments):
        """拼接 raw segment 点列，去掉相邻段首尾重复点。"""
        points = []
        for segment in raw_segments or []:
            segment_points = copy.deepcopy(segment.get("points") or segment.get("path") or [])
            if points and segment_points:
                points.extend(segment_points[1:])
            else:
                points.extend(segment_points)
        return points

    @staticmethod
    def _vehicle_grasped_route_projection(vehicle, lon, lat):
        """把 GPS 点优先投影到车辆当前高德规划路线。"""
        target = {"lon": float(lon), "lat": float(lat)}
        candidates = []
        segments = getattr(vehicle, "planned_route_segment_grasped_point", None) or []
        for segment_index, segment in enumerate(segments):
            points = [
                copy.deepcopy(point)
                for point in (segment.get("points") or segment.get("path") or [])
                if isinstance(point, dict)
                and point.get("lon") is not None
                and point.get("lat") is not None
            ]
            if len(points) >= 2:
                candidates.append({
                    "segment_index": segment_index,
                    "segment": segment,
                    "points": points,
                })

        if not candidates:
            points = [
                copy.deepcopy(point)
                for point in (getattr(vehicle, "planned_route_grasped_point", None) or [])
                if isinstance(point, dict)
                and point.get("lon") is not None
                and point.get("lat") is not None
            ]
            if len(points) >= 2:
                candidates.append({
                    "segment_index": None,
                    "segment": None,
                    "points": points,
                })

        best = None
        for candidate in candidates:
            points = candidate["points"]
            for point_index in range(len(points) - 1):
                projection = CoreDispatcher._project_point_on_polyline_segment(
                    target,
                    points[point_index],
                    points[point_index + 1],
                )
                if best is None or projection["distance"] < best["distance"]:
                    next_point = points[point_index + 1]
                    best = {
                        "lon": projection["point"]["lon"],
                        "lat": projection["point"]["lat"],
                        "edge_u": None,
                        "edge_v": None,
                        "progress": projection["progress"],
                        "distance": projection["distance"],
                        "distance_to_gps": projection["distance"],
                        "next_node": None,
                        "next_node_point": copy.deepcopy(next_point),
                        "snap_source": "amap_grasped_route",
                        "id": f"amap_route:{candidate['segment_index']}:{point_index}@{projection['progress']:.6f}",
                        "name": "车辆当前位置",
                        "zone": next_point.get("zone"),
                        "segment_index": candidate["segment_index"],
                        "point_index": point_index,
                    }
                    segment = candidate.get("segment")
                    if isinstance(segment, dict):
                        best["segment_type"] = segment.get("type")
                        best["request_id"] = segment.get("request_id")
        return best

    @staticmethod
    def _vehicle_position_update_result(vehicle, projection, reported_lon, reported_lat, changed_steps=None):
        """组装纯 GPS 位置更新接口的路线快照。"""
        projection_point = CoreDispatcher._projection_to_path_point(projection)
        raw_segments = copy.deepcopy(getattr(vehicle, "planned_route_segment_raw_point", None) or [])
        result_segments = CoreDispatcher._raw_segments_to_result_segments(raw_segments)
        route_points = copy.deepcopy(getattr(vehicle, "planned_route_point", None) or [])
        if not route_points:
            route_points = CoreDispatcher._combine_raw_segment_points(raw_segments)
        if not route_points:
            route_points = copy.deepcopy(getattr(vehicle, "planned_route_grasped_point", None) or [])
        if route_points:
            try:
                if CoreDispatcher._point_distance_m(projection_point, route_points[0]) > 2.0:
                    route_points = [projection_point] + route_points
            except (TypeError, ValueError, KeyError):
                route_points = [projection_point] + route_points
        else:
            route_points = [projection_point]

        snapped_point = {
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
            "route_progress": projection.get("route_progress"),
            "distance_to_gps": projection["distance_to_gps"],
            "next_node": (
                CoreDispatcher._node_to_path_point(projection["next_node"])
                if projection.get("next_node") is not None
                else projection.get("next_node_point")
            ),
            "snap_source": projection["snap_source"],
            "request_id": projection.get("request_id"),
            "segment_type": projection.get("segment_type"),
        }
        return {
            "gps": copy.deepcopy(getattr(vehicle, "gps", {}) or {}),
            "reported_gps": {"lon": reported_lon, "lat": reported_lat},
            "path": route_points,
            "total_distance": CoreDispatcher._path_distance_m(route_points),
            "planned_route_size": len(getattr(vehicle, "planned_route", []) or []),
            "segments": result_segments,
            "snapped_point": snapped_point,
            "changed_steps": changed_steps or [],
            "on_board_orders": [o.request_id for o in getattr(vehicle, "on_board_orders", []) or []],
            "planned_route": CoreDispatcher._remaining_route_steps_payload(vehicle),
        }

    @staticmethod
    def update_vehicle_position_from_gps(vehicle, city_map, lon, lat, current_timestamp=None):
        """只根据 GPS 坐标更新车辆道路吸附位置，不推进订单和不重建路线。

        Args:
            vehicle (Vehicle): 需要更新位置的车辆。
            city_map (CityGraph): 路网对象。
            lon (float): 前端上报 GPS 经度。
            lat (float): 前端上报 GPS 纬度。
            current_timestamp (float | None): GPS 上报业务时间。

        Returns:
            dict | None: 前端展示所需的吸附点、当前路线快照和订单状态；
                吸附失败时返回 None。

        Side Effects:
            更新 vehicle.gps、last_node、next_node、progress，并写入运行态和轨迹。
        """
        projection = CoreDispatcher._vehicle_grasped_route_projection(vehicle, lon, lat)
        if projection is not None:
            projection["route_progress"] = projection.get("progress")
            road_projection = CoreDispatcher._nearest_road_projection(
                city_map,
                projection["lon"],
                projection["lat"],
                None,
            )
            if road_projection is not None:
                projection["edge_u"] = road_projection["edge_u"]
                projection["edge_v"] = road_projection["edge_v"]
                projection["progress"] = road_projection["progress"]
                projection["next_node"] = road_projection["next_node"]
        else:
            projection = CoreDispatcher._nearest_road_projection(city_map, lon, lat, vehicle)
        if projection is None:
            return None

        vehicle.gps = {"lon": projection["lon"], "lat": projection["lat"]}
        if projection.get("edge_u") is not None:
            vehicle.last_node = projection["edge_u"]
        if projection.get("edge_v") is not None:
            vehicle.next_node = projection["edge_v"]
        vehicle.progress = projection.get("progress", vehicle.progress)

        raw_segments = getattr(vehicle, "planned_route_segment_raw_point", None) or []
        grasped_segments = getattr(vehicle, "planned_route_segment_grasped_point", None) or []
        if raw_segments and grasped_segments:
            projection_point = CoreDispatcher._projection_to_path_point(projection)
            trimmed_segments = CoreDispatcher._trim_grasped_segments_to_position(
                grasped_segments,
                raw_segments,
                start_point=projection_point,
            )
            if trimmed_segments:
                vehicle.planned_route_segment_grasped_point = trimmed_segments
                vehicle.planned_route_grasped_point = CoreDispatcher._combine_grasped_segments(trimmed_segments)

        result = CoreDispatcher._vehicle_position_update_result(
            vehicle,
            projection,
            float(lon),
            float(lat),
        )
        persistence.record_path_update(
            vehicle,
            result,
            report_time=current_timestamp if current_timestamp is not None else time.time(),
        )
        return result

    @staticmethod
    def _route_segment_matches_step(segment, step):
        """判断路线分段是否对应指定 O/D 步骤。"""
        if not isinstance(segment, dict) or not isinstance(step, dict):
            return False
        order = step.get("order")
        request_id = str(getattr(order, "request_id", "")) if order is not None else None
        segment_request_id = segment.get("request_id")
        return (
            segment.get("type") == step.get("type")
            and str(segment_request_id) == request_id
        )

    @staticmethod
    def _reindex_route_segments(segments):
        """重排分段 index，保持快照中的顺序字段连续。"""
        for index, segment in enumerate(segments or []):
            if isinstance(segment, dict):
                segment["index"] = index
        return segments

    @staticmethod
    def _drop_completed_route_prefix(vehicle, step):
        """上下客确认后移除已完成的首段路线快照。"""
        raw_segments = copy.deepcopy(getattr(vehicle, "planned_route_segment_raw_point", None) or [])
        if raw_segments and CoreDispatcher._route_segment_matches_step(raw_segments[0], step):
            raw_segments = raw_segments[1:]
            vehicle.planned_route_segment_raw_point = CoreDispatcher._reindex_route_segments(raw_segments)
            vehicle.planned_route_point = CoreDispatcher._combine_raw_segment_points(raw_segments)

        grasped_segments = copy.deepcopy(getattr(vehicle, "planned_route_segment_grasped_point", None) or [])
        if grasped_segments and CoreDispatcher._route_segment_matches_step(grasped_segments[0], step):
            grasped_segments = grasped_segments[1:]
            vehicle.planned_route_segment_grasped_point = CoreDispatcher._reindex_route_segments(grasped_segments)
            vehicle.planned_route_grasped_point = CoreDispatcher._combine_grasped_segments(grasped_segments)

        if not raw_segments and not getattr(vehicle, "planned_route", None):
            vehicle.planned_route_point = []
        if not grasped_segments and not getattr(vehicle, "planned_route", None):
            vehicle.planned_route_grasped_point = []
            vehicle.planned_route_segment_grasped_point = []

        if raw_segments or grasped_segments or getattr(vehicle, "planned_route", None):
            vehicle.planned_route_grasp_route_version = CoreDispatcher._vehicle_grasp_route_version(vehicle)
        else:
            vehicle.planned_route_grasp_status = None
            vehicle.planned_route_grasp_error = None
            vehicle.planned_route_grasp_route_version = None

    @staticmethod
    def confirm_vehicle_boarding_event(
        vehicle,
        action,
        request_id=None,
        lon=None,
        lat=None,
        distance_threshold_m=30.0,
        current_timestamp=None,
    ):
        """按司机端显式信号确认当前 O/D 上下客步骤。

        Args:
            vehicle (Vehicle): 需要推进订单状态的车辆。
            action (str): pickup 或 dropoff。
            request_id (str | None): 可选订单号；为空时使用当前下一步。
            lon (float | None): 可选确认位置经度；为空时使用车辆当前 GPS。
            lat (float | None): 可选确认位置纬度；为空时使用车辆当前 GPS。
            distance_threshold_m (float): 允许确认的最大距离，单位米。
            current_timestamp (float | None): 事件业务时间。

        Returns:
            dict: 包含 ok、event、planned_route 和错误信息的确认结果。

        Side Effects:
            推进订单状态，移除当前 planned_route 首步，并同步缩短路线快照。
        """
        action = str(action or "").strip().lower()
        if action not in {"pickup", "dropoff"}:
            return {"ok": False, "status_code": 400, "error": "action 必须是 pickup 或 dropoff"}
        if not getattr(vehicle, "planned_route", None):
            return {"ok": False, "status_code": 409, "error": "车辆当前没有待确认的上下客步骤"}

        step = vehicle.planned_route[0]
        expected_action = "pickup" if step.get("type") == "O" else "dropoff"
        order = step.get("order")
        if order is None:
            return {"ok": False, "status_code": 409, "error": "当前路线步骤缺少订单对象"}
        if action != expected_action:
            return {
                "ok": False,
                "status_code": 409,
                "error": f"当前步骤需要 {expected_action}，不能执行 {action}",
            }
        if request_id is not None and str(request_id) != str(order.request_id):
            return {"ok": False, "status_code": 409, "error": "request_id 不是当前下一步订单"}
        order_status = getattr(order, "status", None)
        if expected_action == "pickup" and order_status == "matched":
            return {
                "ok": False,
                "status_code": 409,
                "error": "订单仍在等待司机端接收确认，不能执行上车确认",
                "code": "driver_push_not_confirmed",
            }
        if expected_action == "pickup" and order_status not in (None, "", "waiting_pickup"):
            return {
                "ok": False,
                "status_code": 409,
                "error": f"订单当前状态为 {order_status}，不能执行上车确认",
                "code": "invalid_order_status",
            }
        if expected_action == "dropoff" and order_status not in (None, "", "riding"):
            return {
                "ok": False,
                "status_code": 409,
                "error": f"订单当前状态为 {order_status}，不能执行下车确认",
                "code": "invalid_order_status",
            }

        target_node = order.o_node if step.get("type") == "O" else order.d_node
        gps = getattr(vehicle, "gps", {}) or {}
        check_lon = gps.get("lon") if lon is None else lon
        check_lat = gps.get("lat") if lat is None else lat
        if check_lon is None or check_lat is None:
            return {"ok": False, "status_code": 400, "error": "车辆当前位置为空，无法确认上下客"}

        try:
            check_lon = float(check_lon)
            check_lat = float(check_lat)
            distance_threshold_m = float(distance_threshold_m)
        except (TypeError, ValueError):
            return {"ok": False, "status_code": 400, "error": "确认位置和距离阈值必须是数字"}
        distance_threshold_m = max(0.0, distance_threshold_m)
        distance_to_target = AuxiliaryFunctions.haversine_distance(
            check_lon,
            check_lat,
            target_node.lon,
            target_node.lat,
        )
        if distance_to_target > distance_threshold_m:
            return {
                "ok": False,
                "status_code": 409,
                "error": "车辆距离当前上下客点过远",
                "distance_to_target": distance_to_target,
                "distance_threshold_m": distance_threshold_m,
            }

        vehicle.planned_route.pop(0)
        event = CoreDispatcher._apply_reached_route_step(
            vehicle,
            step,
            target_node,
            current_timestamp=current_timestamp,
        )
        event["distance_to_target"] = distance_to_target
        event["confirmed_position"] = {"lon": check_lon, "lat": check_lat}
        CoreDispatcher._drop_completed_route_prefix(vehicle, step)
        persistence.record_vehicle_route(vehicle)
        persistence.record_vehicle_runtime(
            vehicle,
            report_time=current_timestamp if current_timestamp is not None else time.time(),
        )
        return {
            "ok": True,
            "event": event,
            "on_board_orders": [o.request_id for o in getattr(vehicle, "on_board_orders", []) or []],
            "planned_route": CoreDispatcher._remaining_route_steps_payload(vehicle),
        }

    @staticmethod
    def prepare_vehicle_amap_replan_job(vehicle, city_map):
        """为单车同步高德重规划准备 A* 分段和任务快照。

        Args:
            vehicle (Vehicle): 需要重新规划高德路径的车辆。
            city_map (CityGraph): 路网对象。

        Returns:
            dict: ok 为 True 时包含 job/path_result；失败时包含 error。

        Side Effects:
            根据车辆当前位置重建本地 A* 分段，并把车辆路线规划状态置为 pending。
        """
        gps = getattr(vehicle, "gps", {}) or {}
        lon = gps.get("lon")
        lat = gps.get("lat")
        if lon is None or lat is None:
            node = city_map.nodes_map.get(getattr(vehicle, "next_node", None))
            if node is None:
                node = city_map.nodes_map.get(getattr(vehicle, "last_node", None))
            if node is None:
                return {"ok": False, "status_code": 409, "error": "车辆当前位置为空，无法重规划"}
            lon = node.lon
            lat = node.lat

        projection = CoreDispatcher._nearest_road_projection(city_map, float(lon), float(lat), vehicle)
        if projection is None:
            return {"ok": False, "status_code": 409, "error": "车辆当前位置无法吸附到路网"}

        result = CoreDispatcher.refresh_vehicle_route_metadata(
            vehicle,
            city_map,
            projection["next_node"],
            submit_grasp=False,
        )
        if result is None:
            return {"ok": False, "status_code": 409, "error": "当前订单计划中存在不可达路段"}

        vehicle.gps = {"lon": projection["lon"], "lat": projection["lat"]}
        vehicle.last_node = projection["edge_u"]
        vehicle.next_node = projection["edge_v"]
        vehicle.progress = projection["progress"]

        projection_point = CoreDispatcher._projection_to_path_point(projection)
        result["path"] = [projection_point] + result.get("path", [])
        if result.get("segments"):
            first_segment = result["segments"][0]
            first_path = first_segment.get("path") or []
            first_segment["path"] = [projection_point] + first_path
            first_segment["startNodeId"] = projection_point["id"]
        result["planned_route_point"] = result["path"]
        result["gps"] = copy.deepcopy(vehicle.gps)
        result["reported_gps"] = copy.deepcopy(vehicle.gps)
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
            "next_node": CoreDispatcher._node_to_path_point(projection["next_node"]),
            "snap_source": projection["snap_source"],
        }
        result["changed_steps"] = []
        result["on_board_orders"] = [o.request_id for o in getattr(vehicle, "on_board_orders", []) or []]
        result["planned_route"] = CoreDispatcher._remaining_route_steps_payload(vehicle)

        vehicle.planned_route_point = result["path"]
        raw_segments = CoreDispatcher._route_result_to_grasp_raw_segments(result)
        if not raw_segments:
            CoreDispatcher._clear_route_grasp_state(vehicle)
            persistence.record_vehicle_runtime(vehicle)
            return {"ok": False, "status_code": 409, "error": "当前车辆没有可规划的高德路线"}

        vehicle.planned_route_segment_raw_point = raw_segments
        vehicle.planned_route_grasp_route_version = CoreDispatcher._vehicle_grasp_route_version(vehicle)
        vehicle.planned_route_grasp_status = "pending"
        vehicle.planned_route_grasp_error = None
        job = CoreDispatcher._route_grasp_job_from_vehicle(vehicle)
        if not job:
            return {"ok": False, "status_code": 409, "error": "无法生成高德路线规划任务"}

        persistence.record_vehicle_route(vehicle, path_result=result)
        persistence.record_vehicle_runtime(vehicle)
        return {
            "ok": True,
            "job": job,
            "path_result": result,
            "route_version": job["route_version"],
        }

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
            # 上下客会改变后续 O/D 队列；没有既有规划路线时也需要发起一次高德规划。
            CoreDispatcher._mark_vehicle_route_grasp_pending(vehicle, result)
        else:
            # 普通 GPS 前进只裁剪既有规划路线，不重新请求高德。
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
        """懒加载并复用高德 ETA 客户端。

        说明:
            API Key 优先从环境变量 AMAP_API_KEY 读取；未配置时沿用当前项目默认 Key。
            缺失或禁用时，ETA 模块会返回 disabled 状态，不影响派单、路径更新或订单状态推进。
        """
        api_key = os.getenv("AMAP_API_KEY") or cls.DEFAULT_AMAP_API_KEY
        if cls.eta_service is None or cls.eta_service_api_key != api_key:
            cls.eta_service = AmapEtaCorrectClient(api_key=api_key)
            cls.eta_service_api_key = api_key
        return cls.eta_service

    @classmethod
    def _get_route_planner(cls):
        """懒加载并复用高德驾车规划路线客户端。"""
        api_key = os.getenv("AMAP_API_KEY") or cls.DEFAULT_AMAP_API_KEY
        if cls.route_planner_service is None or cls.route_planner_api_key != api_key:
            cls.route_planner_service = AmapDrivingRoutePlanner(api_key=api_key)
            cls.route_planner_api_key = api_key
        return cls.route_planner_service

    @staticmethod
    def _collect_route_grasp_jobs(fleet):
        """采集待高德驾车规划的车辆路线快照。

        Args:
            fleet (list[Vehicle] | None): 当前车队。

        Returns:
            list[dict]: 可同步执行的路线规划任务列表。

        Side Effects:
            对版本已过期的车辆，可能把其规划状态置为 stale。
        """
        jobs = []
        for vehicle in fleet or []:
            job = CoreDispatcher._route_grasp_job_from_vehicle(vehicle)
            if job:
                jobs.append(job)
        return jobs

    @staticmethod
    def _grasp_route_segment(client, segment, previous_grasped_segment=None, restriction_policy=None):
        """对单个路线分段做高德驾车规划。

        Args:
            client (AmapDrivingRoutePlanner): 高德驾车规划客户端。
            segment (dict): 单个 O、D 或 IDLE 原始路线分段。

        Returns:
            dict: 形如 {"ok": bool, "segment": dict, "reason": str | None} 的分段规划结果。
        """
        points = copy.deepcopy(segment.get("points") or [])
        request_points = copy.deepcopy(segment.get("amap_request_points") or points)
        same_endpoint = False
        if len(request_points) >= 2:
            try:
                same_endpoint = CoreDispatcher._point_distance_m(request_points[0], request_points[-1]) <= 2.0
            except (TypeError, ValueError, KeyError):
                same_endpoint = False
        if len(request_points) < 2 or same_endpoint:
            # O/D 点重合或相邻停靠点吸附到同一路网节点时，A* 会返回单点零长度分段。
            # 这类分段直接复用上一段规划终点，确保多个重合 O/D 在高德路线里表现为同一个点。
            return {
                "ok": True,
                "segment": CoreDispatcher._overlap_stop_grasp_segment(segment, previous_grasped_segment),
            }

        if not getattr(client, "enabled", True):
            return {
                "ok": False,
                "reason": "disabled",
                "segment": segment,
            }

        # 只用分段起终点规划
        if hasattr(client, "plan_segment_sync"):
            try:
                driving = client.plan_segment_sync(request_points, restriction_policy=restriction_policy)
            except TypeError as exc:
                text = str(exc)
                if "restriction_policy" in text or "unexpected keyword" in text:
                    driving = client.plan_segment_sync(request_points)
                else:
                    raise
        elif hasattr(client, "driving_eta_sync"):
            driving = client.driving_eta_sync([request_points[0], request_points[-1]])
        else:
            driving = {"ok": False, "reason": "missing_plan_segment_sync"}
        if isinstance(driving, dict) and driving.get("ok") and len(driving.get("polyline") or []) >= 2:
            grasped = copy.deepcopy(segment)
            grasped["points"] = copy.deepcopy(driving["polyline"])
            grasped["source"] = "driving_plan"
            grasped["duration_sec"] = driving.get("duration_sec")
            grasped["distance_m"] = driving.get("distance_m") or CoreDispatcher._path_distance_m(grasped["points"])
            grasped["traffic_status"] = driving.get("traffic_status")
            grasped["grasp"] = {
                "ok": True,
                "provider": "amap_driving",
                "strategy": driving.get("strategy"),
                "distance_m": grasped["distance_m"],
                "duration_sec": driving.get("duration_sec"),
                "traffic_status": driving.get("traffic_status"),
                "request_points": len(request_points),
                "request_point_source": "order_original_coord" if segment.get("amap_request_points") else "astar_path",
                "waypoint_count": driving.get("waypoint_count", 0),
                "cached": driving.get("cached"),
                "error": None,
            }
            return {"ok": True, "segment": grasped}

        reason = "driving_plan_failed"
        if isinstance(driving, dict):
            reason = driving.get("error") or driving.get("reason") or driving.get("info") or reason
        return {"ok": False, "reason": reason, "segment": segment}

    @staticmethod
    def _run_route_grasp_job(client, job):
        """锁外执行单车路线驾车规划任务。

        Args:
            client (AmapDrivingRoutePlanner): 高德驾车规划客户端。
            job (dict): _route_grasp_job_from_vehicle 构造出的任务快照。

        Returns:
            dict: 单车规划结果；成功时包含分段规划路线和拼接后的完整路线。
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
        restriction_policy = copy.deepcopy(job.get("restriction_policy"))
        for segment in job["segments"]:
            try:
                # 单个分段失败不立即抛出，统一收集错误并返回给车辆状态。
                previous_grasped_segment = grasped_segments[-1] if grasped_segments else None
                result = CoreDispatcher._grasp_route_segment(
                    client,
                    segment,
                    previous_grasped_segment,
                    restriction_policy=restriction_policy,
                )
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
        """在车队中定位目标车辆，并应用驾车规划结果。

        Args:
            job (dict): 原规划任务快照。
            result (dict): _run_route_grasp_job 返回的规划结果。
            fleet (list[Vehicle] | None): 当前车队。

        Returns:
            int: 成功写回或写入错误状态返回 1；车辆不存在或版本不匹配返回 0。
        """
        target_vehicle = None
        for vehicle in fleet or []:
            if CoreDispatcher._vehicle_identity(vehicle) == job["vehicle_id"]:
                target_vehicle = vehicle
                break
        if target_vehicle is None:
            return 0
        return CoreDispatcher._apply_route_grasp_result_to_vehicle(target_vehicle, job, result, fleet=fleet)

    @staticmethod
    def _apply_route_grasp_result_to_vehicle(target_vehicle, job, result, fleet=None):
        """校验版本并把单车驾车规划结果写回车辆对象。

        Args:
            target_vehicle (Vehicle): 规划任务对应的车辆对象。
            job (dict): 原规划任务快照。
            result (dict): _run_route_grasp_job 返回的规划结果。

        Returns:
            int: 成功写回或写入错误状态返回 1；版本不匹配返回 0。

        Side Effects:
            更新车辆的已规划分段、已规划总路线、规划状态和错误信息。
        """
        if target_vehicle is None:
            return 0
        if CoreDispatcher._vehicle_identity(target_vehicle) != job["vehicle_id"]:
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
            # record_route_grasp 会同步刷新 bus_vehicle_runtime.segment_route。
            persistence.record_route_grasp(target_vehicle)
            CoreDispatcher._submit_pending_fleet_push_if_ready(target_vehicle)
            return 1

        status = result.get("status", "error") if isinstance(result, dict) else "error"
        reason = result.get("reason", status) if isinstance(result, dict) else status
        target_vehicle.planned_route_grasp_status = status
        target_vehicle.planned_route_grasp_error = reason
        persistence.record_route_grasp(target_vehicle)
        return 1

    @classmethod
    def _execute_vehicle_route_grasp_job(cls, vehicle, job, job_key):
        """在线程池中执行一次车辆路线驾车规划，并在锁内写回结果。

        Args:
            vehicle (Vehicle): 提交任务时对应的车辆对象。
            job (dict): 原规划任务快照。
            job_key (tuple): 用于去重和清理在途任务的 (vehicle_id, route_version)。

        Side Effects:
            锁外请求高德；锁内校验版本并写回车辆规划状态。
        """
        try:
            try:
                client = cls._get_route_planner()
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
        """手动刷新待驾车规划车辆路线结果。

        Args:
            fleet (list[Vehicle] | None): 当前车队。
            state_lock (RLock | None): 读取和写回车辆状态时使用的锁。
            current_timestamp (float | None): 本次手动刷新时间戳；为空时取当前系统时间。
            force (bool): 是否忽略 5 秒节流限制。
            service (object | None): 测试用高德驾车规划服务桩；为空时使用默认高德客户端。

        Returns:
            int: 本次成功写回或写入错误状态的车辆数量。

        Notes:
            运行时主链路已改为“路径更新即异步提交规划”；该函数保留给测试和人工排障使用。
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
            # 持锁阶段只复制待规划任务快照，不在锁内请求高德。
            jobs = cls._collect_route_grasp_jobs(fleet)

        if not jobs:
            return 0

        client = service or cls._get_route_planner()
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
            CoreDispatcher._vehicle_identity(vehicle),
            str(getattr(vehicle, "next_node", "")),
            f"{float(getattr(vehicle, 'progress', 0.0) or 0.0):.6f}",
        ]
        for step in getattr(vehicle, "planned_route", []):
            order = step.get("order")
            request_id = getattr(order, "request_id", "")
            parts.append(f"{step.get('type')}:{request_id}")
        return CoreDispatcher._short_route_version("eta", parts)

    @staticmethod
    def _build_vehicle_eta_job(vehicle, city_map, current_timestamp):
        """构造单车 ETA 刷新任务快照。

        算法说明:
            ETA 只读取后台规划线程已经写回的分段轨迹，不在这里重新请求高德规划。
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
                "durationSec": segment.get("duration_sec"),
                "distanceM": segment.get("distance_m"),
                "trafficStatus": segment.get("traffic_status"),
                "source": segment.get("source"),
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

        vehicle_id = CoreDispatcher._vehicle_identity(vehicle)
        return {
            "vehicle_id": vehicle_id,
            "route_version": route_version,
            "order_ids": order_ids,
            "is_idle": is_idle,
            "payload": {
                "vehicleId": vehicle_id,
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

    @classmethod
    def _eta_refresh_worker_count(cls, job_count):
        """读取 ETA 刷新并发数，保证单轮尽快覆盖全部车辆任务。"""
        if job_count <= 0:
            return 0
        raw_value = os.getenv("BUS_ETA_REFRESH_MAX_WORKERS") or os.getenv("ETA_REFRESH_MAX_WORKERS")
        try:
            configured = int(raw_value) if raw_value is not None else int(cls.ETA_REFRESH_MAX_WORKERS)
        except (TypeError, ValueError):
            configured = int(cls.ETA_REFRESH_MAX_WORKERS)
        return max(1, min(job_count, configured))

    @staticmethod
    def _run_eta_refresh_job(eta_client, job, current_timestamp):
        """锁外执行单车 ETA pipeline，供串行和并发刷新路径复用。"""
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
        return job, result

    @staticmethod
    def _route_waiting_eta_status(vehicle):
        """把车辆路线规划状态映射成订单 ETA 等待状态。"""
        route_status = getattr(vehicle, "planned_route_grasp_status", None)
        route_error = getattr(vehicle, "planned_route_grasp_error", None)
        if route_status == "ready":
            return None, None
        if route_status == "disabled":
            return "disabled", "route_planning_disabled"
        if route_status == "error":
            return "route_error", route_error or "route_planning_error"
        if route_status == "stale":
            return "loading", route_error or "route_planning_stale"
        return "loading", route_error or "route_planning_pending"

    @classmethod
    def _mark_eta_waiting_for_unready_routes(cls, fleet, updated_at):
        """路线尚未规划完成时，把相关订单/空车热点 ETA 状态写成 loading 并落库。

        Notes:
            该函数只更新 eta_status/eta_error/eta_updated_at，不清空上一次有效 ETA 时间。
        """
        changed = 0
        for vehicle in fleet or []:
            status, message = cls._route_waiting_eta_status(vehicle)
            if status is None:
                continue

            current_orders = cls._current_vehicle_orders(vehicle)
            for order in current_orders.values():
                cls._mark_order_eta_error(order, status, message, updated_at)
                persistence.record_order_snapshot(
                    order,
                    status=cls._order_status_for_persistence(order),
                    vehicle=vehicle,
                )
                changed += 1

            if not current_orders and getattr(vehicle, "idle_target", None):
                vehicle.idle_target_eta_status = status
                vehicle.idle_target_eta_error = message
                persistence.record_eta_result(vehicle)
                changed += 1
        return changed

    @staticmethod
    def _apply_vehicle_eta_result(job, result, updated_at, fleet):
        """校验路线版本并把单车 ETA 结果写回订单。"""
        target_vehicle = None
        for vehicle in fleet or []:
            if CoreDispatcher._vehicle_identity(vehicle) == job["vehicle_id"]:
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
        """按固定间隔刷新订单 ETA，并尽量在一轮内覆盖所有可计算订单。

        并发约束:
            1. 持锁阶段只采集车辆/订单/路线快照。
            2. ETA pipeline 在锁外按车辆并发执行，避免阻塞派单和路径更新。
            3. 写回时再次持锁并校验 route_version，路线变更则丢弃旧结果。
        """
        current_timestamp = float(current_timestamp if current_timestamp is not None else time.time())
        lock_context = state_lock if state_lock is not None else nullcontext()

        pending_changed = 0
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
            pending_changed = cls._mark_eta_waiting_for_unready_routes(fleet, current_timestamp)
            jobs = cls._collect_eta_refresh_jobs(fleet, city_map, current_timestamp)

        if not jobs:
            return pending_changed

        eta_client = service or cls._get_eta_service()
        worker_count = cls._eta_refresh_worker_count(len(jobs))
        if worker_count <= 1:
            results = [
                cls._run_eta_refresh_job(eta_client, job, current_timestamp)
                for job in jobs
            ]
        else:
            results = []
            with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="OrderEtaRefreshWorker") as executor:
                futures = [
                    executor.submit(cls._run_eta_refresh_job, eta_client, job, current_timestamp)
                    for job in jobs
                ]
                for future in as_completed(futures):
                    results.append(future.result())

        changed = pending_changed
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
