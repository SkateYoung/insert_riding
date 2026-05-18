"""打车平台 Flask 启动入口。

main.py 只负责创建应用、注册路由、初始化系统和启动服务。
"""

import os
import subprocess
import sys

try:
    import shapefile  # noqa: F401
except ImportError:
    print("检测到系统中缺失解析 shp 文件的模块 pyshp，正在为您自动安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyshp"])

from flask import Flask

from api import state
from api.routes import bp as api_routes


def create_app():
    """创建 Flask 应用并注册 API 路由。"""
    app = Flask(__name__)
    app.register_blueprint(api_routes)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    return app


app = create_app()


if __name__ == "__main__":
    print("调度系统后端节点启动初始化中...")
    try:
        state.init_system()
        print(f"[系统] 路网加载完成：{len(state.city.nodes_map)} 节点，{len(state.city.pois)} POI")
        print("[系统] 后台统筹派单引擎已在独立线程启动。")
    except Exception as e:
        print(f"[警告] 自动初始化失败: {e}")
        print("[提示] 可通过 POST /init 手动初始化")

    port = int(os.environ.get("PORT", 5000))
    print(f"\n[OK] Flask API 已就绪: http://localhost:{port}")
    print("   可用端点: /health /init /order /fleet /fleet/<vehicle_id>/path /orders/pool /status /tick /export /pois /map/road-network\n")
    app.run(host="0.0.0.0", port=port, debug=False)
