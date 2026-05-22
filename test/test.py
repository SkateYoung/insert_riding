import requests
import time

GAODE_KEY = "da290eeed6705c6c3f9621654d23bca6"

class GaodeMapAPI:
    def __init__(self, key):
        self.key = key
        self.base_url = "https://restapi.amap.com/v3"
        # 你的本地内存缓存
        self.distance_matrix = {} 

    def fetch_distance_matrix(self, origins, destinations):
        """
        批量获取真实路网的行驶距离和预计时间 (用于算法内部算账)
        origins/destinations 格式: "116.481028,39.989643|114.481028,39.989643"
        """
        url = f"{self.base_url}/distance"
        params = {
            "origins": origins,
            "destination": destinations,
            "key": self.key,
            "type": 1 # 1: 驾车路径
        }
        
        response = requests.get(url, params=params).json()
        
        if response.get("status") == "1":
            results = response.get("results", [])
            # 解析并存入本地缓存
            for res in results:
                origin_id = res['origin_id'] # 你可以自定义ID映射
                dest_id = res['dest_id']
                dist = int(res['distance'])
                duration = int(res['duration']) # 真实预计耗时(秒)，考虑了红绿灯！
                
                # 存在本地字典中
                self.distance_matrix[f"{origin_id}_{dest_id}"] = {
                    "dist": dist, 
                    "time": duration
                }
            return True
        return False

    def get_driving_route(self, origin, destination, waypoints=""):
        """
        获取具体的行驶轨迹坐标串 (用于算法出结果后，发给前端画图)
        origin: "经度,纬度"
        waypoints: 途经点，格式 "经度,纬度;经度,纬度"
        """
        url = f"{self.base_url}/direction/driving"
        params = {
            "origin": origin,
            "destination": destination,
            "waypoints": waypoints,
            "key": self.key,
            "extensions": "base" # 返回基本信息即可
        }
        
        response = requests.get(url, params=params).json()
        
        polyline_coords = []
        if response.get("status") == "1":
            paths = response['route']['paths']
            if paths:
                steps = paths[0]['steps']
                for step in steps:
                    # polyline 是一串经纬度，格式如 "116.48,39.99;116.49,39.98"
                    polylines = step['polyline'].split(';')
                    for point in polylines:
                        lon, lat = point.split(',')
                        polyline_coords.append({"lon": float(lon), "lat": float(lat)})
                        
        return polyline_coords

# ================= 测试代码 =================
if __name__ == "__main__":
    gaode = GaodeMapAPI(GAODE_KEY)
    gaode.distance_matrix()
    # 模拟算完路径后，获取轨迹给前端画图
    start = "116.481028,39.989643"
    end = "116.465302,40.004717"
    
    print("正在请求高德 API...")
    track_points = gaode.get_driving_route(start, end)
    print(f"获取到 {len(track_points)} 个轨迹点。你可以把这个 JSON 数组通过 WebSocket 发给前端。")
    print(track_points)