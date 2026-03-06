"""デスクトップ通知（win11toast / NOTIFY_DIR / ブラウザ）。"""
import json
import os
import platform
import time
import streamlit as st
import streamlit.components.v1 as components
import httpx

from .config import get_backend_url


def _notify_dir() -> str:
    notify_dir = ""
    try:
        from config import get_settings
        notify_dir = (get_settings().NOTIFY_DIR or "").strip()
    except Exception:
        pass
    if not notify_dir:
        notify_dir = (os.environ.get("NOTIFY_DIR") or "").strip()
    if not notify_dir and platform.system() == "Windows":
        # __file__ = .../app/ui/notifications.py → リポジトリルートは 3 段上（ui → app → ルート）
        _path = os.path.abspath(__file__)
        _project_root = os.path.dirname(os.path.dirname(os.path.dirname(_path)))
        notify_dir = os.path.join(_project_root, "notify_data")
    # Docker 内で NOTIFY_DIR が空のとき（.env で NOTIFY_DIR= にしている等）は /notify を使う
    if not notify_dir and os.path.exists("/.dockerenv"):
        notify_dir = "/notify"
    return notify_dir or ""


def write_notify_file(notify_type: str, title: str, body: str, **extra) -> None:
    """NOTIFY_DIR に通知 JSON を書き出す。watcher が win11toast で表示する。"""
    notify_dir = _notify_dir()
    if not notify_dir:
        return
    try:
        os.makedirs(notify_dir, exist_ok=True)
        path = os.path.join(notify_dir, f"notify_{int(time.time() * 1000)}.json")
        payload = {"type": notify_type, "title": title, "body": body}
        payload.update(extra)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass


def write_requirement_ready_notify(branch_name: str = "", backend_url: str = "") -> None:
    """「requirement.md を生成しますか？」を win11toast 用に NOTIFY_DIR に書き出す。承認・却下を Streamlit と連動させるため branch_name と backend_url を含める。"""
    write_notify_file(
        "requirement_ready",
        "requirement.md を生成しますか？",
        "ブランチ結果を確認し、requirement.md を生成できます。",
        branch_name=(branch_name or "").strip(),
        backend_url=(backend_url or get_backend_url()).strip(),
    )


def write_requirement_complete_notify(branch_name: str = "") -> None:
    """requirement.md 生成完了を win11toast 用に NOTIFY_DIR に書き出す。"""
    title = "requirement.md 生成完了"
    body = "requirement.md を生成しました。画面にて内容確認ください。"
    write_notify_file("requirement_complete", title, body)


def show_desktop_notification(
    title: str,
    body: str,
    branch_name: str,
    *,
    base_branch: str = "main",
    repo_path: str = "",
    backend_url: str = "",
) -> None:
    checkout_payload = {
        "branch_name": branch_name,
        "base_branch": (base_branch or "main").strip(),
        "repo_path": (repo_path or "").strip(),
        "backend_url": (backend_url or "").strip(),
    }
    backend_url_final = backend_url or get_backend_url()
    checkout_payload["backend_url"] = backend_url_final

    try:
        from win11toast import toast

        def on_toast_click(args):
            a = (args.get("arguments") or "")
            if "承認" not in a:
                return
            try:
                httpx.post(
                    f"{backend_url_final}/branch/checkout",
                    json={
                        "branch_name": branch_name,
                        "base_branch": checkout_payload["base_branch"],
                        "repo_path": checkout_payload["repo_path"] or None,
                    },
                    timeout=180.0,
                )
            except Exception:
                pass

        toast(
            title,
            body,
            duration="long",
            buttons=[
                {"activationType": "protocol", "arguments": "http:承認", "content": "承認"},
                {"activationType": "protocol", "arguments": "http:却下", "content": "却下"},
            ],
            on_click=on_toast_click,
        )
        st.toast(body, icon="✅", duration="long")
        return
    except Exception:
        pass

    notify_dir = _notify_dir()
    if notify_dir:
        try:
            os.makedirs(notify_dir, exist_ok=True)
            path = os.path.join(notify_dir, f"notify_{int(time.time() * 1000)}.json")
            payload = {"title": title, "body": body, "branch_name": branch_name}
            payload["base_branch"] = checkout_payload["base_branch"]
            payload["repo_path"] = checkout_payload["repo_path"]
            _backend_for_notify = ""
            try:
                from config import get_settings
                _backend_for_notify = (get_settings().NOTIFY_BACKEND_URL or "").strip()
            except Exception:
                pass
            if not _backend_for_notify:
                _backend_for_notify = (os.environ.get("NOTIFY_BACKEND_URL") or "").strip()
            if not _backend_for_notify:
                _backend_for_notify = checkout_payload.get("backend_url") or get_backend_url()
            if "backend" in (_backend_for_notify or ""):
                try:
                    from config import get_settings
                    _backend_for_notify = (get_settings().NOTIFY_BACKEND_URL or "http://localhost:8000").strip() or "http://localhost:8000"
                except Exception:
                    _backend_for_notify = os.environ.get("NOTIFY_BACKEND_URL", "http://localhost:8000").strip() or "http://localhost:8000"
            payload["backend_url"] = _backend_for_notify
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

    st.toast(body, icon="✅", duration="long")

    body_esc = json.dumps(body)[1:-1]
    title_esc = json.dumps(title)[1:-1]
    html = f"""
    <script>
    (function() {{
      var N = (window.top && window.top.Notification) ? window.top.Notification : (window.Notification || null);
      if (!N) return;
      function show() {{
        try {{
          new N({title_esc}, {{ body: {body_esc}, tag: "branch-ready" }});
        }} catch (e) {{}}
      }}
      if (N.permission === "granted") {{
        show();
      }} else if (N.permission === "default") {{
        N.requestPermission().then(function(p) {{ if (p === "granted") show(); }}).catch(function() {{}});
      }}
    }})();
    </script>
    """
    components.html(html, height=0)
