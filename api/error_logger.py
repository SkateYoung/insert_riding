# -*- coding: utf-8 -*-
"""系统错误日志写入工具。

该模块集中处理接口错误和算法内部异常的落盘记录，避免各业务文件
各自拼接日志格式。日志默认写入 runtime_logs/error_YYYYMMDD.txt。
"""

import json
import os
import threading
import traceback
from datetime import datetime
from pathlib import Path

try:  # Flask 仅在接口进程中可用，单元测试直接导入模块时允许缺失请求上下文。
    from flask import g, has_request_context, jsonify, request
    from werkzeug.exceptions import HTTPException
except Exception:  # pragma: no cover
    g = None
    request = None
    HTTPException = ()

    def has_request_context():
        return False

    def jsonify(payload):
        return payload


_LOG_LOCK = threading.RLock()
_MAX_TEXT_LENGTH = 4000


def _project_root():
    """返回项目根目录。"""
    return Path(__file__).resolve().parents[1]


def _safe_text(value, max_length=_MAX_TEXT_LENGTH):
    """把任意对象转换为适合写入 txt 的短文本。"""
    if value in (None, ""):
        return ""
    try:
        text = value if isinstance(value, str) else str(value)
    except Exception:
        text = repr(value)
    if len(text) > max_length:
        return text[:max_length] + "...<truncated>"
    return text


def _json_safe(value):
    """把上下文字段转换为 JSON 可序列化结构。"""
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except Exception:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item) for item in value]
        return _safe_text(value)


def _log_path():
    """计算当前错误日志文件路径。"""
    explicit_file = os.getenv("BUS_ERROR_LOG_FILE") or os.getenv("ERROR_LOG_FILE")
    if explicit_file:
        path = Path(explicit_file)
        return path if path.is_absolute() else _project_root() / path

    log_dir = os.getenv("BUS_ERROR_LOG_DIR") or os.getenv("ERROR_LOG_DIR") or "runtime_logs"
    directory = Path(log_dir)
    if not directory.is_absolute():
        directory = _project_root() / directory
    return directory / f"error_{datetime.now().strftime('%Y%m%d')}.txt"


def current_error_log_path():
    """返回当前错误日志文件绝对路径，供接口或排查时查看。"""
    return str(_log_path())


def request_context():
    """读取当前 Flask 请求上下文中的关键排查信息。"""
    if not has_request_context() or request is None:
        return {}
    context = {
        "method": request.method,
        "path": request.path,
        "query_string": request.query_string.decode("utf-8", errors="replace"),
        "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
        "user_agent": request.headers.get("User-Agent"),
    }
    try:
        body = request.get_data(cache=True, as_text=True) or ""
        if body:
            context["request_body"] = _safe_text(body)
    except Exception:
        pass
    return context


def log_error(source, message=None, exc=None, context=None, level="ERROR"):
    """写入一条错误日志。

    Args:
        source (str): 错误来源，例如 api.routes.create_order。
        message (str | None): 简短错误说明。
        exc (BaseException | None): 捕获到的异常对象；存在时写入 traceback。
        context (dict | None): 业务上下文，例如 vehicle_id、request_id。
        level (str): 日志级别文本。

    Returns:
        str | None: 成功时返回日志文件路径；写入失败时返回 None。
    """
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        merged_context = {}
        merged_context.update(request_context())
        if context:
            merged_context.update(context)

        lines = [
            "=" * 88,
            f"time: {timestamp}",
            f"level: {level}",
            f"source: {_safe_text(source)}",
        ]
        if message:
            lines.append(f"message: {_safe_text(message)}")
        if merged_context:
            lines.append("context: " + json.dumps(_json_safe(merged_context), ensure_ascii=False, default=str))
        if exc is not None:
            lines.append("exception: " + repr(exc))
            lines.append("traceback:")
            lines.append("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())
        lines.append("")

        with _LOG_LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
                handle.write("\n")
        return str(path)
    except Exception:
        return None


def log_exception(source, exc, context=None, message=None):
    """记录捕获到的异常堆栈。"""
    return log_error(source, message=message or str(exc), exc=exc, context=context, level="ERROR")


def log_api_response_error(response):
    """记录已被接口正常返回的 4xx/5xx 错误响应。"""
    try:
        if response.status_code < 400:
            return response
        if has_request_context() and g is not None and getattr(g, "_exception_error_logged", False):
            return response
        body = response.get_data(as_text=True) if hasattr(response, "get_data") else ""
        log_error(
            "flask.response",
            message=f"HTTP {response.status_code}",
            context={
                "status_code": response.status_code,
                "response_body": _safe_text(body),
            },
            level="WARNING" if response.status_code < 500 else "ERROR",
        )
    except Exception:
        pass
    return response


def install_flask_error_logging(app):
    """为 Flask 应用安装接口错误日志钩子。"""

    @app.errorhandler(Exception)
    def _log_unhandled_exception(exc):
        """记录未被业务路由捕获的异常，并返回统一 JSON。"""
        if isinstance(exc, HTTPException):
            return jsonify({
                "error": getattr(exc, "name", "http_error"),
                "message": getattr(exc, "description", str(exc)),
            }), int(getattr(exc, "code", None) or 500)
        log_exception("flask.unhandled_exception", exc)
        if g is not None:
            g._exception_error_logged = True
        return jsonify({"error": "internal_server_error", "message": str(exc)}), 500

    @app.after_request
    def _log_error_response(response):
        """记录所有返回给前端的错误响应。"""
        return log_api_response_error(response)

    return app
