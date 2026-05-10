# main.py
"""打车平台主干引导引擎与联调测试组合区。

由于业务全面切分到 models.py、core.py 与 auxiliary.py，
此模块现作为纯净的组装器，用于声明资源实例并统筹各个核心层级联动。
"""

import subprocess
import sys
import os

# 尝试并实现自动热加载安装 shapefile (pyshp)
try:
    import shapefile
except ImportError:
    print("检测到系统中缺失解析 shp 文件的模块 pyshp，正在为您自动拉取按装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyshp"])
    import shapefile
    print("pyshp 挂载成功！")

# 从独立分层的架构域导入各个组件
from models import CityGraph, Vehicle, Order, SPEED_MPS
from core import CoreDispatcher
from auxiliary import AuxiliaryFunctions

if __name__ == "__main__":
    print("调度系统后端节点启动初始化中...")
    
    # 步骤 1：启动数字路网引擎模型实例
    city = CityGraph("dxc_traffic_shp/dxc_rule.shp")
    
    # 步骤 2：分配运营配置、声明出勤车组队 (增至三台以适配三车指派中心)
    fleet = [
        Vehicle("巴士-绿色01", city.pois[0].id, "#10b981", zone=city.pois[0].zone),
        Vehicle("巴士-蓝色02", city.pois[12].id, "#3b82f6", zone=city.pois[12].zone),
        Vehicle("巴士-橙色03", city.pois[24].id, "#f59e0b", zone=city.pois[24].zone)
    ]
    
    # 注入业务元数据 (对应 3 个固定司机与车辆信息)
    fleet[0].driver_id, fleet[0].driver_no = "700045866645051565", "6800A145"
    fleet[0].vehicle_id, fleet[0].plate_no = "72057594546143661", "粤A00001"
    
    fleet[1].driver_id, fleet[1].driver_no = "700045866645052222", "6800B222"
    fleet[1].vehicle_id, fleet[1].plate_no = "72057594546144444", "粤A00002"
    
    fleet[2].driver_id, fleet[2].driver_no = "700045866645053333", "6800C333"
    fleet[2].vehicle_id, fleet[2].plate_no = "72057594546145555", "粤A00003"
    
    # 步骤 3：模拟野外乘客定位请求发送数据流
    # 格式：(上车经度, 上车纬度, 下车经度, 下车纬度)
    test_orders = []
    
    for idx, (plon, plat, dlon, dlat) in enumerate(test_orders, 1):
        o = Order(idx, plon, plat, dlon, dlat, req_time=0.0, city_map=city)
        CoreDispatcher.pool_and_route_planning(fleet, o, city) # 发起订单
        
    # 步骤 4：核心高级业务场景方法
    for v in fleet:
        if len(v.planned_route) == 0:
            CoreDispatcher.idle_parking_scenario(v, city)
        CoreDispatcher.stop_order_prediction(v)
    
    # 步骤 5：调取工具箱下电脱水导出作业，提供给前端 HTML 沙盘做演示引擎底座
    AuxiliaryFunctions.export_visualization_data(city, "map_data.js", fleet, speed_mps=SPEED_MPS)
    print("✅ 后端元数据与图论底座导出完成 (map_data.js)。")