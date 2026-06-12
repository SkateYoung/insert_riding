"""打车平台 Flask 启动入口。

main.py 只负责创建应用、注册路由、初始化系统和启动服务。
"""

import os
import subprocess
import sys

# ============================================================
# 功能一：启动前依赖检测
# 相关内容：pyshp 自动安装
# ============================================================

try:
    import shapefile  # noqa: F401
except ImportError:
    print("检测到系统中缺失解析 shp 文件的模块 pyshp，正在为您自动安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyshp"])

from flask import Flask

from api import state
from api.routes import bp as api_routes


# ============================================================
# 功能二：Flask 应用创建与蓝图注册
# 相关方法：create_app、add_cors_headers
# ============================================================

def create_app():
    """创建 Flask 应用实例并挂载 API 蓝图。

    Args:
        None。

    Returns:
        Flask: 已注册业务路由和跨域响应头处理器的 Flask 应用。
    """
    app = Flask(__name__)
    app.register_blueprint(api_routes)

    @app.after_request
    def add_cors_headers(response):
        """为所有接口响应追加跨域访问头。

        Args:
            response (flask.Response): Flask 即将返回给客户端的响应对象。

        Returns:
            flask.Response: 已追加 CORS 头的同一个响应对象。
        """
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    return app


app = create_app()


# ============================================================
# 功能三：本地运行启动入口
# 相关内容：初始化路网、启动后台线程、监听端口
# ============================================================

if __name__ == "__main__":
    print("调度系统后端节点启动初始化中...")
    try:
        state.init_system()
        print(f"[系统] 路网加载完成：{len(state.city.nodes_map)} 节点，{len(state.city.pois)} POI")
        print("[系统] 后台统筹派单引擎、真实时间时钟、路线纠偏与订单 ETA 刷新线程已启动。")
    except Exception as e:
        print(f"[警告] 自动初始化失败: {e}")
        print("[提示] 可通过 POST /init 手动初始化")

    port = int(os.environ.get("PORT", 5000))
    print(f"\n[OK] Flask API 已就绪: http://localhost:{port}")
    print("   可用端点: /health /time /init /order /orders/<request_id>/eta /orders/<request_id>/cancel /fleet /fleet/<vehicle_id>/path /fleet/<vehicle_id>/rest /orders/pool /status /tick /export /pois /map/road-network\n")
    app.run(host="0.0.0.0", port=port, debug=False)
