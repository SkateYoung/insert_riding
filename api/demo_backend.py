# demo_backend.py
"""
demo.html 所有算法的 Python 移植版。
包含：
  - 地图数据加载（map_data.js → Python 字典）
  - Haversine 球面距离
  - A* 寻路 + 全局路径缓存
  - evaluateRoute（综合多目标成本函数，含 ALPHA/BETA/GAMMA/THETA）
  - insertOrderForVehicle（全排列插入 + 2-Opt 突变优化）
  - rebuildPhysics（路径队列重建）
  - Tick 物理时间步进（车辆移动、上下客、超时判定、订单池轮询）
  - HTTP API 服务（/, /tick, /spawn_order）
用法：
    python demo_backend.py
"""

import json
import math
import os
import random
import re
import heapq
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# ──────────────────────────────────────────────
# 1. 加载 map_data.js → Python 字典
# ──────────────────────────────────────────────
_MAP_DATA = None


def _load_map_data(path: str = "map_data.js") -> dict:
    """读取 map_data.js 中的 JSONP 数据并解析。"""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    # 抹掉头部的 "window.MAP_DATA = " 和尾部的 ";" 取出纯 JSON
    raw = re.sub(r"^\s*window\.MAP_DATA\s*=\s*", "", raw, count=1).rstrip().rstrip(";")
    return json.loads(raw)


def get_map_data() -> dict:
    global _MAP_DATA
    if _MAP_DATA is None:
        _MAP_DATA = _load_map_data()
    return _MAP_DATA


# ──────────────────────────────────────────────
# 2. 地理工具函数
# ──────────────────────────────────────────────

