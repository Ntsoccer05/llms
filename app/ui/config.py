"""バックエンド接続先の取得。"""
import os


def _is_likely_docker() -> bool:
    if os.path.exists("/.dockerenv"):
        return True
    return bool(os.environ.get("KUBERNETES_SERVICE_HOST") or os.environ.get("CONTAINER") == "true")


def _backend_port() -> int:
    try:
        from config import get_settings
        return get_settings().BACKEND_PORT
    except Exception:
        return int(os.environ.get("BACKEND_PORT", "8000"))


def get_backend_url() -> str:
    host = (os.environ.get("BACKEND_HOST") or "").strip()
    if not host:
        try:
            from config import get_settings
            host = (get_settings().BACKEND_HOST or "").strip()
        except Exception:
            pass
    port = _backend_port()
    if _is_likely_docker() and host:
        return f"http://{host}:{port}"
    url = (os.environ.get("BACKEND_URL") or "").strip()
    if not url:
        try:
            from config import get_settings
            url = (get_settings().BACKEND_URL or "").strip()
        except Exception:
            pass
    if url:
        return url
    if host:
        return f"http://{host}:{port}"
    return f"http://localhost:{port}"
