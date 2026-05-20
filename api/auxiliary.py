# auxiliary.py
"""辅助业务层：提供并不涉及具体订单核心算法的基础套件工具箱。"""

import math
import json

class AuxiliaryFunctions:
    """系统的无状态辅助工具类，封装底层物理计算与通信脱水能力。"""
    
    # ============================================================
    # 功能一：地理距离计算
    # 相关方法：haversine_distance
    # ============================================================

    @staticmethod
    def haversine_distance(lon1, lat1, lon2, lat2):
        """通用地球球面距离测算框架（哈弗赛因公式）。
        
        用于计算两个经纬度坐标点之间的最短大圆路径距离。
        
        Args:
            lon1 (float): 起点经度。
            lat1 (float): 起点纬度。
            lon2 (float): 终点经度。
            lat2 (float): 终点纬度。
            
        Returns:
            float: 起结坐标之间的直线物理距离（米）。
        """
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    # ============================================================
    # 功能二：前端可视化数据导出
    # 相关方法：export_visualization_data
    # ============================================================

    @staticmethod
    def export_visualization_data(city_map, file_path="map_data.js", fleet=None, speed_mps=8.333):
        """路网结构与车队基础数据脱水工具。
        
        将后端的图网络、POI 站点以及车队初始位姿提取并转换成 JSONP 格式，
        供 HTML 前端框架（demo.html）进行高性能 Canvas 渲染使用。
        
        Args:
            city_map (CityGraph): 待导出的数字孪生城市路网对象。
            file_path (str, optional): 导出目标文件路径。默认为 "map_data.js"。
            fleet (list, optional): 需要挂载展示的 Vehicle 对象集合。
            speed_mps (float, optional): 前端仿真参考的物理限速（米/秒）。
            
        Returns:
            bool: 是否成功完成文件写入。
        """
        data = {
            "speed_mps": speed_mps,
            "nodes": { k: {"lon": v.lon, "lat": v.lat, "zone": v.zone, "is_poi": v.is_poi, "name": v.name} for k, v in city_map.nodes_map.items() },
            "edges": city_map.edges,
            "pois": [p.id for p in city_map.pois]
        }
        if fleet:
            data["fleet"] = [
                {
                    "id": v.id, 
                    "color": v.color, 
                    "start_node": v.last_node, 
                    "zone": v.op_zone,
                    "driver_id": v.driver_id,
                    "driver_no": v.driver_no,
                    "vehicle_id": v.vehicle_id,
                    "plate_no": v.plate_no
                } for v in fleet
            ]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("window.MAP_DATA = ")
            json.dump(data, f, ensure_ascii=False)
            f.write(";\n")
        print(f"[OK] 前端沙盘地形底座已被脱水导出至 {file_path}")
        return True


