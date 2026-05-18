import threading

from .models import CityGraph, Vehicle
from .core import CoreDispatcher


city = None
fleet = None
matching_thread = None
system_initialized = False


def init_system(shp_path="dxc_traffic_shp/dxc_rule.shp"):
    """加载路网、创建车队、启动后台匹配引擎。"""
    global city, fleet, matching_thread, system_initialized

    city = CityGraph(shp_path)

    fleet = [
        Vehicle("巴士-绿色01", city.pois[0].id, "#10b981", zone=city.pois[0].zone),
        Vehicle("巴士-蓝色02", city.pois[12].id, "#3b82f6", zone=city.pois[12].zone),
        Vehicle("巴士-橙色03", city.pois[24].id, "#f59e0b", zone=city.pois[24].zone),
    ]

    fleet[0].driver_id, fleet[0].driver_no = "700045866645051565", "6800A145"
    fleet[0].vehicle_id, fleet[0].plate_no = "72057594546143661", "粤A00001"

    fleet[1].driver_id, fleet[1].driver_no = "700045866645052222", "6800B222"
    fleet[1].vehicle_id, fleet[1].plate_no = "72057594546144444", "粤A00002"

    fleet[2].driver_id, fleet[2].driver_no = "700045866645053333", "6800C333"
    fleet[2].vehicle_id, fleet[2].plate_no = "72057594546145555", "粤A00003"

    for v in fleet:
        CoreDispatcher.refresh_vehicle_route_metadata(v, city)

    matching_thread = threading.Thread(
        target=CoreDispatcher.process_pool_matching,
        args=(fleet, city),
        daemon=True,
        name="OrderMatchingEngine",
    )
    matching_thread.start()

    system_initialized = True