def haversine_dist(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """球面距离(米) —— Haversine 公式。"""
    R = 6_371_000
    r = math.pi / 180
    dLat = (lat2 - lat1) * r
    dLon = (lon2 - lon1) * r
    a = math.sin(dLat / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin(dLon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ──────────────────────────────────────────────
# 3. 模拟器核心状态（单例）
# ──────────────────────────────────────────────

class SimState:
    """全局模拟器状态，对应 demo.html 中的所有顶层变量。"""

    def __init__(self):
        md = get_map_data()
        self.SPEED: float = md["speed_mps"]  # 8.333 m/s ≈ 30 km/h
        self.CAPACITY: int = 10
        self.sys_time: float = 0.0
        self.order_counter: int = 1

        # ── 节点表 ──
        raw_nodes = md["nodes"]
        self.nodes: dict = {}
        min_lon, max_lon = math.inf, -math.inf
        min_lat, max_lat = math.inf, -math.inf
        for nid, n in raw_nodes.items():
            self.nodes[nid] = {
                "id": nid,
                "lon": n["lon"],
                "lat": n["lat"],
                "zone": n["zone"],
                "is_poi": n["is_poi"],
                "neighbors": [],  # 将在 edges 中填充
            }
            if n["lon"] < min_lon: min_lon = n["lon"]
            if n["lon"] > max_lon: max_lon = n["lon"]
            if n["lat"] < min_lat: min_lat = n["lat"]
            if n["lat"] > max_lat: max_lat = n["lat"]

        self.min_lon = min_lon
        self.max_lon = max_lon
        self.min_lat = min_lat
        self.max_lat = max_lat

        # ── 邻接表（list of {id, dist}）和边表 ──
        self.edges = md["edges"]
        # 为 A* 也保留字典形式的邻接关系
        self._neighbors_dict: dict[str, dict[str, float]] = {nid: {} for nid in self.nodes}
        for e in self.edges:
            u, v, d = e["u"], e["v"], e["dist"]
            self.nodes[u]["neighbors"].append({"id": v, "dist": d})
            self.nodes[v]["neighbors"].append({"id": u, "dist": d})
            self._neighbors_dict[u][v] = d
            self._neighbors_dict[v][u] = d

        # ── 画布坐标映射（1000×800 虚拟世界）──
        vw, vh = 1000, 800
        for nid, n in self.nodes.items():
            n["x"] = (n["lon"] - min_lon) / (max_lon - min_lon) * vw
            n["y"] = vh - ((n["lat"] - min_lat) / (max_lat - min_lat) * vh)

        # ── POI 节点 ID 列表 ──
        self.pois: list = md["pois"]

        # ── A* 路径缓存 ──
        self._path_cache: dict = {}

        # ── 车队（截取 map_data 第一辆） ──
        vdata = md["fleet"][0]
        sn = self.nodes[vdata["start_node"]]
        self.fleet: list = [
            {
                "id": "全城通航1号巴士",
                "color": "#10b981",
                "zone": vdata["zone"],
                "capacity": self.CAPACITY,
                "time": 0.0,
                "onBoardOrders": [],
                "plannedRoute": [],        # list of {type: 'P'/'D', order: {...}}
                "lastNode": sn,
                "nextNode": sn,
                "x": sn["x"],
                "y": sn["y"],
                "pathQueue": [],           # list of {node: {...}, action: step|None}
                "waitingSince": None,
            }
        ]

        # ── 订单大表 & 等待池 ──
        self.active_orders: list = []
        self.order_pool: list = []
        self.pool_update_timer: float = 0.0

        # ── 给前端的事件日志队列（FIFO） ──
        self.pending_logs: list = []  # list of {msg: str, color: str}

        # 线程锁，保障 tick 与 HTTP 并发安全
        self._lock = threading.Lock()

    # ── 日志收集 ──
    def _log(self, msg: str, color: str = "#64748b"):
        self.pending_logs.append({"msg": msg, "color": color, "time": round(self.sys_time, 1)})

    # ── 取走所有待发日志 ──
    def flush_logs(self) -> list:
        logs = self.pending_logs[:]
        self.pending_logs.clear()
        return logs


# ──────────────────────────────────────────────
# 4. A* 寻路算法（含缓存）
# ──────────────────────────────────────────────

def _a_star(sim: SimState, start_id: str, end_id: str) -> dict:
    """A* 寻路，返回 {dist: float, path: [node_dict, ...]}。"""
    if start_id == end_id:
        return {"dist": 0.0, "path": [sim.nodes[start_id]]}

    nodes = sim.nodes
    end_n = nodes[end_id]
    open_set = []  # (f, counter, id)
    counter = 0
    heapq.heappush(open_set, (0.0, counter, start_id))
    came_from: dict = {}
    g_score: dict = {start_id: 0.0}

    while open_set:
        _, _, curr_id = heapq.heappop(open_set)
        if curr_id == end_id:
            path = []
            step = curr_id
            while step:
                path.append(nodes[step])
                step = came_from.get(step)
            path.reverse()
            return {"dist": g_score[curr_id], "path": path}

        curr_n = nodes[curr_id]
        for ne in curr_n["neighbors"]:
            ne_id, ne_dist = ne["id"], ne["dist"]
            tg = g_score[curr_id] + ne_dist
            if ne_id not in g_score or tg < g_score[ne_id]:
                came_from[ne_id] = curr_id
                g_score[ne_id] = tg
                nn = nodes[ne_id]
                h = haversine_dist(nn["lon"], nn["lat"], end_n["lon"], end_n["lat"])
                counter += 1
                heapq.heappush(open_set, (tg + h, counter, ne_id))

    return {"dist": math.inf, "path": []}


def get_cached_path(sim: SimState, start_id: str, end_id: str) -> dict:
    """带全局缓存的 A* 封装。"""
    if start_id == end_id:
        return {"dist": 0.0, "path": [sim.nodes[start_id]]}
    key = f"{start_id}|{end_id}"
    if key not in sim._path_cache:
        sim._path_cache[key] = _a_star(sim, start_id, end_id)
    return sim._path_cache[key]


# ──────────────────────────────────────────────
# 5. 综合成本评估函数 evaluateRoute
# ──────────────────────────────────────────────

def evaluate_route(sim: SimState, route: list, vehicle: dict) -> dict:
    """
    量化一条路线序列的综合成本，对应 demo.html 的 evaluateRoute()。
    Returns:
        {feasible: bool, cost: float, pickT: dict, arrT: dict}
    """
    ALPHA_1 = 0.0    # 空驶里程倍率惩罚（与 demo.html 一致）
    ALPHA_2 = 1.0    # 载客有效里程基准
    BETA    = 3.5    # 站牌下乘客枯等折损
    GAMMA   = 2.5    # 车内乘客绕路折损
    THETA   = 1500.0 # 老客超180s延宕护盾
    INFEASIBLE = {"feasible": False, "cost": math.inf, "pickT": {}, "arrT": {}}

    sl = vehicle["lastNode"]
    sn = vehicle["nextNode"]

    # 计算当前在路段上的剩余距离
    first_dist = 0.0
    if sl["id"] != sn["id"]:
        street_len = 1.0
        for ne in sl["neighbors"]:
            if ne["id"] == sn["id"]:
                street_len = ne["dist"]
                break
        ln = math.hypot(sn["x"] - sl["x"], sn["y"] - sl["y"])
        vn = math.hypot(sn["x"] - vehicle["x"], sn["y"] - vehicle["y"])
        first_dist = street_len * (vn / (ln if ln > 0 else 1))

    sim_t = vehicle["time"] + first_dist / sim.SPEED
    cl = len(vehicle["onBoardOrders"])
    empty_dist = 0.0
    loaded_dist = 0.0
    zone_penalty = 0.0
    pick_t: dict = {}
    arr_t: dict = {}

    if cl == 0:
        empty_dist += first_dist
    else:
        loaded_dist += first_dist

    cur_sn = sn

    for step in route:
        o = step["order"]
        tg = o["pNode"] if step["type"] == "P" else o["dNode"]
        res = get_cached_path(sim, cur_sn["id"], tg["id"])
        if res["dist"] == math.inf:
            return INFEASIBLE

        if cl == 0:
            empty_dist += res["dist"]
        else:
            loaded_dist += res["dist"]

        sim_t += res["dist"] / sim.SPEED
        cur_sn = tg

        if tg["zone"] != vehicle["zone"]:
            zone_penalty += 300.0

        if step["type"] == "P":
            cl += 1
            if cl > vehicle["capacity"]:
                return INFEASIBLE
            pick_t[o["id"]] = sim_t
        else:
            cl -= 1
            if cl < 0:
                return INFEASIBLE
            arr_t[o["id"]] = sim_t

    cost = ALPHA_1 * empty_dist + ALPHA_2 * loaded_dist + zone_penalty

    for step in route:
        o = step["order"]
        if step["type"] == "P":
            wait_time = pick_t[o["id"]] - o["reqTime"]
            cost += BETA * wait_time
            if pick_t[o["id"]] > o["maxPickupTime"]:
                return INFEASIBLE
        else:
            # 如果订单已在车上，pick_t 中不会有该订单 ID，我们在后续 onboard 循环中处理其成本
            if o["id"] in pick_t:
                in_car_time = arr_t[o["id"]] - pick_t[o["id"]]
                cost += GAMMA * in_car_time
            
            if arr_t[o["id"]] > o["maxArrivalTime"]:
                return INFEASIBLE

    for onboard in vehicle["onBoardOrders"]:
        extra = arr_t.get(onboard["id"], 0) - vehicle["time"]
        cost += GAMMA * extra
        if extra > 180.0:
            cost += THETA

    return {"feasible": True, "cost": cost, "pickT": pick_t, "arrT": arr_t}


# ──────────────────────────────────────────────
# 6. 订单插入 + 2-Opt 优化
# ──────────────────────────────────────────────

def insert_order_for_vehicle(sim: SimState, v: dict, order: dict) -> dict:
    """
    贪婪全排列插入 + 2-Opt 突变，对应 demo.html 的 insertOrderForVehicle()。
    Returns: {route, cost, pickT, arrT}
    """
    r = v["plannedRoute"]
    n = len(r)
    best_r = None
    best_c = math.inf
    best_p = best_a = None
    p_step = {"type": "P", "order": order}
    d_step = {"type": "D", "order": order}

    for i in range(n + 1):
        tr1 = r[:i] + [p_step] + r[i:]
        for j in range(i + 1, n + 2):
            tr2 = tr1[:j] + [d_step] + tr1[j:]
            res = evaluate_route(sim, tr2, v)
            if res["feasible"] and res["cost"] < best_c:
                best_c = res["cost"]
                best_r = tr2
                best_p = res["pickT"]
                best_a = res["arrT"]

    # 2-Opt 突变反转寻优
    if best_r:
        improved = True
        safety = 50
        onboard_ids = {x["id"] for x in v["onBoardOrders"]}
        while improved and safety > 0:
            safety -= 1
            improved = False
            tr_len = len(best_r)
            for i in range(tr_len - 1):
                for j in range(i + 1, tr_len):
                    mut_r = best_r[:i] + list(reversed(best_r[i:j + 1])) + best_r[j + 1:]
                    # 检查前置依赖：不能在接到乘客之前送客
                    valid = True
                    seen_p: set = set()
                    for step in mut_r:
                        if step["type"] == "P":
                            seen_p.add(step["order"]["id"])
                        else:
                            oid = step["order"]["id"]
                            if oid not in seen_p and oid not in onboard_ids:
                                valid = False
                                break
                    if not valid:
                        continue
                    res = evaluate_route(sim, mut_r, v)
                    if res["feasible"] and res["cost"] < best_c - 0.001:
                        best_c = res["cost"]
                        best_r = mut_r
                        best_p = res["pickT"]
                        best_a = res["arrT"]
                        improved = True
                        break
                if improved:
                    break

    return {"route": best_r, "cost": best_c, "pickT": best_p, "arrT": best_a}


# ──────────────────────────────────────────────
# 7. 物理路径重建 rebuildPhysics
# ──────────────────────────────────────────────

def rebuild_physics(sim: SimState, v: dict):
    """把 plannedRoute 展开成逐节点的 pathQueue，对应 demo.html 的 rebuildPhysics()。"""
    seq = []
    curr = v["nextNode"]

    for step in v["plannedRoute"]:
        tg = step["order"]["pNode"] if step["type"] == "P" else step["order"]["dNode"]
        res = get_cached_path(sim, curr["id"], tg["id"])
        path = res["path"]
        if len(path) == 1:
            seq.append({"node": tg, "action": step})
        else:
            for i in range(1, len(path)):
                nd = path[i]
                is_last = (i == len(path) - 1)
                seq.append({"node": nd, "action": step if is_last else None})
        curr = tg

    if v["lastNode"]["id"] != v["nextNode"]["id"]:
        if not seq or seq[0]["node"]["id"] != v["nextNode"]["id"]:
            seq.insert(0, {"node": v["nextNode"], "action": None})

    v["pathQueue"] = seq


# ──────────────────────────────────────────────
# 8. 生成随机"野外"订单
# ──────────────────────────────────────────────

def generate_wild_order(sim: SimState) -> dict | None:
    """对应 demo.html 的 generateWildOrder()。"""
    r_lon = sim.min_lon + random.random() * (sim.max_lon - sim.min_lon)
    r_lat = sim.min_lat + random.random() * (sim.max_lat - sim.min_lat)
    d_lon = sim.min_lon + random.random() * (sim.max_lon - sim.min_lon)
    d_lat = sim.min_lat + random.random() * (sim.max_lat - sim.min_lat)

    def nearest_poi(lon: float, lat: float) -> dict | None:
        best = None
        bd = math.inf
        for pid in sim.pois:
            p = sim.nodes[pid]
            d = haversine_dist(lon, lat, p["lon"], p["lat"])
            if d < bd:
                bd = d
                best = p
        return best

    p_node = nearest_poi(r_lon, r_lat)
    d_node = nearest_poi(d_lon, d_lat)

    if p_node is None or d_node is None or p_node["id"] == d_node["id"]:
        sim._log("❌ 用户请求由于过近或偏远被吸附至同一POI，已驳回。", "#ef4444")
        return None

    direct_dist = get_cached_path(sim, p_node["id"], d_node["id"])["dist"]
    direct_time = direct_dist / sim.SPEED

    order = {
        "id": sim.order_counter,
        "pNode": p_node,
        "dNode": d_node,
        "reqTime": sim.sys_time,
        "maxPickupTime": sim.sys_time + 1800.0,
        "maxArrivalTime": sim.sys_time + 1800.0 + direct_time * 2.0 + 300.0,
        "passengerReadyTime": sim.sys_time + random.random() * 400.0,
        "passengerMaxWait": 1800.0,
        "vehicleMaxWait": 180.0,
    }
    sim.order_counter += 1

    best_v = None
    best_route = None
    best_cost = math.inf

    for v in sim.fleet:
        r = insert_order_for_vehicle(sim, v, order)
        if r["cost"] < best_cost:
            best_cost = r["cost"]
            best_route = r["route"]
            best_v = v

    if best_v:
        best_v["plannedRoute"] = best_route
        rebuild_physics(sim, best_v)
        sim._log(
            f"✅ 将 [单{order['id']}] 指派给 <b style=\"color:{best_v['color']}\">{best_v['id']}</b>！"
        )
        sim.active_orders.append(
            {"order": order, "vId": best_v["id"], "vColor": best_v["color"], "state": "waiting"}
        )
    else:
        sim._log(f"⚠️ 大面积爆单阻塞，[单{order['id']}] 落入【缓存等待池】！", "#f59e0b")
        sim.order_pool.append(order)
        sim.active_orders.append(
            {"order": order, "vId": "【池化沉淀等待资源】", "state": "matching"}
        )

    return order


# ──────────────────────────────────────────────
# 9. Tick 物理步进（主仿真心跳）
# ──────────────────────────────────────────────

def tick(sim: SimState, dt: float) -> dict:
    """
    推进系统时间 dt 秒，更新所有车辆位置、处理上下客、检查订单池。
    Returns 本帧的全量状态快照，供前端直接渲染。
    """
    sim.sys_time += dt
    sim.pool_update_timer += dt

    # ── 订单缓冲池轮询（每 3 秒一次） ──
    if sim.pool_update_timer > 3.0 and sim.order_pool:
        sim.pool_update_timer = 0.0
        for i in range(len(sim.order_pool) - 1, -1, -1):
            o = sim.order_pool[i]
            # 超时剔除
            if sim.sys_time > o["maxPickupTime"]:
                sim.order_pool.pop(i)
                sim.active_orders = [a for a in sim.active_orders if a["order"]["id"] != o["id"]]
                sim._log(f"🗑️ 乘客 [单{o['id']}] 在寒风中等了太久没派上车，退出软件！", "#ef4444")
                continue
            best_v = best_route = None
            best_cost = math.inf
            for v in sim.fleet:
                res = insert_order_for_vehicle(sim, v, o)
                if res["cost"] < best_cost:
                    best_cost = res["cost"]
                    best_route = res["route"]
                    best_v = v
            if best_v and best_cost < math.inf:
                sim.order_pool.pop(i)
                best_v["plannedRoute"] = best_route
                rebuild_physics(sim, best_v)
                ao = next((a for a in sim.active_orders if a["order"]["id"] == o["id"]), None)
                if ao:
                    ao["vId"] = best_v["id"]
                    ao["state"] = "waiting"
                sim._log(f"🎉 缓冲池：[单{o['id']}] 被 {best_v['id']} 打捞接单！", best_v["color"])

    # ── 车辆物理步进 ──
    for v in sim.fleet:
        v["time"] += dt
        remaining = sim.SPEED * dt
        safety = 200

        while remaining > 0.001 and v["pathQueue"] and safety > 0:
            safety -= 1
            nex = v["pathQueue"][0]
            v["nextNode"] = nex["node"]

            dist_canvas = math.hypot(
                nex["node"]["x"] - v["x"],
                nex["node"]["y"] - v["y"]
            )
            # 从物理里程换算为虚拟画布像素步长
            full_canvas = math.hypot(
                v["nextNode"]["x"] - v["lastNode"]["x"],
                v["nextNode"]["y"] - v["lastNode"]["y"]
            )
            if full_canvas < 0.001:
                full_canvas = 1.0
            # 对应链路的物理真实长度
            street_len = 1.0
            for ne in v["lastNode"]["neighbors"]:
                if ne["id"] == v["nextNode"]["id"]:
                    street_len = ne["dist"]
                    break

            move_pixel = full_canvas * (remaining / street_len)

            if dist_canvas <= move_pixel:
                spent = (dist_canvas / full_canvas) * street_len
                remaining -= spent
                v["x"] = v["nextNode"]["x"]
                v["y"] = v["nextNode"]["y"]

                if nex["action"]:
                    step = nex["action"]
                    o = step["order"]
                    ao = next((a for a in sim.active_orders if a["order"]["id"] == o["id"]), None)

                    if step["type"] == "P":
                        # 乘客还没走到站
                        if sim.sys_time < o["passengerReadyTime"]:
                            if v["waitingSince"] is None:
                                v["waitingSince"] = sim.sys_time
                            # 超时取消
                            if sim.sys_time - v["waitingSince"] > o["vehicleMaxWait"]:
                                sim._log(
                                    f"🚫 乘客 [单{o['id']}] 迟到超时，司机取消该单！", "#f43f5e"
                                )
                                v["plannedRoute"] = [s for s in v["plannedRoute"] if s["order"]["id"] != o["id"]]
                                sim.active_orders = [a for a in sim.active_orders if a["order"]["id"] != o["id"]]
                                v["waitingSince"] = None
                                rebuild_physics(sim, v)
                                remaining = 0  # 丢弃本帧剩余时间量
                                break
                            else:
                                remaining = 0  # 枯等中
                                break
                        else:
                            v["waitingSince"] = None
                            v["onBoardOrders"].append(o)
                            if ao:
                                ao["state"] = "riding"
                            sim._log(
                                f"🚙 {v['id']} 接 [单{o['id']}] 乘客上车。", v["color"]
                            )
                    else:
                        v["onBoardOrders"] = [x for x in v["onBoardOrders"] if x["id"] != o["id"]]
                        sim.active_orders = [a for a in sim.active_orders if a["order"]["id"] != o["id"]]
                        sim._log(f"💵 {v['id']} 送 [单{o['id']}] 安全下榻。", "#10b981")

                    v["plannedRoute"] = v["plannedRoute"][1:]

                # ── 统一更新 lastNode 并弹出队列（与 demo.html 保持一致） ──
                v["lastNode"] = v["nextNode"]
                v["pathQueue"].pop(0)
                if not v["pathQueue"]:
                    v["nextNode"] = v["lastNode"]
            else:
                dx = (nex["node"]["x"] - v["x"]) / dist_canvas * move_pixel
                dy = (nex["node"]["y"] - v["y"]) / dist_canvas * move_pixel
                v["x"] += dx
                v["y"] += dy
                remaining = 0

    # ── 计算 ETA（复用 evaluateRoute 推演结果） ──
    all_picks: dict = {}
    all_arrs: dict = {}
    for v in sim.fleet:
        res = evaluate_route(sim, v["plannedRoute"], v)
        if res.get("pickT"):
            all_picks.update(res["pickT"])
        if res.get("arrT"):
            all_arrs.update(res["arrT"])

    # ── 序列化状态快照（只输出前端所需字段，Node 对象只保留 x/y/id） ──
    def slim_node(n: dict) -> dict:
        return {"id": n["id"], "x": n["x"], "y": n["y"]}

    fleet_snap = []
    for v in sim.fleet:
        pq_snap = [
            {"node": slim_node(q["node"]), "action": {"type": q["action"]["type"], "orderId": q["action"]["order"]["id"]} if q["action"] else None}
            for q in v["pathQueue"]
        ]
        route_snap = [
            {
                "type": s["type"],
                "order": {
                    "id": s["order"]["id"],
                    "pNode": slim_node(s["order"]["pNode"]),
                    "dNode": slim_node(s["order"]["dNode"]),
                }
            }
            for s in v["plannedRoute"]
        ]
        fleet_snap.append({
            "id": v["id"],
            "color": v["color"],
            "x": v["x"],
            "y": v["y"],
            "onBoardCount": len(v["onBoardOrders"]),
            "pathQueue": pq_snap,
            "plannedRoute": route_snap,
        })

    active_snap = []
    for ao in sim.active_orders:
        o = ao["order"]
        oid = o["id"]
        pick_remain = max(0.0, all_picks.get(oid, 0) - sim.sys_time)
        arr_remain = max(0.0, all_arrs.get(oid, 0) - sim.sys_time)
        active_snap.append({
            "orderId": oid,
            "vId": ao["vId"],
            "vColor": ao.get("vColor", "#888"),
            "state": ao["state"],
            "pickRemain": round(pick_remain, 1),
            "arrRemain": round(arr_remain, 1),
        })

    return {
        "sysTime": round(sim.sys_time, 2),
        "fleet": fleet_snap,
        "activeOrders": active_snap,
        "logs": sim.flush_logs(),
    }


# ──────────────────────────────────────────────
# 10. HTTP 服务层
# ──────────────────────────────────────────────

# 全局模拟器单例
_SIM: SimState | None = None


def get_sim() -> SimState:
    global _SIM
    if _SIM is None:
        print("🌍 正在初始化模拟器（加载 map_data.js）...")
        _SIM = SimState()
        print(f"✅ 地图加载完成：{len(_SIM.nodes)} 个节点，{len(_SIM.edges)} 条边，{len(_SIM.pois)} 个 POI。")
    return _SIM


class Handler(BaseHTTPRequestHandler):
    """轻量 HTTP 请求处理器。"""

    # 已启用默认请求日志辅助调试 (BaseHTTPRequestHandler)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str, content_type: str):
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        print(f"📥 收到 GET 请求: {self.path}")
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/demo_vis.html"):
            self._send_file("demo_vis.html", "text/html; charset=utf-8")
        elif path == "/map_data.js":
            self._send_file("map_data.js", "application/javascript; charset=utf-8")
        elif path == "/map_snapshot":
            # 返回地图静态数据供前端初始化
            sim = get_sim()
            nodes_slim = {
                nid: {"lon": n["lon"], "lat": n["lat"], "zone": n["zone"],
                      "is_poi": n["is_poi"], "x": n["x"], "y": n["y"]}
                for nid, n in sim.nodes.items()
            }
            self._send_json({
                "nodes": nodes_slim,
                "edges": sim.edges,
                "pois": sim.pois,
                "speed_mps": sim.SPEED,
            })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        sim = get_sim()

        if path == "/tick":
            dt = float(body.get("dt", 0.016))
            with sim._lock:
                state = tick(sim, dt)
            self._send_json(state)

        elif path == "/spawn_order":
            with sim._lock:
                generate_wild_order(sim)
                # 返回成功后全量状态
                state = tick(sim, 0.0)
            self._send_json(state)

        else:
            self._send_json({"error": "unknown endpoint"}, 404)


# ──────────────────────────────────────────────
# 11. 入口
# ──────────────────────────────────────────────

if __name__ == "__main__":
    host, port = "0.0.0.0", 8765
    # 预热模拟器
    get_sim()
    server = HTTPServer((host, port), Handler)
    print(f"\n🚀 demo 可视化后端已启动：http://localhost:{port}")
    print("   在浏览器打开上述地址即可查看演示页面。按 Ctrl+C 退出。\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务已停止。")
