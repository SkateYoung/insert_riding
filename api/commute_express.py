# -*- coding: utf-8 -*-
"""通勤快线独立业务模块。

该模块只负责固定站点快线的车辆匹配和订单状态推进。快线线路的站点来自
map_poi，线路顺序由创建线路时 stops 数组的经纬度顺序决定；本模块不生成
A* 路线、不请求高德驾车规划，也不向动态巴士订单池插入任务。
"""

from datetime import datetime
from types import SimpleNamespace

from . import fleet_push, persistence
from .auxiliary import AuxiliaryFunctions
from .models import SPEED_MPS


COMMUTE_FIXED_WAITING = "commute_fixed_waiting"
COMMUTE_CRUISING = "commute_cruising"
COMMUTE_OPERATION_MODES = {COMMUTE_FIXED_WAITING, COMMUTE_CRUISING}


class CommuteExpressError(ValueError):
    """通勤快线业务错误，用于路由层转换为稳定 HTTP 响应。"""

    def __init__(self, message, code="commute_error", status_code=400, field=None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.field = field


class CommuteExpressService:
    """通勤快线核心服务。

    该服务只做固定站点顺序上的候选车辆选择。车辆是否真正行驶、GPS 如何推进，
    由外部定位上报负责；快线车辆的 GPS 上报不会触发动态巴士的道路吸附和路线裁剪。
    """

    ROUTE_HEAD_LOCK_DISTANCE_M = 300.0
    ROUTE_HEAD_LOCK_ETA_SECONDS = 120.0

    @staticmethod
    def _int(value, field_name, required=True):
        if value in (None, ""):
            if required:
                raise CommuteExpressError(f"{field_name} 不能为空", code=f"{field_name}_required", field=field_name)
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise CommuteExpressError(f"{field_name} 必须是整数", code=f"{field_name}_invalid", field=field_name) from exc

    @staticmethod
    def _int_or_none(value):
        """把可选值转换为整数，转换失败时返回 None。"""
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float(value, field_name, required=True):
        if value in (None, ""):
            if required:
                raise CommuteExpressError(f"{field_name} 不能为空", code=f"{field_name}_required", field=field_name)
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise CommuteExpressError(f"{field_name} 必须是数字", code=f"{field_name}_invalid", field=field_name) from exc

    @staticmethod
    def _vehicle_id(vehicle):
        """读取运行态车辆的业务编号。"""
        return str(getattr(vehicle, "vehicle_id", None) or getattr(vehicle, "id", "") or "")

    @staticmethod
    def _runtime_vehicle_by_id(fleet, vehicle_id):
        """从指定车队中按车辆业务编号查找车辆。"""
        vehicle_id = str(vehicle_id or "").strip()
        if not vehicle_id:
            return None
        for vehicle in fleet or []:
            if CommuteExpressService._vehicle_id(vehicle) == vehicle_id:
                return vehicle
        return None

    @staticmethod
    def _coord_key(lon, lat):
        """按数据库 DECIMAL(11,8)/(10,8) 精度生成经纬度匹配键。"""
        return (round(float(lon), 8), round(float(lat), 8))

    @classmethod
    def _payload_coord(cls, payload, prefix):
        """读取形如 origin_lon/origin_lat 的坐标字段。"""
        lon = payload.get(f"{prefix}_lon", payload.get(f"{prefix}_lng", payload.get(f"{prefix}_longitude")))
        lat = payload.get(f"{prefix}_lat", payload.get(f"{prefix}_latitude"))
        return cls._float(lon, f"{prefix}_lon"), cls._float(lat, f"{prefix}_lat")

    @staticmethod
    def _station_distance_m(a, b):
        """计算两个站点快照之间的直线距离。"""
        return AuxiliaryFunctions.haversine_distance(
            float(a["lon"]),
            float(a["lat"]),
            float(b["lon"]),
            float(b["lat"]),
        )

    @staticmethod
    def _stop_id(stop):
        """读取线路站点的 map_poi 主键。"""
        return int(stop["poi_id"])

    @classmethod
    def _stop_by_poi_id(cls, stops):
        return {cls._stop_id(stop): stop for stop in stops or []}

    @classmethod
    def _line_sequence_between(cls, stops, start_poi_id, end_poi_id):
        """按 stops 数组顺序生成从起点 POI 到终点 POI 的单向循环站点序列。"""
        ordered = list(stops or [])
        if not ordered:
            return []
        poi_ids = [cls._stop_id(stop) for stop in ordered]
        if int(start_poi_id) not in poi_ids or int(end_poi_id) not in poi_ids:
            return []
        index = poi_ids.index(int(start_poi_id))
        result = []
        while True:
            result.append(ordered[index])
            if poi_ids[index] == int(end_poi_id):
                break
            index = (index + 1) % len(ordered)
            if len(result) > len(ordered) + 1:
                break
        return result

    @classmethod
    def _loop_distance_between(cls, stops, start_poi_id, end_poi_id):
        """计算沿固定站点顺序从一个 POI 到另一个 POI 的近似距离。"""
        sequence = cls._line_sequence_between(stops, start_poi_id, end_poi_id)
        if len(sequence) <= 1:
            return 0.0
        return sum(cls._station_distance_m(sequence[index - 1], sequence[index]) for index in range(1, len(sequence)))

    @classmethod
    def _line_stop_by_coordinate(cls, stops, lon, lat, field_name):
        """按经纬度从当前线路站点中查找一个站点。"""
        coord_key = cls._coord_key(lon, lat)
        matches = [
            stop for stop in stops or []
            if cls._coord_key(stop.get("lon"), stop.get("lat")) == coord_key
        ]
        if not matches:
            raise CommuteExpressError(
                f"{field_name} 不在线路站点中",
                code="commute_stop_not_in_line",
                status_code=404,
                field=field_name,
            )
        if len(matches) > 1:
            raise CommuteExpressError(
                f"{field_name} 在线路中匹配到多个站点",
                code="commute_stop_coordinate_ambiguous",
                status_code=409,
                field=field_name,
            )
        return matches[0]

    @classmethod
    def _gps_distance_to_stop(cls, vehicle, stop):
        """计算车辆 GPS 到线路站点的直线距离；车辆无 GPS 时返回 None。"""
        gps = getattr(vehicle, "gps", {}) or {}
        if gps.get("lon") is None or gps.get("lat") is None:
            return None
        try:
            return AuxiliaryFunctions.haversine_distance(
                float(gps["lon"]),
                float(gps["lat"]),
                float(stop["lon"]),
                float(stop["lat"]),
            )
        except (TypeError, ValueError):
            return None

    @classmethod
    def _step_target_poi_id(cls, step):
        """读取快线服务步骤对应的目标 POI。"""
        if not isinstance(step, dict):
            return None
        order = step.get("order")
        if order is None:
            return None
        if step.get("type") == "O":
            return getattr(order, "commute_origin_poi_id", None)
        if step.get("type") == "D":
            return getattr(order, "commute_destination_poi_id", None)
        return None

    @staticmethod
    def _step_passenger_count(step):
        """读取快线服务步骤对应的乘客人数。"""
        order = step.get("order") if isinstance(step, dict) else None
        return int(getattr(order, "passenger_count", 1) or 1)

    @classmethod
    def _route_distance_for_steps(cls, vehicle, stops, steps):
        """估算车辆按给定服务步骤行驶的线路距离。"""
        if not steps:
            return 0.0
        stop_by_id = cls._stop_by_poi_id(stops)
        first_poi_id = cls._step_target_poi_id(steps[0])
        first_stop = stop_by_id.get(int(first_poi_id)) if first_poi_id is not None else None
        if first_stop is None:
            return None
        distance = cls._gps_distance_to_stop(vehicle, first_stop)
        if distance is None:
            return None
        previous_poi_id = int(first_poi_id)
        for step in steps[1:]:
            poi_id = cls._step_target_poi_id(step)
            if poi_id is None or int(poi_id) not in stop_by_id:
                return None
            distance += cls._loop_distance_between(stops, previous_poi_id, int(poi_id))
            previous_poi_id = int(poi_id)
        return distance

    @classmethod
    def _route_capacity_feasible(cls, vehicle, steps, capacity):
        """校验服务步骤执行过程中是否超载或出现未上车先下车。"""
        load = 0
        picked_request_ids = set()
        for order in getattr(vehicle, "on_board_orders", []) or []:
            request_id = str(getattr(order, "request_id", "") or "")
            if not request_id:
                continue
            load += int(getattr(order, "passenger_count", 1) or 1)
            picked_request_ids.add(request_id)
        for step in steps:
            order = step.get("order") if isinstance(step, dict) else None
            request_id = str(getattr(order, "request_id", "") or "")
            if not request_id:
                return False
            if getattr(order, "status", None) == "riding" and request_id not in picked_request_ids:
                load += int(getattr(order, "passenger_count", 1) or 1)
                picked_request_ids.add(request_id)

        if load > capacity:
            return False
        for step in steps:
            order = step.get("order")
            request_id = str(getattr(order, "request_id", "") or "")
            count = cls._step_passenger_count(step)
            if step.get("type") == "O":
                load += count
                picked_request_ids.add(request_id)
            elif step.get("type") == "D":
                if request_id not in picked_request_ids:
                    return False
                load -= count
            else:
                return False
            if load < 0 or load > capacity:
                return False
        return True

    @classmethod
    def _route_head_locked(cls, vehicle):
        """判断快线车辆当前队首是否进入执行保护窗口。"""
        steps = getattr(vehicle, "planned_route", []) or []
        if not steps:
            return False
        head = steps[0]
        order = head.get("order") if isinstance(head, dict) else None
        if order is None:
            return False
        target = getattr(order, "o_node", None) if head.get("type") == "O" else getattr(order, "d_node", None)
        gps = getattr(vehicle, "gps", None) or {}
        if target is None or gps.get("lon") is None or gps.get("lat") is None:
            return False
        try:
            distance_m = AuxiliaryFunctions.haversine_distance(
                float(gps.get("lon")),
                float(gps.get("lat")),
                float(target.lon),
                float(target.lat),
            )
        except (TypeError, ValueError):
            return False
        eta_seconds = distance_m / SPEED_MPS if SPEED_MPS > 0 else float("inf")
        return (
            distance_m <= cls.ROUTE_HEAD_LOCK_DISTANCE_M
            or eta_seconds <= cls.ROUTE_HEAD_LOCK_ETA_SECONDS
        )

    @classmethod
    def _best_local_insertion_plan(cls, vehicle, stops, order_obj):
        """局部插入新订单 O/D，保持车辆已有服务步骤相对顺序不变。"""
        existing_steps = list(getattr(vehicle, "planned_route", []) or [])
        capacity = int(getattr(vehicle, "capacity", 0) or 0)
        if capacity <= 0:
            return None
        min_origin_index = 1 if cls._route_head_locked(vehicle) and existing_steps else 0
        baseline_distance = cls._route_distance_for_steps(vehicle, stops, existing_steps)
        if baseline_distance is None:
            baseline_distance = 0.0 if not existing_steps else None
        if baseline_distance is None:
            return None

        origin_step = {"type": "O", "order": order_obj}
        destination_step = {"type": "D", "order": order_obj}
        best = None
        for origin_index in range(min_origin_index, len(existing_steps) + 1):
            with_origin = existing_steps[:origin_index] + [origin_step] + existing_steps[origin_index:]
            for destination_index in range(origin_index + 1, len(with_origin) + 1):
                candidate_steps = (
                    with_origin[:destination_index]
                    + [destination_step]
                    + with_origin[destination_index:]
                )
                if not cls._route_capacity_feasible(vehicle, candidate_steps, capacity):
                    continue
                total_distance = cls._route_distance_for_steps(vehicle, stops, candidate_steps)
                if total_distance is None:
                    continue
                extra_distance = max(0.0, total_distance - baseline_distance)
                plan = {
                    "planned_route": candidate_steps,
                    "origin_index": origin_index,
                    "destination_index": destination_index,
                    "total_distance_m": total_distance,
                    "extra_distance_m": extra_distance,
                }
                if best is None or (
                    extra_distance,
                    origin_index,
                    destination_index,
                ) < (
                    best["extra_distance_m"],
                    best["origin_index"],
                    best["destination_index"],
                ):
                    best = plan
        return best

    @classmethod
    def _commute_route_version(cls, vehicle):
        """生成快线服务队列版本，用于平台识别单车导航快照。"""
        parts = []
        for step in getattr(vehicle, "planned_route", []) or []:
            order = step.get("order") if isinstance(step, dict) else None
            parts.append(
                f"{step.get('type')}:{getattr(order, 'request_id', '')}:"
                f"{cls._step_target_poi_id(step) or ''}:{getattr(order, 'status', '')}"
            )
        return f"commute:{cls._vehicle_id(vehicle)}:{'|'.join(parts) or 'empty'}"

    @classmethod
    def _submit_vehicle_commute_push(cls, vehicle, event_reason, request_id=None):
        """快线服务队列变化后，把单车快照推送给平台。"""
        if vehicle is None:
            return False
        vehicle.commute_route_version = cls._commute_route_version(vehicle)
        return fleet_push.submit_vehicle_navigation(vehicle, {
            "event_type": "fleet_route_changed",
            "event_reason": event_reason,
            "vehicle_id": cls._vehicle_id(vehicle),
            "request_id": request_id,
            "route_version": getattr(vehicle, "commute_route_version", None),
        })

    @classmethod
    def _candidate_distance_to_origin(cls, vehicle, assignment, stops, origin_poi_id):
        """计算候选车辆 GPS 到订单上车站的直线距离。"""
        stop = cls._stop_by_poi_id(stops).get(int(origin_poi_id))
        if stop is None:
            return None
        return cls._gps_distance_to_stop(vehicle, stop)

    @classmethod
    def _find_candidate_vehicle(cls, line, stops, order_payload, fleet):
        """查找最适合承接快线订单的车辆。"""
        assignments = [
            item for item in persistence.list_commute_vehicle_assignments(line.get("line_code"))
            if item.get("status") == "active"
        ]
        best = None
        origin_poi_id = int(order_payload["origin_poi_id"])
        origin_stop = cls._stop_by_poi_id(stops).get(origin_poi_id)
        destination_stop = cls._stop_by_poi_id(stops).get(int(order_payload["destination_poi_id"]))
        if origin_stop is None or destination_stop is None:
            return None
        order_obj = cls._commute_order_object(
            {**order_payload, "status": "waiting_pickup"},
            origin_stop,
            destination_stop,
        )
        passenger_count = int(order_payload.get("passenger_count") or 1)
        for assignment in assignments:
            vehicle = cls._runtime_vehicle_by_id(fleet, assignment.get("vehicle_code"))
            if vehicle is None:
                continue
            if cls._int_or_none(getattr(vehicle, "operation_area_id", None)) != cls._int_or_none(line.get("operation_area_id")):
                continue
            if str(getattr(vehicle, "operation_mode", "") or "") not in COMMUTE_OPERATION_MODES:
                continue
            if getattr(vehicle, "rest_status", "operating") != "operating":
                continue
            if passenger_count > int(getattr(vehicle, "capacity", 0) or 0):
                continue
            distance = cls._candidate_distance_to_origin(vehicle, assignment, stops, origin_poi_id)
            if distance is None:
                continue
            insertion_plan = cls._best_local_insertion_plan(vehicle, stops, order_obj)
            if insertion_plan is None:
                continue
            candidate = {
                "vehicle": vehicle,
                "assignment": assignment,
                "distance_to_origin_m": distance,
                "insertion_plan": insertion_plan,
                "order_obj": order_obj,
            }
            if best is None or (
                distance,
                insertion_plan["extra_distance_m"],
            ) < (
                best["distance_to_origin_m"],
                best["insertion_plan"]["extra_distance_m"],
            ):
                best = candidate
        return best

    @staticmethod
    def _node_like_from_stop(stop):
        """把 POI 快照转换成兼容上下客距离校验的轻量节点对象。"""
        return SimpleNamespace(
            id=stop.get("poi_code") or str(stop.get("poi_id")),
            poi_id=stop.get("poi_id"),
            poi_code=stop.get("poi_code"),
            name=stop.get("station_name") or stop.get("poi_name") or stop.get("poi_code"),
            lon=float(stop["lon"]),
            lat=float(stop["lat"]),
            zone=stop.get("zone"),
        )

    @classmethod
    def _commute_order_object(cls, order_record, origin_stop, destination_stop):
        """把 bus_order 快线记录转换成车辆计划队列中的轻量订单对象。"""
        return SimpleNamespace(
            request_id=order_record["request_id"],
            passenger_count=int(order_record.get("passenger_count") or 1),
            passenger_phone=order_record.get("passenger_phone"),
            passenger_id=order_record.get("passenger_id"),
            status=order_record.get("status") or "waiting_pickup",
            order_source="commute_express",
            operation_area_id=order_record.get("operation_area_id"),
            line_code=order_record.get("line_code"),
            commute_order=True,
            commute_origin_poi_id=int(order_record["origin_poi_id"]),
            commute_destination_poi_id=int(order_record["destination_poi_id"]),
            route_poi_sequence=list(order_record.get("route_poi_sequence") or []),
            o_node=cls._node_like_from_stop(origin_stop),
            d_node=cls._node_like_from_stop(destination_stop),
            o_lon=float(origin_stop["lon"]),
            o_lat=float(origin_stop["lat"]),
            d_lon=float(destination_stop["lon"]),
            d_lat=float(destination_stop["lat"]),
            actual_pick_time=None,
            completion_time=None,
        )

    @classmethod
    def _mark_vehicle_commute_runtime(cls, vehicle, assignment):
        """标记车辆处于快线业务，并仅刷新运行态，不生成路线。"""
        vehicle.commute_express_active = True
        vehicle.commute_line_code = assignment.get("line_code")
        vehicle.operation_mode = assignment.get("task_mode") or getattr(vehicle, "operation_mode", None)
        vehicle.planned_route_point = []
        vehicle.planned_route_segment_raw_point = []
        vehicle.planned_route_segment_grasped_point = []
        vehicle.planned_route_grasped_point = []
        vehicle.planned_route_grasp_status = None
        vehicle.planned_route_grasp_error = None
        vehicle.commute_route_version = cls._commute_route_version(vehicle)
        persistence.record_vehicle_runtime(vehicle)

    @classmethod
    def create_order(cls, payload, fleet, city_map=None, request_time=None):
        """创建通勤快线订单并尝试匹配车辆。"""
        request_id = str(payload.get("request_id") or "").strip()
        line_code = str(payload.get("line_code") or "").strip()
        passenger_phone = str(payload.get("passenger_phone") or "").strip()
        if not request_id:
            raise CommuteExpressError("request_id 不能为空", code="request_id_required", field="request_id")
        if not line_code:
            raise CommuteExpressError("line_code 不能为空", code="line_code_required", field="line_code")
        if not passenger_phone:
            raise CommuteExpressError("passenger_phone 不能为空", code="passenger_phone_required", field="passenger_phone")
        passenger_count = cls._int(payload.get("passenger_count", 1), "passenger_count")
        origin_lon, origin_lat = cls._payload_coord(payload, "origin")
        destination_lon, destination_lat = cls._payload_coord(payload, "destination")

        line = persistence.get_commute_line(line_code, with_stops=True)
        if not line or line.get("status") != "enabled":
            raise CommuteExpressError("通勤快线线路不存在或未启用", code="commute_line_not_found", status_code=404)
        stops = line.get("stops") or []
        origin_stop = cls._line_stop_by_coordinate(stops, origin_lon, origin_lat, "origin")
        destination_stop = cls._line_stop_by_coordinate(stops, destination_lon, destination_lat, "destination")
        if cls._stop_id(origin_stop) == cls._stop_id(destination_stop):
            raise CommuteExpressError("上下车站点不能相同", code="same_origin_destination", status_code=409)
        route_poi_sequence = [
            cls._stop_id(stop)
            for stop in cls._line_sequence_between(stops, cls._stop_id(origin_stop), cls._stop_id(destination_stop))
        ]
        now = request_time or datetime.now().replace(microsecond=0)
        order_record = {
            "request_id": request_id,
            "line_code": line_code,
            "operation_area_id": line.get("operation_area_id"),
            "origin_poi_id": cls._stop_id(origin_stop),
            "destination_poi_id": cls._stop_id(destination_stop),
            "origin_poi_code": origin_stop.get("poi_code"),
            "destination_poi_code": destination_stop.get("poi_code"),
            "origin_station_name": origin_stop.get("station_name"),
            "destination_station_name": destination_stop.get("station_name"),
            "origin_lon": origin_stop.get("lon"),
            "origin_lat": origin_stop.get("lat"),
            "destination_lon": destination_stop.get("lon"),
            "destination_lat": destination_stop.get("lat"),
            "passenger_phone": passenger_phone,
            "passenger_id": str(payload.get("passenger_id") or "").strip() or None,
            "passenger_count": passenger_count,
            "status": "pooled",
            "order_source": "commute_express",
            "route_poi_sequence": route_poi_sequence,
            "request_time": now,
        }
        persistence.save_commute_order(order_record, create=True)
        candidate = cls._find_candidate_vehicle(line, stops, order_record, fleet)
        if candidate is None:
            return {"status": "pooled", "order": persistence.get_commute_order(request_id), "candidate": None}

        vehicle = candidate["vehicle"]
        assignment = candidate["assignment"]
        order_record["status"] = "waiting_pickup"
        order_record["assigned_vehicle_code"] = cls._vehicle_id(vehicle)
        order_record["assigned_plate_no"] = getattr(vehicle, "plate_no", None)
        vehicle.planned_route = candidate["insertion_plan"]["planned_route"]
        cls._mark_vehicle_commute_runtime(vehicle, assignment)
        persistence.save_commute_order(order_record, create=False)
        event_reason = "commute_order_assigned" if len(vehicle.planned_route) == 2 else "commute_order_inserted"
        cls._submit_vehicle_commute_push(vehicle, event_reason, request_id)
        return {
            "status": "waiting_pickup",
            "order": persistence.get_commute_order(request_id),
            "candidate": {
                "vehicle_id": cls._vehicle_id(vehicle),
                "vehicle_code": cls._vehicle_id(vehicle),
                "plate_no": getattr(vehicle, "plate_no", None),
                "distance_to_origin_m": candidate["distance_to_origin_m"],
                "extra_distance_m": candidate["insertion_plan"]["extra_distance_m"],
                "origin_insert_index": candidate["insertion_plan"]["origin_index"],
                "destination_insert_index": candidate["insertion_plan"]["destination_index"],
                "task_mode": assignment.get("task_mode"),
            },
            "vehicle": vehicle,
        }

    @classmethod
    def cancel_order(cls, request_id, fleet, city_map=None):
        """取消通勤快线订单，并从车辆剩余服务步骤中移除。"""
        order = persistence.get_commute_order(request_id)
        if not order:
            raise CommuteExpressError("通勤快线订单不存在", code="commute_order_not_found", status_code=404)
        if order.get("status") in {"completed", "cancelled"}:
            return {"status": order.get("status"), "order": order}
        vehicle = cls._runtime_vehicle_by_id(fleet, order.get("assigned_vehicle_code"))
        if vehicle is not None:
            planned_route = list(getattr(vehicle, "planned_route", []) or [])
            vehicle.planned_route = [
                step for step in planned_route
                if str(getattr(step.get("order"), "request_id", "")) != str(request_id)
            ]
            vehicle.on_board_orders = [
                item for item in getattr(vehicle, "on_board_orders", []) or []
                if str(getattr(item, "request_id", "")) != str(request_id)
            ]
            vehicle.commute_route_version = cls._commute_route_version(vehicle)
            persistence.record_vehicle_runtime(vehicle)
            cls._submit_vehicle_commute_push(vehicle, "commute_order_cancelled", request_id)
        order["status"] = "cancelled"
        order["cancel_time"] = datetime.now().replace(microsecond=0)
        order["cancel_reason"] = "passenger_cancelled"
        persistence.save_commute_order(order, create=False)
        return {"status": "cancelled", "order": persistence.get_commute_order(request_id)}

    @classmethod
    def confirm_boarding_event(
        cls,
        vehicle,
        action,
        request_id=None,
        lon=None,
        lat=None,
        distance_threshold_m=30.0,
        city_map=None,
    ):
        """确认快线车辆当前上下客步骤。

        distance_threshold_m 仅用于兼容旧请求体，当前不再按距离拦截确认。
        """
        action = str(action or "").strip().lower()
        if action not in {"pickup", "dropoff"}:
            raise CommuteExpressError("action 必须是 pickup 或 dropoff", code="invalid_action")
        if not getattr(vehicle, "planned_route", None):
            raise CommuteExpressError("车辆当前没有待确认步骤", code="no_commute_step", status_code=409)
        step = vehicle.planned_route[0]
        expected_action = "pickup" if step.get("type") == "O" else "dropoff"
        if action != expected_action:
            raise CommuteExpressError(f"当前步骤需要 {expected_action}", code="invalid_step_action", status_code=409)
        order = step.get("order")
        if request_id not in (None, "") and str(request_id) != str(order.request_id):
            raise CommuteExpressError("request_id 不是当前下一步订单", code="request_id_not_current", status_code=409)
        target_node = order.o_node if step.get("type") == "O" else order.d_node
        gps = getattr(vehicle, "gps", {}) or {}
        check_lon = gps.get("lon") if lon is None else lon
        check_lat = gps.get("lat") if lat is None else lat
        if check_lon is None or check_lat is None:
            raise CommuteExpressError("车辆当前位置为空", code="vehicle_position_missing")
        try:
            check_lon = float(check_lon)
            check_lat = float(check_lat)
        except (TypeError, ValueError):
            raise CommuteExpressError("车辆当前位置必须是数字", code="vehicle_position_invalid")
        distance = AuxiliaryFunctions.haversine_distance(check_lon, check_lat, target_node.lon, target_node.lat)

        vehicle.planned_route.pop(0)
        order_record = persistence.get_commute_order(order.request_id) or {"request_id": order.request_id}
        if action == "pickup":
            order.status = "riding"
            if all(getattr(item, "request_id", None) != order.request_id for item in getattr(vehicle, "on_board_orders", []) or []):
                vehicle.on_board_orders.append(order)
            order_record["status"] = "riding"
            order_record["actual_pickup_time"] = datetime.now().replace(microsecond=0)
        else:
            order.status = "completed"
            vehicle.on_board_orders = [
                item for item in getattr(vehicle, "on_board_orders", []) or []
                if getattr(item, "request_id", None) != order.request_id
            ]
            order_record["status"] = "completed"
            order_record["completion_time"] = datetime.now().replace(microsecond=0)
        persistence.save_commute_order(order_record, create=False)
        vehicle.commute_route_version = cls._commute_route_version(vehicle)
        persistence.record_vehicle_runtime(vehicle)
        cls._submit_vehicle_commute_push(vehicle, "commute_boarding_updated", order.request_id)
        return {
            "status": order_record["status"],
            "event": {
                "action": action,
                "request_id": order.request_id,
                "distance_to_target": distance,
                "target_node": {
                    "id": target_node.id,
                    "poi_id": getattr(target_node, "poi_id", None),
                    "lon": target_node.lon,
                    "lat": target_node.lat,
                    "name": target_node.name,
                },
            },
            "planned_route": [
                {
                    "type": item.get("type"),
                    "request_id": getattr(item.get("order"), "request_id", None),
                    "target_poi_id": cls._step_target_poi_id(item),
                }
                for item in getattr(vehicle, "planned_route", []) or []
            ],
            "planned_route_size": len(vehicle.planned_route),
        }
