# -*- coding: utf-8 -*-
"""MySQL 异步持久化层。

本模块只负责把内存调度系统中的运行快照镜像写入 MySQL，不反向参与派单、
路径重建、ETA、纠偏等核心算法决策。所有 record_* 入口均为 best-effort：
当 BUS_DB_ENABLED 未开启、PyMySQL 缺失、数据库断连或 SQL 异常时，错误只会
留在后台写库线程状态中，不会向业务主流程继续抛出。
"""

import copy
import json
import os
import queue
import threading
import time
from datetime import datetime

try:
    import pymysql
except ImportError:  # pragma: no cover - depends on deployment environment.
    pymysql = None

try:
    from .models import SPEED_MPS
except Exception:  # pragma: no cover - keeps module importable in isolation.
    SPEED_MPS = 16.6666666667


DEFAULT_QUEUE_SIZE = 10000
DEFAULT_TENANT_ID = "000000"


# ============================================================
# 功能一：持久化配置、时间转换与业务快照辅助函数
# 相关方法：_env_enabled、_json、_route_version、_order_payload
# ============================================================

def _env_enabled(value):
    """解析环境变量中的布尔开关。

    Args:
        value (Any): 环境变量原始值。

    Returns:
        bool: 是否表示开启。
    """
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _now_dt():
    """生成数据库使用的本地时间，精度统一到秒。"""
    return datetime.now().replace(microsecond=0)


