# models.py
"""物理域实体数据模型层。
包含地标节点、城市图理论路网抽象、打车订单及运营实体的标准组件。
"""

import os
import random
import heapq
from auxiliary import AuxiliaryFunctions

# 尝试并实现自动热加载安装 shapefile (pyshp)
HAS_SHAPEFILE = False
try:
    import shapefile
    HAS_SHAPEFILE = True
except ImportError:
    pass

# 常量定义
SPEED_KMH = 60
SPEED_MPS = SPEED_KMH * 1000.0 / 3600.0   # 平均推演物理时速：8.33 m/s (同步 JS 设定)

class Node:
    """地图上的路网几何节点模型对象。
    
    代表着街道路口、死角终端或是弯折转角点。
    
    Args:
        node_id (str): 节点的绝对全球唯一识别 ID，本项目默认由六位经纬度拼接而来作为标识串。
        lon (float): 该点的经度(Longitude)。
        lat (float): 该点的纬度(Latitude)。
        
    Attributes:
        neighbors (dict): 双向/单向路径的连通边对象集，存储着目标相邻节点的 ID 键及其物理长度距离(米)。
        zone (int): 该点所属的大行政辖区标号（1/2/3区）。
        is_poi (bool): 是否为主干算法评估后最终选作的“标准合法上下客POI站点”。
    """
    def __init__(self, node_id, lon, lat):
        """路网节点实例化构造器。
        
        Args:
            node_id (str): 节点的全球唯一识别标识串。
            lon (float): 节点所在的经度坐标。
            lat (float): 节点所在的纬度坐标。
        """
        self.id = node_id
        self.lon = lon
        self.lat = lat
        self.name = f"普通路点 {node_id}" # 默认名称
        self.neighbors = {}
        self.zone = 0
        self.is_poi = False

    def __str__(self):
        return f"Node_{self.id}({self.zone}区)"


