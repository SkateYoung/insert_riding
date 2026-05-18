# Flask Blueprint 说明

## 1. 为什么使用 Blueprint

`Blueprint` 是 Flask 用来拆分路由模块的机制。

之前所有接口都写在 `main.py` 中，文件会越来越长，也会把“启动服务”和“业务接口”混在一起。现在把路由拆到 `api/routes.py` 后，`main.py` 只负责启动 Flask，接口逻辑集中放在单独文件中，结构更清楚。

## 2. 当前项目中的文件分工

### `main.py`

只负责服务启动：

- 创建 Flask 应用
- 注册 `Blueprint`
- 添加 CORS 响应头
- 启动时初始化系统
- 执行 `app.run(...)`

核心代码类似：

```python
from flask import Flask
from api.routes import bp as api_routes

def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_routes)
    return app

app = create_app()
```

### `api/routes.py`

负责 API 路由：

- `/health`
- `/init`
- `/order`
- `/fleet`
- `/fleet/<vehicle_id>/path`
- `/orders/pool`
- `/status`
- `/tick`
- `/export`
- `/pois`
- `/map/road-network`

核心代码类似：

```python
from flask import Blueprint

bp = Blueprint("api_routes", __name__)

@bp.route("/health", methods=["GET"])
def health():
    ...
```

注意这里使用的是 `@bp.route(...)`，不是 `@app.route(...)`。

### `api/state.py`

负责保存运行时状态：

- `city`
- `fleet`
- `matching_thread`
- `system_initialized`
- `init_system(...)`

路由文件通过 `api.state` 读取或更新这些状态。

## 3. 请求流转方式

请求进入 Flask 后，大致流程是：

```text
浏览器/客户端
    ↓
main.py 创建的 Flask app
    ↓
app.register_blueprint(api_routes)
    ↓
api/routes.py 中对应的接口函数
    ↓
api/state.py 中的 city、fleet 等运行状态
    ↓
api/core.py、api/models.py、api/auxiliary.py
```

例如：

```text
POST /fleet/<vehicle_id>/path
    ↓
api/routes.py:update_vehicle_path
    ↓
api/core.py:CoreDispatcher.rebuild_vehicle_path_from_gps(...)
    ↓
返回更新后的路网轨迹点
```

## 4. 后续如何新增接口

新增接口时，优先放在 `api/routes.py`。

示例：

```python
@bp.route("/example", methods=["GET"])
def example():
    return jsonify({"status": "ok"})
```

如果接口需要访问全局状态，从 `api.state` 读取：

```python
from . import state

@bp.route("/fleet/count", methods=["GET"])
def fleet_count():
    if not state.system_initialized:
        return jsonify({"error": "系统未初始化"}), 400
    return jsonify({"count": len(state.fleet)})
```

如果是算法逻辑，不建议直接写在 `api/routes.py`，应放到：

- `api/core.py`：调度、路径、订单分配等核心算法
- `api/models.py`：实体模型
- `api/auxiliary.py`：通用工具函数

`api/routes.py` 应尽量只做：

- 读取请求参数
- 校验参数
- 调用业务函数
- 返回 JSON

## 5. Blueprint 的好处

- `main.py` 更短，只负责启动。
- 路由集中在 `api/routes.py`，更容易查找接口。
- 全局状态集中在 `api/state.py`，避免到处散落。
- 后续可以继续拆分多个 Blueprint，例如：
  - `vehicle_routes`
  - `order_routes`
  - `map_routes`

## 6. 注意事项

不要在 `api/routes.py` 中导入 `main.py`。

这样容易造成循环导入：

```text
main.py 导入 api.routes
api.routes 又导入 main.py
```

正确做法是：

```python
from . import state
```

通过 `api/state.py` 共享运行状态。