def _to_datetime(value):
    """把时间戳或 datetime 转换为 MySQL datetime 可写入值。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value)).replace(microsecond=0)
    return value


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value)


def _json(value):
    """把 Python 对象稳定序列化为 JSON 字符串。"""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=_json_default)


def _float_or_none(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _point_from_node(node):
    if node is None:
        return None
    return {
        "id": getattr(node, "id", None),
        "lon": getattr(node, "lon", None),
        "lat": getattr(node, "lat", None),
        "name": getattr(node, "name", None),
        "zone": getattr(node, "zone", None),
    }


def _point_from_mapping(point):
    if not isinstance(point, dict):
        return None
    return {
        "id": point.get("id"),
        "lon": point.get("lon"),
        "lat": point.get("lat"),
        "name": point.get("name"),
        "zone": point.get("zone"),
    }


def _node_path_points(path):
    return [_point_from_node(node) for node in path or []]


def _vehicle_code(vehicle):
    return str(
        getattr(vehicle, "vehicle_id", None)
        or getattr(vehicle, "id", None)
        or ""
    )


def _driver_code(vehicle):
    return str(
        getattr(vehicle, "driver_id", None)
        or getattr(vehicle, "driver_no", None)
        or f"driver:{getattr(vehicle, 'id', '')}"
    )


def _route_version(vehicle):
    """生成车辆当前路线版本签名。

    优先使用车辆纠偏流程写入的版本号；没有版本号时，按车辆 ID、O/D 停靠序列
    或 IDLE 热点目标兜底生成，供路线快照、分段和订单路线关联使用。

    Args:
        vehicle (Vehicle): 车辆运行对象。

    Returns:
        str: 当前车辆路线版本。
    """
    version = getattr(vehicle, "planned_route_grasp_route_version", None)
    if version:
        return str(version)
    parts = [str(getattr(vehicle, "id", ""))]
    for step in getattr(vehicle, "planned_route", []) or []:
        order = step.get("order")
        parts.append(f"{step.get('type')}:{getattr(order, 'request_id', '')}")
    idle_target = getattr(vehicle, "idle_target", None)
    if idle_target and not getattr(vehicle, "planned_route", None):
        parts.append(f"IDLE:{idle_target.get('node_id')}:{idle_target.get('generated_at')}")
    if len(parts) == 1:
        parts.append("EMPTY")
    return "|".join(parts)


def _operation_status(vehicle):
    rest_status = getattr(vehicle, "rest_status", None)
    if rest_status == "resting":
        return "resting"
    if rest_status in {"closing", "preparing_closure"}:
        return "closing"
    if getattr(vehicle, "planned_route", None) or getattr(vehicle, "on_board_orders", None):
        return "serving"
    if getattr(vehicle, "idle_target", None):
        return "idle"
    return "idle"


def _order_status(order, default="pooled"):
    status = getattr(order, "status", None)
    if status:
        return str(status)
    return default


def _order_route_snapshot(order, city_map):
    """为新建订单计算 O 到 D 的本地 A* 原始路线快照。

    Args:
        order (Order): 订单对象。
        city_map (CityGraph): 当前路网对象。

    Returns:
        dict: 可直接合入 bus_order 的路线字段。
    """
    if order is None or city_map is None:
        return {}
    o_node = getattr(order, "o_node", None)
    d_node = getattr(order, "d_node", None)
    if o_node is None or d_node is None:
        return {}
    try:
        distance, path = city_map.get_path(o_node, d_node)
    except Exception:
        return {"route_status": "error", "route_error": "get_path_failed"}
    if distance == float("inf"):
        return {"route_status": "error", "route_error": "path_unreachable"}
    points = _node_path_points(path)
    return {
        "route_status": "ready",
        "route_distance_m": float(distance),
        "route_duration_s": int(float(distance) / SPEED_MPS) if SPEED_MPS else None,
        "raw_route_points": points,
        "route_segments": [
            {
                "type": "OD",
                "request_id": str(getattr(order, "request_id", "")),
                "distance": float(distance),
                "points": points,
            }
        ],
        "route_updated_at": _now_dt(),
    }


def _route_segments_from_vehicle(vehicle):
    """合并车辆 raw 分段与高德纠偏分段，生成数据库分段快照。

    Args:
        vehicle (Vehicle): 车辆运行对象。

    Returns:
        list[dict]: 车辆当前 O/D 或 IDLE 分段列表。
    """
    raw_segments = copy.deepcopy(getattr(vehicle, "planned_route_segment_raw_point", None) or [])
    grasped_segments = copy.deepcopy(getattr(vehicle, "planned_route_segment_grasped_point", None) or [])
    grasped_by_index = {}
    for segment in grasped_segments:
        grasped_by_index[(segment.get("index"), segment.get("type"), str(segment.get("request_id")))] = segment

    merged = []
    for index, raw in enumerate(raw_segments):
        key = (raw.get("index", index), raw.get("type"), str(raw.get("request_id")))
        grasped = grasped_by_index.get(key) or (grasped_segments[index] if index < len(grasped_segments) else None)
        merged.append({
            "index": raw.get("index", index),
            "type": raw.get("type"),
            "request_id": raw.get("request_id"),
            "target_node": raw.get("target_node"),
            "distance": raw.get("distance", raw.get("aStarDistanceM")),
            "raw_points": raw.get("points") or raw.get("path") or [],
            "grasped_points": (grasped or {}).get("points") or (grasped or {}).get("path") or [],
            "grasp": (grasped or {}).get("grasp"),
            "source": (grasped or {}).get("source"),
        })
    return merged


def _orders_in_vehicle(vehicle):
    orders = {}
    for order in getattr(vehicle, "on_board_orders", []) or []:
        orders[str(getattr(order, "request_id", ""))] = order
    for step in getattr(vehicle, "planned_route", []) or []:
        order = step.get("order")
        if order is not None:
            orders[str(getattr(order, "request_id", ""))] = order
    return orders


def _order_route_from_vehicle(vehicle, request_id):
    """从整车路线中截取某个订单 O 到 D 的订单路线。

    Args:
        vehicle (Vehicle): 车辆运行对象。
        request_id (str): 订单号。

    Returns:
        dict | None: 可写入 bus_order 的订单路线字段；没有可用分段时返回 None。
    """
    request_id = str(request_id)
    segments = _route_segments_from_vehicle(vehicle)
    if not segments:
        return None

    collecting = False
    selected = []
    has_pickup = False
    has_dropoff = False
    for segment in segments:
        segment_request_id = str(segment.get("request_id"))
        segment_type = segment.get("type")
        if segment_request_id == request_id and segment_type == "O":
            collecting = True
            has_pickup = True
        if collecting:
            selected.append(segment)
        if segment_request_id == request_id and segment_type == "D":
            has_dropoff = True
            break

    if not selected and any(str(o.request_id) == request_id for o in getattr(vehicle, "on_board_orders", []) or []):
        selected = []
        for segment in segments:
            selected.append(segment)
            if str(segment.get("request_id")) == request_id and segment.get("type") == "D":
                has_dropoff = True
                break

    if not selected:
        return None

    raw_points = []
    grasped_points = []
    distance = 0.0
    for segment in selected:
        raw_segment_points = segment.get("raw_points") or []
        grasped_segment_points = segment.get("grasped_points") or []
        if raw_points and raw_segment_points:
            raw_points.extend(copy.deepcopy(raw_segment_points[1:]))
        else:
            raw_points.extend(copy.deepcopy(raw_segment_points))
        if grasped_points and grasped_segment_points:
            grasped_points.extend(copy.deepcopy(grasped_segment_points[1:]))
        else:
            grasped_points.extend(copy.deepcopy(grasped_segment_points))
        distance += float(segment.get("distance") or 0.0)

    route_status = "ready" if has_dropoff and (raw_points or grasped_points) else "pending"
    if has_pickup and not has_dropoff:
        route_status = "pending"
    return {
        "request_id": request_id,
        "route_version": _route_version(vehicle),
        "route_status": route_status,
        "route_distance_m": distance or None,
        "route_duration_s": int(distance / SPEED_MPS) if distance and SPEED_MPS else None,
        "raw_route_points": raw_points or None,
        "grasped_route_points": grasped_points or None,
        "route_segments": selected,
        "route_updated_at": _now_dt(),
        "route_error": None,
    }


# ============================================================
# 功能二：MySQL 异步写入队列与后台 Worker
# 相关方法：MySqlPersistence.enqueue、_worker_loop、_execute_task
# ============================================================

class MySqlPersistence:
    """封装数据库连接、异步队列和 SQL 写入分发。

    业务线程只调用 enqueue 提交已经序列化好的快照；真正的 MySQL 连接与写入
    全部在后台线程中完成，从而避免数据库抖动影响派单与 GPS 更新。
    """

    def __init__(self, config=None):
        """初始化持久化管理器。

        Args:
            config (dict, optional): 数据库连接、租户和队列配置。
        """
        config = config or {}
        self.enabled = bool(config.get("enabled")) and pymysql is not None
        self.host = config.get("host") or "127.0.0.1"
        self.port = int(config.get("port") or 3306)
        self.user = config.get("user") or "root"
        self.password = config.get("password") or ""
        self.database = config.get("database") or "bus_dispatch_core"
        self.tenant_id = config.get("tenant_id") or DEFAULT_TENANT_ID
        self.queue = queue.Queue(maxsize=int(config.get("queue_size") or DEFAULT_QUEUE_SIZE))
        self.worker = None
        self.stop_event = threading.Event()
        self.last_error = None
        self.last_success_at = None
        self.dropped_tasks = 0
        self.processed_tasks = 0
        self._connection = None
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls):
        """从环境变量构造持久化管理器。

        Returns:
            MySqlPersistence: 已读取 BUS_DB_* 配置的管理器实例。
        """
        return cls({
            "enabled": _env_enabled(os.getenv("BUS_DB_ENABLED", "1")),
            "host": os.getenv("BUS_DB_HOST", "127.0.0.1"),
            "port": os.getenv("BUS_DB_PORT", "3306"),
            "user": os.getenv("BUS_DB_USER", "root"),
            "password": os.getenv("BUS_DB_PASSWORD", "021015"),
            "database": os.getenv("BUS_DB_NAME", "bus_dispatch_core"),
            "tenant_id": os.getenv("BUS_DB_TENANT_ID", DEFAULT_TENANT_ID),
            "queue_size": os.getenv("BUS_DB_QUEUE_SIZE", str(DEFAULT_QUEUE_SIZE)),
        })

    def status(self):
        """返回当前写库线程状态，供 /health 只读展示。"""
        return {
            "enabled": self.enabled,
            "available": pymysql is not None,
            "queue_size": self.queue.qsize(),
            "last_error": self.last_error,
            "last_success_at": self.last_success_at,
            "dropped_tasks": self.dropped_tasks,
            "processed_tasks": self.processed_tasks,
            "database": self.database,
            "tenant_id": self.tenant_id,
        }

    def start(self):
        """按需启动后台写库线程。

        Returns:
            bool: 线程可用或已启动返回 True；未启用数据库时返回 False。
        """
        if not self.enabled:
            return False
        with self._lock:
            if self.worker is not None and self.worker.is_alive():
                return True
            self.stop_event.clear()
            self.worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="MySqlPersistenceWriter",
            )
            self.worker.start()
        return True

    def shutdown(self, wait=False):
        """停止后台写库线程并关闭数据库连接。

        Args:
            wait (bool, optional): 是否等待线程最多 5 秒退出。
        """
        self.stop_event.set()
        if self.worker is not None:
            self.worker.join(timeout=5 if wait else 0)
        self._close_connection()

    def enqueue(self, op, payload):
        """向后台队列提交一次数据库写入任务。

        Args:
            op (str): SQL 操作名称，对应 _op_<op> 方法。
            payload (dict): 已抽取好的业务快照。

        Returns:
            bool: 成功入队返回 True；未启用或队列已满返回 False。
        """
        if not self.enabled:
            return False
        self.start()
        task = {
            "op": op,
            "tenant_id": self.tenant_id,
            # 入队前复制快照，避免后台线程读到业务对象后续变化。
            "payload": copy.deepcopy(payload or {}),
            "queued_at": time.time(),
        }
        try:
            self.queue.put_nowait(task)
            return True
        except queue.Full:
            self.dropped_tasks += 1
            self.last_error = "persistence_queue_full"
            return False

    def _worker_loop(self):
        """后台写库主循环。

        数据库异常在这里被吞掉并记录 last_error，随后关闭连接等待下一次任务重连。
        """
        while not self.stop_event.is_set():
            try:
                task = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._execute_task(task)
                self.processed_tasks += 1
                self.last_success_at = time.time()
                self.last_error = None
            except Exception as exc:  # pragma: no cover - exercised by integration.
                self.last_error = str(exc)
                self._rollback()
                self._close_connection()
            finally:
                self.queue.task_done()

    def _connect(self):
        """获取可用 MySQL 连接，断线时自动重连。"""
        if self._connection is not None:
            try:
                self._connection.ping(reconnect=True)
                return self._connection
            except Exception:
                self._close_connection()
        self._connection = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )
        return self._connection

    def _close_connection(self):
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def _rollback(self):
        if self._connection is not None:
            try:
                self._connection.rollback()
            except Exception:
                pass

    def _execute(self, cursor, sql, params=None):
        cursor.execute(sql, params or ())

    def _fetch_id(self, cursor, table, code_column, code_value, tenant_id):
        """通过业务编码查找数据库自增主键。

        数据库表之间用自增 ID 建关联，但算法侧只持有 vehicle_code、request_id、
        node_code 这类业务编码，因此写入关联表前需要做一次轻量转换。
        """
        if code_value in (None, ""):
            return None
        cursor.execute(
            f"SELECT id FROM `{table}` WHERE tenant_id=%s AND `{code_column}`=%s AND deleted=0 LIMIT 1",
            (tenant_id, str(code_value)),
        )
        row = cursor.fetchone()
        return row["id"] if row else None

    def _execute_task(self, task):
        """执行单个入队任务并提交事务。"""
        conn = self._connect()
        tenant_id = task.get("tenant_id") or self.tenant_id
        op = task["op"]
        payload = task.get("payload") or {}
        with conn.cursor() as cursor:
            handler = getattr(self, f"_op_{op}", None)
            if handler is None:
                raise ValueError(f"unknown_persistence_op:{op}")
            handler(cursor, tenant_id, payload)
        conn.commit()

    # ============================================================
    # 功能三：各业务表 SQL Upsert/Insert 处理器
    # 相关方法：_op_order、_op_vehicle_runtime、_op_route_segment
    # ============================================================

    def _op_tenant(self, cursor, tenant_id, payload):
        self._execute(cursor, """
            INSERT INTO sys_tenant (tenant_id, tenant_name, status)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE tenant_name=VALUES(tenant_name), status=VALUES(status)
        """, (
            tenant_id,
            payload.get("tenant_name") or tenant_id,
            payload.get("status") or "enabled",
        ))

    def _op_poi(self, cursor, tenant_id, payload):
        self._execute(cursor, """
            INSERT INTO map_poi
                (poi_code, poi_name, poi_type, longitude, latitude, zone, node_code, address, status, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                poi_name=VALUES(poi_name), longitude=VALUES(longitude), latitude=VALUES(latitude),
                zone=VALUES(zone), node_code=VALUES(node_code), status=VALUES(status), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            payload["poi_code"],
            payload.get("poi_name") or payload["poi_code"],
            payload.get("poi_type") or "pickup_dropoff",
            payload.get("longitude"),
            payload.get("latitude"),
            payload.get("zone"),
            payload.get("node_code"),
            payload.get("address"),
            payload.get("status") or "enabled",
            tenant_id,
        ))

    def _op_road_node(self, cursor, tenant_id, payload):
        self._execute(cursor, """
            INSERT INTO map_road_node
                (node_code, node_name, longitude, latitude, zone, is_poi, status, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                node_name=VALUES(node_name), longitude=VALUES(longitude), latitude=VALUES(latitude),
                zone=VALUES(zone), is_poi=VALUES(is_poi), status=VALUES(status), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            payload["node_code"],
            payload.get("node_name"),
            payload.get("longitude"),
            payload.get("latitude"),
            payload.get("zone"),
            1 if payload.get("is_poi") else 0,
            payload.get("status") or "enabled",
            tenant_id,
        ))

    def _op_driver(self, cursor, tenant_id, payload):
        self._execute(cursor, """
            INSERT INTO bus_driver
                (driver_code, driver_no, driver_name, phone, license_class, service_city,
                 employment_status, work_status, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                driver_no=VALUES(driver_no), driver_name=VALUES(driver_name), phone=VALUES(phone),
                work_status=VALUES(work_status), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            payload["driver_code"],
            payload.get("driver_no"),
            payload.get("driver_name") or payload.get("driver_no") or payload["driver_code"],
            payload.get("phone"),
            payload.get("license_class"),
            payload.get("service_city"),
            payload.get("employment_status") or "active",
            payload.get("work_status") or "listening",
            tenant_id,
        ))

    def _op_vehicle(self, cursor, tenant_id, payload):
        driver_id = self._fetch_id(cursor, "bus_driver", "driver_code", payload.get("driver_code"), tenant_id)
        self._execute(cursor, """
            INSERT INTO bus_vehicle
                (vehicle_code, plate_no, vehicle_type, seat_count, max_load_count, vehicle_color,
                 operation_status, operation_mode, current_driver_id, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                plate_no=VALUES(plate_no), seat_count=VALUES(seat_count), max_load_count=VALUES(max_load_count),
                vehicle_color=VALUES(vehicle_color), operation_status=VALUES(operation_status),
                current_driver_id=VALUES(current_driver_id), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            payload["vehicle_code"],
            payload.get("plate_no") or payload["vehicle_code"],
            payload.get("vehicle_type") or "bus",
            payload.get("seat_count") or 0,
            payload.get("max_load_count") or 0,
            payload.get("vehicle_color"),
            payload.get("operation_status") or "idle",
            payload.get("operation_mode") or "dynamic_bus",
            driver_id,
            tenant_id,
        ))

    def _op_vehicle_driver_bind(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        driver_id = self._fetch_id(cursor, "bus_driver", "driver_code", payload.get("driver_code"), tenant_id)
        if vehicle_id is None or driver_id is None:
            return
        self._execute(cursor, """
            INSERT INTO bus_vehicle_driver_bind
                (vehicle_id, driver_id, bind_status, bind_at, unbind_at, operator, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            vehicle_id,
            driver_id,
            payload.get("bind_status") or "active",
            _to_datetime(payload.get("bind_at")) or _now_dt(),
            _to_datetime(payload.get("unbind_at")),
            payload.get("operator"),
            tenant_id,
        ))

    def _op_order(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("assigned_vehicle_code"), tenant_id)
        driver_id = self._fetch_id(cursor, "bus_driver", "driver_code", payload.get("assigned_driver_code"), tenant_id)
        origin_poi_id = self._fetch_id(cursor, "map_poi", "poi_code", payload.get("origin_poi_code"), tenant_id)
        destination_poi_id = self._fetch_id(cursor, "map_poi", "poi_code", payload.get("destination_poi_code"), tenant_id)
        self._execute(cursor, """
            INSERT INTO bus_order
                (request_id, passenger_code, passenger_phone, passenger_count, order_source, status,
                 origin_lon, origin_lat, destination_lon, destination_lat, origin_poi_id, destination_poi_id,
                 origin_node_code, destination_node_code, origin_name, destination_name, request_time,
                 expected_pickup_earliest, expected_pickup_latest, passenger_ready_time, max_pickup_time,
                 max_arrival_time, assigned_vehicle_id, assigned_driver_id, assigned_plate_no, answer_time,
                 actual_pickup_time, completion_time, cancel_time, cancel_type, cancel_reason,
                 actual_pickup_distance_m, actual_pickup_duration_s, loaded_distance_m, loaded_duration_s,
                 route_version, route_status, route_distance_m, route_duration_s, raw_route_points,
                 grasped_route_points, route_segments, route_updated_at, route_error,
                 estimated_arrival_time, estimated_dropoff_time, estimated_arrival_eta_seconds,
                 estimated_dropoff_eta_seconds, eta_status, eta_error, eta_updated_at, tenant_id)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                 passenger_count=VALUES(passenger_count), status=VALUES(status),
                 assigned_vehicle_id=VALUES(assigned_vehicle_id), assigned_driver_id=VALUES(assigned_driver_id),
                 assigned_plate_no=VALUES(assigned_plate_no), answer_time=COALESCE(VALUES(answer_time), answer_time),
                 actual_pickup_time=COALESCE(VALUES(actual_pickup_time), actual_pickup_time),
                 completion_time=COALESCE(VALUES(completion_time), completion_time),
                 cancel_time=COALESCE(VALUES(cancel_time), cancel_time),
                 cancel_type=COALESCE(VALUES(cancel_type), cancel_type),
                 cancel_reason=COALESCE(VALUES(cancel_reason), cancel_reason),
                 route_version=COALESCE(VALUES(route_version), route_version),
                 route_status=COALESCE(VALUES(route_status), route_status),
                 route_distance_m=COALESCE(VALUES(route_distance_m), route_distance_m),
                 route_duration_s=COALESCE(VALUES(route_duration_s), route_duration_s),
                 raw_route_points=COALESCE(VALUES(raw_route_points), raw_route_points),
                 grasped_route_points=COALESCE(VALUES(grasped_route_points), grasped_route_points),
                 route_segments=COALESCE(VALUES(route_segments), route_segments),
                 route_updated_at=COALESCE(VALUES(route_updated_at), route_updated_at),
                 route_error=VALUES(route_error),
                 estimated_arrival_time=COALESCE(VALUES(estimated_arrival_time), estimated_arrival_time),
                 estimated_dropoff_time=COALESCE(VALUES(estimated_dropoff_time), estimated_dropoff_time),
                 estimated_arrival_eta_seconds=COALESCE(VALUES(estimated_arrival_eta_seconds), estimated_arrival_eta_seconds),
                 estimated_dropoff_eta_seconds=COALESCE(VALUES(estimated_dropoff_eta_seconds), estimated_dropoff_eta_seconds),
                 eta_status=COALESCE(VALUES(eta_status), eta_status),
                 eta_error=VALUES(eta_error), eta_updated_at=COALESCE(VALUES(eta_updated_at), eta_updated_at),
                 updated_at=CURRENT_TIMESTAMP(3)
        """, (
            payload["request_id"],
            payload.get("passenger_code"),
            payload.get("passenger_phone"),
            payload.get("passenger_count") or 1,
            payload.get("order_source"),
            payload.get("status") or "pooled",
            payload.get("origin_lon"),
            payload.get("origin_lat"),
            payload.get("destination_lon"),
            payload.get("destination_lat"),
            origin_poi_id,
            destination_poi_id,
            payload.get("origin_node_code"),
            payload.get("destination_node_code"),
            payload.get("origin_name"),
            payload.get("destination_name"),
            _to_datetime(payload.get("request_time")),
            _to_datetime(payload.get("expected_pickup_earliest")),
            _to_datetime(payload.get("expected_pickup_latest")),
            _to_datetime(payload.get("passenger_ready_time")),
            _to_datetime(payload.get("max_pickup_time")),
            _to_datetime(payload.get("max_arrival_time")),
            vehicle_id,
            driver_id,
            payload.get("assigned_plate_no"),
            _to_datetime(payload.get("answer_time")),
            _to_datetime(payload.get("actual_pickup_time")),
            _to_datetime(payload.get("completion_time")),
            _to_datetime(payload.get("cancel_time")),
            payload.get("cancel_type"),
            payload.get("cancel_reason"),
            payload.get("actual_pickup_distance_m"),
            payload.get("actual_pickup_duration_s"),
            payload.get("loaded_distance_m"),
            payload.get("loaded_duration_s"),
            payload.get("route_version"),
            payload.get("route_status"),
            payload.get("route_distance_m"),
            payload.get("route_duration_s"),
            _json(payload.get("raw_route_points")),
            _json(payload.get("grasped_route_points")),
            _json(payload.get("route_segments")),
            _to_datetime(payload.get("route_updated_at")),
            payload.get("route_error"),
            _to_datetime(payload.get("estimated_arrival_time")),
            _to_datetime(payload.get("estimated_dropoff_time")),
            _int_or_none(payload.get("estimated_arrival_eta_seconds")),
            _int_or_none(payload.get("estimated_dropoff_eta_seconds")),
            payload.get("eta_status"),
            payload.get("eta_error"),
            _to_datetime(payload.get("eta_updated_at")),
            tenant_id,
        ))

    def _op_dispatch_task(self, cursor, tenant_id, payload):
        order_id = self._fetch_id(cursor, "bus_order", "request_id", payload.get("request_id"), tenant_id)
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        selected_vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("selected_vehicle_code"), tenant_id)
        self._execute(cursor, """
            INSERT INTO bus_dispatch_task
                (task_no, task_type, trigger_source, request_id, order_id, vehicle_id, selected_vehicle_id,
                 route_version, status, candidate_vehicle_count, input_summary, output_summary,
                 elapsed_ms, error_message, started_at, finished_at, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status=VALUES(status), output_summary=VALUES(output_summary), elapsed_ms=VALUES(elapsed_ms),
                error_message=VALUES(error_message), finished_at=VALUES(finished_at), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            payload["task_no"],
            payload.get("task_type") or "dispatch",
            payload.get("trigger_source"),
            payload.get("request_id"),
            order_id,
            vehicle_id,
            selected_vehicle_id,
            payload.get("route_version"),
            payload.get("status") or "success",
            payload.get("candidate_vehicle_count"),
            _json(payload.get("input_summary")),
            _json(payload.get("output_summary")),
            payload.get("elapsed_ms"),
            payload.get("error_message"),
            _to_datetime(payload.get("started_at")),
            _to_datetime(payload.get("finished_at")),
            tenant_id,
        ))

    def _op_route_step(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        order_id = self._fetch_id(cursor, "bus_order", "request_id", payload.get("request_id"), tenant_id)
        target_poi_id = self._fetch_id(cursor, "map_poi", "poi_code", payload.get("target_poi_code"), tenant_id)
        if vehicle_id is None or order_id is None:
            return
        self._execute(cursor, """
            INSERT INTO bus_dispatch_route_step
                (vehicle_id, route_version, sequence_no, step_type, order_id, request_id, target_poi_id,
                 target_node_code, target_lon, target_lat, planned_arrival_time, eta_seconds,
                 status, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                step_type=VALUES(step_type), order_id=VALUES(order_id), request_id=VALUES(request_id),
                target_poi_id=VALUES(target_poi_id), target_node_code=VALUES(target_node_code),
                target_lon=VALUES(target_lon), target_lat=VALUES(target_lat), eta_seconds=VALUES(eta_seconds),
                status=VALUES(status), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            vehicle_id,
            payload["route_version"],
            payload["sequence_no"],
            payload["step_type"],
            order_id,
            payload["request_id"],
            target_poi_id,
            payload.get("target_node_code"),
            payload.get("target_lon"),
            payload.get("target_lat"),
            _to_datetime(payload.get("planned_arrival_time")),
            payload.get("eta_seconds"),
            payload.get("status") or "pending",
            tenant_id,
        ))

    def _op_route_segment(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        order_id = self._fetch_id(cursor, "bus_order", "request_id", payload.get("request_id"), tenant_id)
        target_poi_id = self._fetch_id(cursor, "map_poi", "poi_code", payload.get("target_poi_code"), tenant_id)
        if vehicle_id is None:
            return
        self._execute(cursor, """
            INSERT INTO bus_dispatch_route_segment
                (vehicle_id, route_version, segment_index, segment_type, order_id, request_id,
                 start_node_code, end_node_code, target_poi_id, raw_points, grasped_points,
                 distance_m, duration_s, eta_seconds, grasp_status, grasp_error, segment_status, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                segment_type=VALUES(segment_type), order_id=VALUES(order_id), request_id=VALUES(request_id),
                start_node_code=VALUES(start_node_code), end_node_code=VALUES(end_node_code),
                target_poi_id=VALUES(target_poi_id), raw_points=VALUES(raw_points),
                grasped_points=VALUES(grasped_points), distance_m=VALUES(distance_m),
                duration_s=VALUES(duration_s), eta_seconds=VALUES(eta_seconds),
                grasp_status=VALUES(grasp_status), grasp_error=VALUES(grasp_error),
                segment_status=VALUES(segment_status), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            vehicle_id,
            payload["route_version"],
            payload["segment_index"],
            payload["segment_type"],
            order_id,
            payload.get("request_id"),
            payload.get("start_node_code"),
            payload.get("end_node_code"),
            target_poi_id,
            _json(payload.get("raw_points")),
            _json(payload.get("grasped_points")),
            payload.get("distance_m"),
            payload.get("duration_s"),
            payload.get("eta_seconds"),
            payload.get("grasp_status"),
            payload.get("grasp_error"),
            payload.get("segment_status") or "active",
            tenant_id,
        ))

    def _op_vehicle_runtime(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        driver_id = self._fetch_id(cursor, "bus_driver", "driver_code", payload.get("driver_code"), tenant_id)
        idle_target_poi_id = self._fetch_id(cursor, "map_poi", "poi_code", payload.get("idle_target_poi_code"), tenant_id)
        if vehicle_id is None:
            return
        self._execute(cursor, """
            INSERT INTO bus_vehicle_runtime
                (vehicle_id, driver_id, current_lon, current_lat, speed_kmh, heading, last_node_code,
                 next_node_code, edge_progress, on_board_count, on_board_order_ids, planned_step_count,
                 rest_status, can_accept_order, route_version, route_grasp_status, route_grasp_error,
                 idle_target_poi_id, idle_target_lon, idle_target_lat, idle_target_eta_seconds,
                 idle_target_eta_time, idle_target_eta_status, reported_at, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                driver_id=VALUES(driver_id), current_lon=VALUES(current_lon), current_lat=VALUES(current_lat),
                last_node_code=VALUES(last_node_code), next_node_code=VALUES(next_node_code),
                edge_progress=VALUES(edge_progress), on_board_count=VALUES(on_board_count),
                on_board_order_ids=VALUES(on_board_order_ids), planned_step_count=VALUES(planned_step_count),
                rest_status=VALUES(rest_status), can_accept_order=VALUES(can_accept_order),
                route_version=VALUES(route_version), route_grasp_status=VALUES(route_grasp_status),
                route_grasp_error=VALUES(route_grasp_error), idle_target_poi_id=VALUES(idle_target_poi_id),
                idle_target_lon=VALUES(idle_target_lon), idle_target_lat=VALUES(idle_target_lat),
                idle_target_eta_seconds=VALUES(idle_target_eta_seconds),
                idle_target_eta_time=VALUES(idle_target_eta_time),
                idle_target_eta_status=VALUES(idle_target_eta_status),
                reported_at=VALUES(reported_at), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            vehicle_id,
            driver_id,
            payload.get("current_lon"),
            payload.get("current_lat"),
            payload.get("speed_kmh"),
            payload.get("heading"),
            payload.get("last_node_code"),
            payload.get("next_node_code"),
            payload.get("edge_progress"),
            payload.get("on_board_count") or 0,
            _json(payload.get("on_board_order_ids")),
            payload.get("planned_step_count") or 0,
            payload.get("rest_status") or "operating",
            1 if payload.get("can_accept_order", True) else 0,
            payload.get("route_version"),
            payload.get("route_grasp_status"),
            payload.get("route_grasp_error"),
            idle_target_poi_id,
            payload.get("idle_target_lon"),
            payload.get("idle_target_lat"),
            _int_or_none(payload.get("idle_target_eta_seconds")),
            _to_datetime(payload.get("idle_target_eta_time")),
            payload.get("idle_target_eta_status"),
            _to_datetime(payload.get("reported_at")) or _now_dt(),
            tenant_id,
        ))

    def _op_location_log(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        driver_id = self._fetch_id(cursor, "bus_driver", "driver_code", payload.get("driver_code"), tenant_id)
        if vehicle_id is None:
            return
        self._execute(cursor, """
            INSERT INTO bus_vehicle_location_log
                (vehicle_id, driver_id, longitude, latitude, speed_kmh, heading, source,
                 raw_payload, report_time, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            vehicle_id,
            driver_id,
            payload["longitude"],
            payload["latitude"],
            payload.get("speed_kmh"),
            payload.get("heading"),
            payload.get("source") or "gps",
            _json(payload.get("raw_payload")),
            _to_datetime(payload.get("report_time")) or _now_dt(),
            tenant_id,
        ))

    def _op_route_snapshot(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        if vehicle_id is None:
            return
        self._execute(cursor, """
            INSERT INTO bus_vehicle_route_snapshot
                (vehicle_id, route_version, route_type, raw_route_points, grasped_route_points,
                 raw_segments, grasped_segments, distance_m, planned_step_count, grasp_status,
                 grasp_error, snapshot_status, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                 route_type=VALUES(route_type), raw_route_points=VALUES(raw_route_points),
                 grasped_route_points=VALUES(grasped_route_points), raw_segments=VALUES(raw_segments),
                 grasped_segments=VALUES(grasped_segments), distance_m=VALUES(distance_m),
                 planned_step_count=VALUES(planned_step_count), grasp_status=VALUES(grasp_status),
                 grasp_error=VALUES(grasp_error), snapshot_status=VALUES(snapshot_status),
                 updated_at=CURRENT_TIMESTAMP(3)
        """, (
            vehicle_id,
            payload["route_version"],
            payload.get("route_type") or "order",
            _json(payload.get("raw_route_points")),
            _json(payload.get("grasped_route_points")),
            _json(payload.get("raw_segments")),
            _json(payload.get("grasped_segments")),
            payload.get("distance_m"),
            payload.get("planned_step_count") or 0,
            payload.get("grasp_status"),
            payload.get("grasp_error"),
            payload.get("snapshot_status") or "active",
            tenant_id,
        ))

    def _op_rest_request(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        driver_id = self._fetch_id(cursor, "bus_driver", "driver_code", payload.get("driver_code"), tenant_id)
        if vehicle_id is None or driver_id is None:
            return
        self._execute(cursor, """
            INSERT INTO bus_driver_rest_request
                (rest_request_no, driver_id, vehicle_id, desired_rest_time, rest_duration_minutes,
                 status, request_lon, request_lat, requested_at, started_at, ended_at, remark, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status=VALUES(status), started_at=VALUES(started_at), ended_at=VALUES(ended_at),
                remark=VALUES(remark), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            payload["rest_request_no"],
            driver_id,
            vehicle_id,
            _to_datetime(payload.get("desired_rest_time")),
            payload.get("rest_duration_minutes") or 20,
            payload.get("status") or "requested",
            payload.get("request_lon"),
            payload.get("request_lat"),
            _to_datetime(payload.get("requested_at")) or _now_dt(),
            _to_datetime(payload.get("started_at")),
            _to_datetime(payload.get("ended_at")),
            payload.get("remark"),
            tenant_id,
        ))

    def _op_hotspot_forecast(self, cursor, tenant_id, payload):
        vehicle_id = self._fetch_id(cursor, "bus_vehicle", "vehicle_code", payload.get("vehicle_code"), tenant_id)
        hotspot_poi_id = self._fetch_id(cursor, "map_poi", "poi_code", payload.get("hotspot_poi_code"), tenant_id)
        self._execute(cursor, """
            INSERT INTO bus_hotspot_forecast
                (forecast_no, vehicle_id, hotspot_poi_id, target_lon, target_lat, zone, forecast_time,
                 window_start, window_end, score, expected_demand_count, reason_json, status, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status=VALUES(status), expected_demand_count=VALUES(expected_demand_count),
                reason_json=VALUES(reason_json), updated_at=CURRENT_TIMESTAMP(3)
        """, (
            payload["forecast_no"],
            vehicle_id,
            hotspot_poi_id,
            payload["target_lon"],
            payload["target_lat"],
            payload.get("zone"),
            _to_datetime(payload.get("forecast_time")) or _now_dt(),
            _to_datetime(payload.get("window_start")),
            _to_datetime(payload.get("window_end")),
            payload.get("score"),
            payload.get("expected_demand_count"),
            _json(payload.get("reason_json")),
            payload.get("status") or "active",
            tenant_id,
        ))


# ============================================================
# 功能四：模块级持久化管理器与生命周期控制
# 相关方法：manager、configure_from_env、status、start、shutdown、enqueue
# ============================================================

_manager = MySqlPersistence.from_env()


def manager():
    """返回当前模块级持久化管理器。"""
    return _manager


def configure_from_env():
    """重新读取环境变量并替换模块级持久化管理器。

    Returns:
        MySqlPersistence: 新的持久化管理器实例。
    """
    global _manager
    _manager = MySqlPersistence.from_env()
    return _manager


def status():
    """返回数据库持久化状态快照。"""
    return _manager.status()


def start():
    """启动模块级后台写库线程。"""
    return _manager.start()


def shutdown(wait=False):
    """关闭模块级后台写库线程。

    Args:
        wait (bool, optional): 是否等待线程退出。
    """
    return _manager.shutdown(wait=wait)


def enqueue(op, payload):
    """向模块级写库队列提交任务。

    Args:
        op (str): SQL 操作名称。
        payload (dict): 已抽取好的业务快照。

    Returns:
        bool: 是否成功入队。
    """
    return _manager.enqueue(op, payload)


# ============================================================
# 功能五：系统初始化、订单、车辆、路线和业务状态落库入口
# 相关方法：record_initial_state、record_order_snapshot、record_vehicle_route
# ============================================================

def record_initial_state(city_map, fleet):
    """系统初始化后落库基础静态数据与车辆运行初始态。

    Args:
        city_map (CityGraph): 已加载的城市路网与 POI。
        fleet (list[Vehicle]): 当前车辆列表。
    """
    enqueue("tenant", {"tenant_name": os.getenv("BUS_DB_TENANT_NAME") or _manager.tenant_id})
    for node in getattr(city_map, "nodes_map", {}).values():
        enqueue("road_node", {
            "node_code": node.id,
            "node_name": getattr(node, "name", None),
            "longitude": getattr(node, "lon", None),
            "latitude": getattr(node, "lat", None),
            "zone": getattr(node, "zone", None),
            "is_poi": bool(getattr(node, "is_poi", False)),
        })
    for poi in getattr(city_map, "pois", []) or []:
        enqueue("poi", {
            "poi_code": poi.id,
            "poi_name": getattr(poi, "name", None) or poi.id,
            "longitude": getattr(poi, "lon", None),
            "latitude": getattr(poi, "lat", None),
            "zone": getattr(poi, "zone", None),
            "node_code": poi.id,
        })
    for vehicle in fleet or []:
        record_driver(vehicle)
        record_vehicle(vehicle)
        record_vehicle_route(vehicle)
        record_vehicle_runtime(vehicle)


def record_driver(vehicle):
    """写入或更新车辆对应的司机档案。

    Args:
        vehicle (Vehicle): 车辆运行对象。
    """
    enqueue("driver", {
        "driver_code": _driver_code(vehicle),
        "driver_no": getattr(vehicle, "driver_no", None),
        "driver_name": getattr(vehicle, "driver_no", None) or _driver_code(vehicle),
        "work_status": "resting" if getattr(vehicle, "is_resting", False) else "listening",
    })


def record_vehicle(vehicle):
    """写入或更新车辆基础档案。

    Args:
        vehicle (Vehicle): 车辆运行对象。
    """
    enqueue("vehicle", {
        "vehicle_code": _vehicle_code(vehicle),
        "plate_no": getattr(vehicle, "plate_no", None) or _vehicle_code(vehicle),
        "seat_count": getattr(vehicle, "capacity", 0),
        "max_load_count": getattr(vehicle, "capacity", 0),
        "vehicle_color": getattr(vehicle, "color", None),
        "operation_status": _operation_status(vehicle),
        "driver_code": _driver_code(vehicle),
    })


def record_vehicle_runtime(vehicle, report_time=None):
    """写入车辆实时运行快照。

    Args:
        vehicle (Vehicle): 车辆运行对象。
        report_time (float | datetime, optional): GPS 或业务事件发生时间。
    """
    gps = getattr(vehicle, "gps", {}) or {}
    idle_target = getattr(vehicle, "idle_target", None) or {}
    enqueue("vehicle_runtime", {
        "vehicle_code": _vehicle_code(vehicle),
        "driver_code": _driver_code(vehicle),
        "current_lon": gps.get("lon"),
        "current_lat": gps.get("lat"),
        "last_node_code": getattr(vehicle, "last_node", None),
        "next_node_code": getattr(vehicle, "next_node", None),
        "edge_progress": getattr(vehicle, "progress", None),
        "on_board_count": sum(getattr(o, "passenger_count", 0) for o in getattr(vehicle, "on_board_orders", []) or []),
        "on_board_order_ids": [str(getattr(o, "request_id", "")) for o in getattr(vehicle, "on_board_orders", []) or []],
        "planned_step_count": len(getattr(vehicle, "planned_route", []) or []),
        "rest_status": getattr(vehicle, "rest_status", "operating"),
        "can_accept_order": (
            not getattr(vehicle, "is_rest_requested", False)
            and not getattr(vehicle, "is_resting", False)
            and getattr(vehicle, "rest_status", "operating") == "operating"
        ),
        "route_version": _route_version(vehicle),
        "route_grasp_status": getattr(vehicle, "planned_route_grasp_status", None),
        "route_grasp_error": getattr(vehicle, "planned_route_grasp_error", None),
        "idle_target_poi_code": idle_target.get("node_id"),
        "idle_target_lon": idle_target.get("lon"),
        "idle_target_lat": idle_target.get("lat"),
        "idle_target_eta_seconds": getattr(vehicle, "idle_target_eta_seconds", None),
        "idle_target_eta_time": getattr(vehicle, "idle_target_eta_time", None),
        "idle_target_eta_status": getattr(vehicle, "idle_target_eta_status", None),
        "reported_at": report_time or getattr(vehicle, "time", None) or time.time(),
    })


def record_location(vehicle, report_time=None, raw_payload=None):
    """写入车辆 GPS 历史轨迹。

    Args:
        vehicle (Vehicle): 车辆运行对象。
        report_time (float | datetime, optional): GPS 上报时间。
        raw_payload (dict, optional): 路径更新接口返回的原始上下文。

    Returns:
        bool: 成功入队返回 True；车辆暂无 GPS 时返回 False。
    """
    gps = getattr(vehicle, "gps", {}) or {}
    if gps.get("lon") is None or gps.get("lat") is None:
        return False
    return enqueue("location_log", {
        "vehicle_code": _vehicle_code(vehicle),
        "driver_code": _driver_code(vehicle),
        "longitude": gps.get("lon"),
        "latitude": gps.get("lat"),
        "source": "gps",
        "raw_payload": raw_payload,
        "report_time": report_time or getattr(vehicle, "time", None) or time.time(),
    })


def _order_payload(order, city_map=None, status=None, vehicle=None, route_override=None):
    """把 Order 对象转换成 bus_order 可写入载荷。

    Args:
        order (Order): 订单对象。
        city_map (CityGraph, optional): 路网对象，用于新订单 O/D 原始路线计算。
        status (str, optional): 指定写入状态。
        vehicle (Vehicle, optional): 已匹配车辆。
        route_override (dict, optional): 从整车路线截取出的订单路线字段。

    Returns:
        dict: bus_order upsert 载荷。
    """
    route = route_override or _order_route_snapshot(order, city_map)
    payload = {
        "request_id": str(getattr(order, "request_id", "")),
        "passenger_code": getattr(order, "passenger_id", None) or None,
        "passenger_count": getattr(order, "passenger_count", 1),
        "order_source": "dynamic_bus",
        "status": status or _order_status(order),
        "origin_lon": getattr(order, "o_lon", None),
        "origin_lat": getattr(order, "o_lat", None),
        "destination_lon": getattr(order, "d_lon", None),
        "destination_lat": getattr(order, "d_lat", None),
        "origin_poi_code": getattr(getattr(order, "o_node", None), "id", None),
        "destination_poi_code": getattr(getattr(order, "d_node", None), "id", None),
        "origin_node_code": getattr(getattr(order, "o_node", None), "id", None),
        "destination_node_code": getattr(getattr(order, "d_node", None), "id", None),
        "origin_name": getattr(getattr(order, "o_node", None), "name", None),
        "destination_name": getattr(getattr(order, "d_node", None), "name", None),
        "request_time": getattr(order, "request_time", None),
        "expected_pickup_earliest": getattr(order, "expected_pickup_earliest", None),
        "expected_pickup_latest": getattr(order, "expected_pickup_latest", None),
        "passenger_ready_time": getattr(order, "passenger_ready_time", None),
        "max_pickup_time": getattr(order, "max_pickup_time", None),
        "max_arrival_time": getattr(order, "max_arrival_time", None),
        "answer_time": getattr(order, "answer_time", None),
        "actual_pickup_time": getattr(order, "actual_pick_time", None),
        "completion_time": getattr(order, "completion_time", None),
        "cancel_time": getattr(order, "cancel_time", None),
        "cancel_type": getattr(order, "cancel_type", None),
        "cancel_reason": getattr(order, "cancel_reason", None),
        "actual_pickup_distance_m": getattr(order, "actual_pickup_dist", None),
        "loaded_distance_m": getattr(order, "loaded_dist", None),
        "estimated_arrival_time": getattr(order, "estimated_arrival_time", None),
        "estimated_dropoff_time": getattr(order, "estimated_dropoff_time", None),
        "estimated_arrival_eta_seconds": getattr(order, "estimated_arrival_eta_seconds", None),
        "estimated_dropoff_eta_seconds": getattr(order, "estimated_dropoff_eta_seconds", None),
        "eta_status": getattr(order, "eta_status", None),
        "eta_error": getattr(order, "eta_error", None),
        "eta_updated_at": getattr(order, "eta_updated_at", None),
    }
    payload.update(route or {})
    if vehicle is not None:
        payload.update({
            "assigned_vehicle_code": _vehicle_code(vehicle),
            "assigned_driver_code": _driver_code(vehicle),
            "assigned_plate_no": getattr(vehicle, "plate_no", None),
            "answer_time": payload.get("answer_time") or _now_dt(),
        })
    return payload


def record_order_created(order, city_map=None, status="pooled"):
    """新订单进入订单池时写入订单主表。

    Args:
        order (Order): 订单对象。
        city_map (CityGraph, optional): 路网对象，用于补充订单 O/D 原始路线。
        status (str, optional): 初始订单状态。

    Returns:
        bool: 是否成功入队。
    """
    return enqueue("order", _order_payload(order, city_map=city_map, status=status))


def record_order_snapshot(order, city_map=None, status=None, vehicle=None, route_override=None):
    """按订单当前状态刷新 bus_order。

    Args:
        order (Order): 订单对象。
        city_map (CityGraph, optional): 路网对象。
        status (str, optional): 指定写入状态。
        vehicle (Vehicle, optional): 当前服务车辆。
        route_override (dict, optional): 已计算好的订单路线字段。

    Returns:
        bool: 是否成功入队。
    """
    return enqueue("order", _order_payload(
        order,
        city_map=city_map,
        status=status,
        vehicle=vehicle,
        route_override=route_override,
    ))


def record_dispatch_assignment(order, vehicle, city_map=None, path_result=None, details=None):
    """订单派给车辆后写入调度任务、订单、路线和运行态。

    Args:
        order (Order): 被派单订单。
        vehicle (Vehicle): 接单车辆。
        city_map (CityGraph, optional): 路网对象。
        path_result (dict, optional): 当前车辆路线重建结果。
        details (dict, optional): 派单算法输入或评分摘要。
    """
    record_driver(vehicle)
    record_vehicle(vehicle)
    route_version = _route_version(vehicle)
    record_order_snapshot(order, city_map=city_map, status=_order_status(order, "matched"), vehicle=vehicle)
    enqueue("dispatch_task", {
        "task_no": f"dispatch:{getattr(order, 'request_id', '')}:{route_version}:{int(time.time() * 1000)}",
        "task_type": "dispatch",
        "trigger_source": "order_pool",
        "request_id": str(getattr(order, "request_id", "")),
        "vehicle_code": _vehicle_code(vehicle),
        "selected_vehicle_code": _vehicle_code(vehicle),
        "route_version": route_version,
        "status": "success",
        "input_summary": details or {},
        "output_summary": {
            "vehicle_id": getattr(vehicle, "id", None),
            "route_version": route_version,
            "planned_step_count": len(getattr(vehicle, "planned_route", []) or []),
        },
        "finished_at": _now_dt(),
    })
    record_vehicle_route(vehicle, path_result=path_result)
    record_vehicle_runtime(vehicle)


def record_vehicle_route(vehicle, path_result=None):
    """写入整车路线快照、O/D 停靠步骤、分段路线和订单路线。

    Args:
        vehicle (Vehicle): 车辆运行对象。
        path_result (dict, optional): 路线重建结果，用于补充总距离。
    """
    route_version = _route_version(vehicle)
    route_type = "idle" if getattr(vehicle, "idle_target", None) and not getattr(vehicle, "planned_route", None) else "order"
    raw_segments = copy.deepcopy(getattr(vehicle, "planned_route_segment_raw_point", None) or [])
    grasped_segments = copy.deepcopy(getattr(vehicle, "planned_route_segment_grasped_point", None) or [])
    raw_points = copy.deepcopy(getattr(vehicle, "planned_route_point", None) or [])
    grasped_points = copy.deepcopy(getattr(vehicle, "planned_route_grasped_point", None) or [])
    distance = None
    if isinstance(path_result, dict):
        distance = path_result.get("total_distance")
    enqueue("route_snapshot", {
        "vehicle_code": _vehicle_code(vehicle),
        "route_version": route_version,
        "route_type": route_type,
        "raw_route_points": raw_points,
        "grasped_route_points": grasped_points,
        "raw_segments": raw_segments,
        "grasped_segments": grasped_segments,
        "distance_m": distance,
        "planned_step_count": len(getattr(vehicle, "planned_route", []) or []),
        "grasp_status": getattr(vehicle, "planned_route_grasp_status", None),
        "grasp_error": getattr(vehicle, "planned_route_grasp_error", None),
        "snapshot_status": "active",
    })

    # 计划步骤只保存 O/D 停靠序列，便于后台按车辆查看后续服务顺序。
    for sequence_no, step in enumerate(getattr(vehicle, "planned_route", []) or [], start=1):
        order = step.get("order")
        if order is None:
            continue
        target = getattr(order, "o_node", None) if step.get("type") == "O" else getattr(order, "d_node", None)
        enqueue("route_step", {
            "vehicle_code": _vehicle_code(vehicle),
            "route_version": route_version,
            "sequence_no": sequence_no,
            "step_type": step.get("type"),
            "request_id": str(getattr(order, "request_id", "")),
            "target_poi_code": getattr(target, "id", None),
            "target_node_code": getattr(target, "id", None),
            "target_lon": getattr(target, "lon", None),
            "target_lat": getattr(target, "lat", None),
            "status": "pending",
        })

    # 分段表保存原始 A* 点列与高德纠偏点列，ETA 和地图展示都可复用。
    for segment in _route_segments_from_vehicle(vehicle):
        request_id = segment.get("request_id")
        target = _point_from_mapping(segment.get("target_node"))
        raw_points = segment.get("raw_points") or []
        enqueue("route_segment", {
            "vehicle_code": _vehicle_code(vehicle),
            "route_version": route_version,
            "segment_index": segment.get("index", 0),
            "segment_type": segment.get("type") or "OD",
            "request_id": request_id,
            "target_poi_code": target.get("id") if target else None,
            "start_node_code": raw_points[0].get("id") if raw_points else None,
            "end_node_code": raw_points[-1].get("id") if raw_points else None,
            "raw_points": raw_points,
            "grasped_points": segment.get("grasped_points"),
            "distance_m": segment.get("distance"),
            "duration_s": int(float(segment.get("distance") or 0.0) / SPEED_MPS) if segment.get("distance") else None,
            "grasp_status": getattr(vehicle, "planned_route_grasp_status", None),
            "grasp_error": getattr(vehicle, "planned_route_grasp_error", None),
            "segment_status": "active",
        })

    # 订单主表中的路线是从整车合并路线中截取 O 到 D 后得到的单订单视角。
    for request_id, order in _orders_in_vehicle(vehicle).items():
        route_override = _order_route_from_vehicle(vehicle, request_id)
        if route_override:
            record_order_snapshot(order, status=_order_status(order, "matched"), vehicle=vehicle, route_override=route_override)


def record_path_update(vehicle, path_result=None, report_time=None):
    """GPS 路径更新后写入车辆运行、轨迹、路线与上下客事件。

    Args:
        vehicle (Vehicle): 车辆运行对象。
        path_result (dict, optional): /fleet/<vehicle_id>/path 的路径更新结果。
        report_time (float | datetime, optional): GPS 上报时间。
    """
    record_vehicle(vehicle)
    record_vehicle_runtime(vehicle, report_time=report_time)
    record_location(vehicle, report_time=report_time, raw_payload=path_result)
    record_vehicle_route(vehicle, path_result=path_result)
    for event in (path_result or {}).get("changed_steps", []) if isinstance(path_result, dict) else []:
        request_id = str(event.get("request_id"))
        for order in _orders_in_vehicle(vehicle).values():
            if str(getattr(order, "request_id", "")) == request_id:
                status_value = "riding" if event.get("action") == "pickup" else "completed"
                record_order_snapshot(order, status=status_value, vehicle=vehicle)
                break


def record_rest_request(vehicle, result=None):
    """司机休息或收车申请后写入申请记录与车辆运行态。

    Args:
        vehicle (Vehicle): 车辆运行对象。
        result (dict, optional): 休息接口返回的业务决策结果。
    """
    result = result or {}
    gps = getattr(vehicle, "gps", {}) or {}
    started_at = getattr(vehicle, "rest_started_time", None) if getattr(vehicle, "is_resting", False) else None
    enqueue("rest_request", {
        "rest_request_no": f"rest:{_vehicle_code(vehicle)}:{int(time.time() * 1000)}",
        "vehicle_code": _vehicle_code(vehicle),
        "driver_code": _driver_code(vehicle),
        "desired_rest_time": getattr(vehicle, "desired_rest_time", None),
        "rest_duration_minutes": int((getattr(vehicle, "rest_duration", 0) or 0) / 60) or 20,
        "status": result.get("status") or getattr(vehicle, "rest_status", None) or "requested",
        "request_lon": gps.get("lon"),
        "request_lat": gps.get("lat"),
        "requested_at": _now_dt(),
        "started_at": started_at,
        "remark": result.get("decision"),
    })
    record_vehicle_runtime(vehicle)


def record_route_grasp(vehicle):
    """车辆路线纠偏状态变化后刷新路线快照与运行态。

    Args:
        vehicle (Vehicle): 车辆运行对象。
    """
    record_vehicle_route(vehicle)
    record_vehicle_runtime(vehicle)


def record_eta_result(vehicle):
    """ETA 后台刷新完成后写入订单 ETA 与车辆热点 ETA。

    Args:
        vehicle (Vehicle): 车辆运行对象。
    """
    if vehicle is not None:
        record_vehicle_runtime(vehicle)
        for order in _orders_in_vehicle(vehicle).values():
            record_order_snapshot(order, status=_order_status(order), vehicle=vehicle)


def record_hotspot_forecast(vehicle):
    """空车热点预测生成后写入热点预测结果和车辆运行态。

    Args:
        vehicle (Vehicle): 车辆运行对象。

    Returns:
        bool: 没有热点目标时返回 False；否则提交写库任务。
    """
    idle_target = getattr(vehicle, "idle_target", None) or {}
    idle_forecast = getattr(vehicle, "idle_forecast", None) or {}
    if not idle_target:
        return False
    enqueue("hotspot_forecast", {
        "forecast_no": f"hotspot:{_vehicle_code(vehicle)}:{idle_forecast.get('forecast_generated_at') or int(time.time())}",
        "vehicle_code": _vehicle_code(vehicle),
        "hotspot_poi_code": idle_target.get("node_id"),
        "target_lon": idle_target.get("lon") or idle_target.get("node_lon"),
        "target_lat": idle_target.get("lat") or idle_target.get("node_lat"),
        "zone": idle_forecast.get("zone"),
        "forecast_time": idle_forecast.get("forecast_generated_at") or _now_dt(),
        "expected_demand_count": idle_forecast.get("pred_count"),
        "reason_json": {
            "idle_target": idle_target,
            "idle_forecast": idle_forecast,
        },
        "status": "active",
    })
    record_vehicle_runtime(vehicle)