class CityGraph:
    """数字孪生世界路图抽象框架。
    
    封装了庞大的 shapefile 读取机制、生成真实世界映射图、生成 POI 等全套功能。
    
    Args:
        shp_path (str): 目标基础路网地图数据的位置源。
    """
    def __init__(self, shp_path="zsc_shp/ditu_gcj02_ln.shp"):
        """路网引擎初始化构造器。
        
        负责读取 SHP 文件并构建内存级图论拓扑结构，同时执行连通组件提取与 POI 采样。
        
        Args:
            shp_path (str, optional): SHP 文件路径。默认为 "zsc_shp/ditu_gcj02_ln.shp"。
        """
        self.nodes_map = {}
        self.edges = []
        self.pois = []
        self.path_cache = {} # 路径评估高速缓存，key: "start_node_id|end_node_id"
        
        print("开始解析基础 SHP 空间路网数据...")
        if not os.path.exists(shp_path):
            raise FileNotFoundError(f"找不到关键的 SHP 地理数据集: {shp_path}")
            
        sf = shapefile.Reader(shp_path)
        
        def get_id(pt):
            return f"{pt[0]:.6f}_{pt[1]:.6f}"
            
        for sr in sf.shapeRecords():
            pts = sr.shape.points
            if len(pts) < 2: continue
            
            for i in range(len(pts)):
                uid = get_id(pts[i])
                if uid not in self.nodes_map:
                    self.nodes_map[uid] = Node(uid, pts[i][0], pts[i][1])
                    
            # 获取本路段全局交规方向限定（FT = 从头到尾的单行道, B = 兼容双向线）
            oneway_rule = sr.record.as_dict().get('Oneway', 'B')
            
            # 建立遵守真实交规的图论连通度
            for i in range(len(pts)-1):
                id1 = get_id(pts[i])
                id2 = get_id(pts[i+1])
                n1 = self.nodes_map[id1]
                n2 = self.nodes_map[id2]
                
                dist = AuxiliaryFunctions.haversine_distance(n1.lon, n1.lat, n2.lon, n2.lat)
                
                # 法则1: 多段线的点序本身即代表法定行进正方向 (FT通途), 必定建立图论有向边
                if id2 not in n1.neighbors:
                    n1.neighbors[id2] = dist
                    self.edges.append({"u": id1, "v": id2, "dist": dist})
                    
                # 法则2: 严打交规逆行！只有在该道路属于双向车道 (B) 时，才准许合法建立反向有向边 
                if oneway_rule == 'B':
                    if id1 not in n2.neighbors:
                        n2.neighbors[id1] = dist
                        self.edges.append({"u": id2, "v": id1, "dist": dist})
                    
        self._keep_largest_connected_component()
        print(f"[OK] 孤立死角剔除，连接图建立成功！有效节点: {len(self.nodes_map)}个。")
        
        # 简单经线切割三区域
        sorted_nodes = sorted(list(self.nodes_map.values()), key=lambda n: n.lon)
        n_count = len(sorted_nodes)
        z1 = sorted_nodes[:n_count//3]
        z2 = sorted_nodes[n_count//3:2*n_count//3]
        z3 = sorted_nodes[2*n_count//3:]
        for n in z1: n.zone = 1
        for n in z2: n.zone = 2
        for n in z3: n.zone = 3
        
        # ======  30 个固定坐标 ======
        target_coords = [
            (113.400432, 23.058342), (113.408249, 23.059654), (113.409279, 23.059181),
            (113.410918, 23.056409), (113.408958, 23.055814), (113.403476, 23.056747),
            (113.403402, 23.052397), (113.403426, 23.045208), (113.397930, 23.047002),
            (113.395399, 23.044034), (113.394788, 23.036643), (113.376318, 23.038370),
            (113.366185, 23.039608), (113.353567, 23.040831), (113.360126, 23.044599),
            (113.366346, 23.043228), (113.363934, 23.048971), (113.365738, 23.054616),
            (113.371203, 23.054979), (113.371864, 23.060934), (113.376951, 23.064815),
            (113.382411, 23.064052), (113.393363, 23.062182), (113.396898, 23.063383),
            (113.386289, 23.056230), (113.390231, 23.046660), (113.385723, 23.050278),
            (113.374612, 23.046061), (113.386851, 23.060300)
        ]
        
        self.pois = []
        # 由于手动输入的坐标可能无法直接命中路网节点，在此执行最近邻节点归位
        all_graph_nodes = list(self.nodes_map.values())
        unique_poi_ids = set()
        
        for lon, lat in target_coords:
            best_n = None
            min_d = float('inf')
            # 暴力遍历寻找最近点，由于 POI 数量极少且仅执行一次，性能开销可忽略
            for n in all_graph_nodes:
                d = AuxiliaryFunctions.haversine_distance(lon, lat, n.lon, n.lat)
                if d < min_d:
                    min_d = d
                    best_n = n
            
            if best_n and best_n.id not in unique_poi_ids:
                best_n.is_poi = True
                self.pois.append(best_n)
                unique_poi_ids.add(best_n.id)

        self._assign_poi_names()
        print(f"[OK] POIs 固定加载成功！共映射到 {len(self.pois)} 个唯一路网节点并分配了名称。")

    def _assign_poi_names(self):
        """为所有 POI 站点分配具有业务感的随机名称。"""
        prefixes = ["科技园", "大学城", "商业街", "创新大厦", "体育馆", "图书馆", "地铁站", "公寓区", "实验楼", "中心广场"]
        secondary = ["南门", "北门", "东门", "西门", "A座", "B座", "二期", "分馆", "广场", "枢纽"]
        
        random.seed(42) # 保证名称在不同运行间保持一致
        p_list = prefixes.copy()
        s_list = secondary.copy()
        random.shuffle(p_list)
        random.shuffle(s_list)
        
        for i, poi in enumerate(self.pois):
            p = prefixes[i % len(prefixes)]
            s = secondary[(i // len(prefixes)) % len(secondary)]
            poi.name = f"{p}{s}"

    def _keep_largest_connected_component(self):
        """路网图脱水：仅保留图中最大的通车区块阵列，剔除所有的离岛孤岛避免寻路黑洞。
        
        该算法通过广度优先搜索 (BFS) 识别图中所有的强连通分量，并只保留规模最大的那个。
        
        Returns:
            None
        """
        visited = set()
        ccs = []
        all_ids = list(self.nodes_map.keys())
        for start_id in all_ids:
            if start_id not in visited:
                cc = []
                q = [start_id]
                visited.add(start_id)
                while q:
                    curr = q.pop()
                    cc.append(curr)
                    for nbr in self.nodes_map[curr].neighbors:
                        if nbr not in visited:
                            visited.add(nbr)
                            q.append(nbr)
                ccs.append(cc)
        largest_cc = max(ccs, key=len)
        allowed = set(largest_cc)
        
        keys_to_del = [k for k in self.nodes_map if k not in allowed]
        for k in keys_to_del:
            del self.nodes_map[k]
        
        new_edges = []
        for e in self.edges:
            if e['u'] in allowed and e['v'] in allowed:
                new_edges.append(e)
        self.edges = new_edges

    def get_path(self, start_node, end_node):
        """A* (A-Star) 全局最短路径推演扫描算子。
        
        提供从目标起终点的逐级地理网格渗透式搜索，并带有结果缓存机制。
        
        Args:
            start_node (Node): 在线车体目前所在的最近拓扑顶点。
            end_node (Node): 将要驶向的目标打车定位点。
            
        Returns:
            tuple: (全行程最低距离(米), Node对象数组路径)
        """
        cache_key = f"{start_node.id}|{end_node.id}"
        if cache_key in self.path_cache:
            return self.path_cache[cache_key]

        if start_node == end_node:
            return 0.0, [start_node]
            
        open_set = []
        heapq.heappush(open_set, (0.0, 0, start_node.id))
        came_from = {}
        g_score = {start_node.id: 0.0}
        
        counter = 1
        while open_set:
            f, _, curr_id = heapq.heappop(open_set)
            
            if curr_id == end_node.id:
                path = []
                curr = curr_id
                while curr in came_from:
                    path.append(self.nodes_map[curr])
                    curr = came_from[curr]
                path.append(start_node)
                path.reverse()
                res = (g_score[curr_id], path)
                self.path_cache[cache_key] = res
                return res
                
            curr_node = self.nodes_map[curr_id]
            for nbr_id, dist in curr_node.neighbors.items():
                tentative_g = g_score[curr_id] + dist
                if nbr_id not in g_score or tentative_g < g_score[nbr_id]:
                    came_from[nbr_id] = curr_id
                    g_score[nbr_id] = tentative_g
                    nbr_node = self.nodes_map[nbr_id]
                    # Heuristic A* 评估法：到目标坐标的物理鸟瞰直线开销
                    h = AuxiliaryFunctions.haversine_distance(nbr_node.lon, nbr_node.lat, end_node.lon, end_node.lat)
                    f_val = tentative_g + h
                    heapq.heappush(open_set, (f_val, counter, nbr_id))
                    counter += 1
                    
        res = (float('inf'), [])
        self.path_cache[cache_key] = res
        return res


class Order:
    """系统乘客订单信令容器。
    
    在构建体实例化期间会强行触发野坐标向着主街POI点的并轨吸附。
    
    Args:
        order_id (int|str): 平台派发给该乘客的专属单号。
        random_p_lon (float): GPS 发射位置源：原始经度。
        random_p_lat (float): GPS 发射位置源：原始纬度。
        random_d_lon (float): 指向终点的下车原始经度。
        random_d_lat (float): 指向终点的下车原始纬度。
        req_time (float): 触发呼叫按下的时间戳。
        city_map (CityGraph): 提供 POI 校准纠偏的参考系。
    """
    def __init__(self, order_id, random_p_lon, random_p_lat, random_d_lon, random_d_lat, req_time, city_map):
        """乘客订单实例化构造器。
        
        负责将经纬度随机位置吸附并对齐到路网 POI 站点，同时推算 SLA 等各项业务指标。
        
        Args:
            order_id (int|str): 订单唯一标识 ID。
            random_p_lon (float): 上车点原始经度。
            random_p_lat (float): 上车点原始纬度。
            random_d_lon (float): 下车点原始经度。
            random_d_lat (float): 下车点原始纬度。
            req_time (float): 呼叫订单发起的物理系统时间。
            city_map (CityGraph): 参与站点吸附校验的地图实例。
        """
        self.id = order_id
        self.req_time = req_time
        
        def nearest_poi(lon, lat):
            best = None
            best_dist = float('inf')
            for p in city_map.pois:
                d = AuxiliaryFunctions.haversine_distance(lon, lat, p.lon, p.lat)
                if d < best_dist:
                    best_dist = d
                    best = p
            return best
            
        self.p_node = nearest_poi(random_p_lon, random_p_lat)
        self.d_node = nearest_poi(random_d_lon, random_d_lat)
        
        # ------ 同步 JS 算法参数：超时缓冲与爽约验证属性 ------
        self.passenger_max_wait = 1800.0  # 乘客可最高容忍接力等车时隙：30 分钟 (同步 JS 设定)
        self.vehicle_max_wait = 180.0    # 车辆最高容忍路边原地干等时隙：3 分钟
        
        # 乘客准备就绪时间（正态拟合随机步入时间）
        self.passenger_ready_time = self.req_time + random.uniform(0, 10.0) # 同步 JS generateWildOrder 中的 10s 步行时间
        
        # ------ 新增 SLA 时间窗限制 ------
        self.max_pickup_time = self.req_time + self.passenger_max_wait
        
        # 直达里程推演（用于计算最晚送达时间）
        direct_dist, _ = city_map.get_path(self.p_node, self.d_node)
        direct_time = direct_dist / SPEED_MPS
        self.max_arrival_time = self.max_pickup_time + direct_time * 2.0 + 300.0
        
        # 核心追加：真实接人时间点（记录于物理仿真抵达接客点瞬间），用于后续成本推演防 NaN
        self.actual_pick_time = None
        
        # ------ 新增用于落库统计的模板字段 ------
        import datetime
        self.stats_date = datetime.date.today().strftime("%Y-%m-%d")
        self.status = ""
        self.journey_id = ""
        self.merchant_name = ""
        self.op_zone = ""
        self.driver_id = ""
        self.driver_no = ""
        self.vehicle_id = ""
        self.plate_no = ""
        self.passenger_id = ""
        self.answer_time = None
        self.completion_time = None
        self.cancel_type = ""
        self.cancel_time = None
        self.passenger_count = 1
        self.actual_pickup_dist = 0.0
        self.actual_pickup_duration = 0.0
        self.passenger_billing_duration = 0.0
        self.loaded_dist = 0.0

    def to_dict(self):
        """将订单转换为结构化模板字典，用于落库存档与分析。"""
        # 计算时速 (m/s 转换成 km/h, 1 m/s = 3.6 km/h)
        # 注意这里的 duration 以分钟为单位，需换算成秒 (duration * 60)
        avg_pickup_speed = 0.0
        if self.actual_pickup_duration > 0:
            avg_pickup_speed = (self.actual_pickup_dist / (self.actual_pickup_duration * 60.0)) * 3.6
            
        avg_dropoff_speed = 0.0
        if self.passenger_billing_duration > 0:
            avg_dropoff_speed = (self.loaded_dist / (self.passenger_billing_duration * 60.0)) * 3.6

        return {
            "统计日期": self.stats_date,
            "订单id": self.id,
            "订单状态": self.status,
            "行程id": self.journey_id,
            "商户名称": self.merchant_name,
            "运营区域": self.op_zone,
            "起点名称": self.p_node.name if self.p_node else "",
            "终点名称": self.d_node.name if self.d_node else "",
            "司机id": self.driver_id,
            "司机工号": self.driver_no,
            "车辆id": self.vehicle_id,
            "车牌号": self.plate_no,
            "乘客id": self.passenger_id,
            "呼单时间": self.req_time,
            "应答时间": self.answer_time,
            "上客时间": self.actual_pick_time,
            "完单时间": self.completion_time,
            "取消类型": self.cancel_type,
            "取消时间": self.cancel_time,
            "发单乘客人次": self.passenger_count,
            "实际接驾里程(米)": round(self.actual_pickup_dist, 2),
            "实际接驾时长(分钟)": round(self.actual_pickup_duration, 2),
            "乘客计费时长(分钟)": round(self.passenger_billing_duration, 2),
            "载客里程(米)": round(self.loaded_dist, 2),
            "送驾平均时速(千米/小时)": round(avg_dropoff_speed, 2),
            "接驾平均时速(千米/小时)": round(avg_pickup_speed, 2)
        }


class Vehicle:
    """载荷车体对象载体抽象结构。
    
    记录行驶阶段中的运力容量与行程状态表列。
    
    Args:
        v_id (str): 车牌系统内部串行号或自编号。
        start_node (str|Node对象的主键): 最初始化被挂载入库进入服务状态的点。
        color (str): 前端展示时向外透传的底漆 HEX。
        zone (int): 该车归属的车队原籍驻地标签。
        capacity (int, optional): 座位载客量定额。默认为 10 大巴制。
    """
    def __init__(self, v_id, start_node, color, zone, capacity=10):
        """物理车辆载体实例化构造器。
        
        Args:
            v_id (str): 车辆唯一标识 ID。
            start_node (Node): 车辆初始被挂载部署的拓扑节点。
            color (str): 车辆在前端 UI 中的渲染色。
            zone (int): 车辆原籍所在的运营辖区。
            capacity (int, optional): 车辆定额载客量上限。默认为 10。
        """
        self.id = v_id
        self.color = color
        self.op_zone = zone 
        self.capacity = capacity
        
        # 运营元数据 (由 main.py 分配)
        self.driver_id = ""
        self.driver_no = ""
        self.vehicle_id = ""
        self.plate_no = ""
        
        self.time = 0.0                    
        self.on_board_orders = []          
        self.planned_route = []            
        
        self.last_node = start_node
        self.next_node = start_node
        self.progress = 0.0
        
        # 新增状态机：疲劳监控与休眠状态
        self.driving_time = 0.0
        self.is_rest_requested = False
        self.is_resting = False
        self.rest_timer = 0.0

    def tick(self, dt: float):
        """推进载体物理环境内部时钟与疲劳累加判断机制。
        
        供仿真主引擎（物理帧渲染时）统一驱使调用：
        如果本车正停在路边大休闭关沉睡，它的 driving_time 被剥离冻结。
        若连续开车达到 10 分钟 (600s)，触发强制罢工熔断预警锁锁死系统派单源，
        清空现有债客后遁入安全避风港深眠 5 分钟 (300) 后出关复工。
        
        Args:
            dt (float): 经过的物理推演真实步进时间（秒）。
        """
        # ============== 疲劳与休息状态机时钟管理 ==============
        if self.is_resting:
            # 当车在休息状态下，不累计驾驶时间，停止物理移动，专注累加休息倒数机制
            self.rest_timer += dt
            if self.rest_timer >= 300.0: # 满 5 分钟充能完毕
                self.is_resting = False
                self.is_rest_requested = False
                self.rest_timer = 0.0
                self.driving_time = 0.0 # 完全洗去疲劳值
                print(f"[Vehicle.Sleep] ☀️ {self.id} 休整五分钟完毕！满血重归调度池。")
            return
            
        # 仅当车辆处于【接单干活状态】时，才累加存续行驶时间
        if len(self.on_board_orders) > 0 or len(self.planned_route) > 0:
            self.driving_time += dt
            
        # 极限工态疲劳触发器 (600s = 10分钟)
        if self.driving_time > 600.0 and not self.is_rest_requested:
            self.is_rest_requested = True
            print(f"[Vehicle.Warning] ⚠️ {self.id} 驾驶超限10分钟！已被系统强制开启疲劳监控，下线预备休息。")
            
        # 收车预备 -> 正式深睡沉淀 判定：身上再无接驳负债
        if self.is_rest_requested and len(self.on_board_orders) == 0 and len(self.planned_route) == 0:
            self.is_resting = True
            self.rest_timer = 0.0
            print(f"[Vehicle.Sleep] 🌙 {self.id} 运力释放完毕，进入深睡阶段。")
