"""HITL ワークフロー用の UI 部品・バックエンド呼び出しヘルパー。"""
import fnmatch
import json
import os
import time
import streamlit as st
import streamlit.components.v1 as components
import httpx

from ui.config import get_backend_url
from ui.notifications import (
    show_desktop_notification,
    write_requirement_complete_notify,
    write_requirement_ready_notify,
)
from ui.states import clear_hitl_state


def gitignore_roots():
    _file = os.path.abspath(__file__)
    _workflows = os.path.dirname(_file)
    _ui = os.path.dirname(_workflows)
    _app = os.path.dirname(_ui)
    _project = os.path.dirname(_app)
    return [_project, _app, os.getcwd(), _workflows]


def filter_uploaded_by_gitignore(uploaded_dir):
    if not uploaded_dir:
        return uploaded_dir
    try:
        patterns = []
        for root in gitignore_roots():
            path = os.path.join(root, ".gitignore")
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip().split("#")[0].strip()
                        if line and not line.startswith("!"):
                            patterns.append(line.rstrip("/"))
                break
        if not patterns:
            patterns = [
                ".env", "__pycache__", "*.pyc", "*.pyo", "*.pyd",
                ".venv", "venv", "env", "notify_data", ".idea", ".vscode", ".DS_Store", "*.log",
            ]

        def should_ignore(path: str) -> bool:
            if not path:
                return False
            p = path.replace("\\", "/").strip("/")
            parts = [x for x in p.split("/") if x]
            base = parts[-1] if parts else ""
            if base == ".env" or p.endswith("/.env"):
                return True
            for pat in patterns:
                if not pat:
                    continue
                if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(base, pat):
                    return True
                if pat in parts or pat == base:
                    return True
                if "/" + pat in p or p.endswith("/" + pat) or "\\" + pat in p:
                    return True
            return False

        return [f for f in uploaded_dir if not should_ignore(getattr(f, "name", "") or "")]
    except Exception:
        return uploaded_dir


def render_notification_help():
    """通知の出し方の説明 expander。"""
    with st.expander("🔔 ブラウザを閉じても PC に通知を出す方法"):
        st.caption(
            "**Windows で Streamlit をローカル実行している場合** — まず **watcher を起動したまま**にしてください。"
            "通知はプロジェクト直下の `notify_data` に書き出され、watcher が PC にトースト表示します（ブラウザを閉じていても表示されます）。"
        )
        st.caption(
            "**Docker で実行している場合** — 同じく **watcher を起動したまま**にすると、"
            "コンテナが `notify_data` に書き出した通知を watcher が表示します。"
        )
        st.markdown("""
このリポジトリの **docker-compose** では `./notify_data` を **NOTIFY_DIR** でマウント済みです。

**初回だけ（どちらか一方でOK）**
- **スタートアップに登録**（おすすめ）: `scripts\\\\install_watcher_startup.bat` をダブルクリックで実行すると、PC 起動時に watcher が自動で動きます。
- **手動で 1 回起動**: プロジェクトルートで `python scripts/win_notify_watcher.py notify_data` を実行し、そのターミナルは閉じずにそのままにしておく。

（事前に `pip install win11toast` が必要です）

**通知が来ない場合の確認:**  
① watcher 起動時に「Notify watcher started」のトーストが 1 回出れば watcher と win11toast は動いています。  
② **Docker はこのリポジトリのフォルダ**（`notify_data` があるフォルダ）で `docker compose` を実行してください。  
③ トーストの「承認」で getaddrinfo failed になる場合: バックエンドのポートが 8000 でないときは、`.env` に `NOTIFY_BACKEND_URL=http://localhost:ポート` を設定してください。
        """)
        st.caption("画面上のトーストやブラウザの「通知の許可」は、ブラウザを開いているとき用の補助です。")
        if st.button("通知の許可をリクエスト（ブラウザ）", key="hitl_notify_permission"):
            components.html(
                """<script>
                (function() {
                  var N = (window.top && window.top.Notification) ? window.top.Notification : (window.Notification || null);
                  if (N && N.permission === "default") N.requestPermission();
                })();
                </script>""",
                height=0,
            )
            st.toast("ブラウザの通知許可ダイアログが表示されたら「許可」を選んでください。", icon="🔔", duration="long")


def fetch_page_detail_and_notify(task_id: str, base_branch_input: str, repo_path_input: str) -> bool:
    """
    バックエンドでページ詳細を取得し、session_state に格納してデスクトップ通知を出す。
    同じブランチ名の通知は1回だけ送信する。
    成功で True、失敗で False（step_placeholder は呼び出し側で設定すること）。
    """
    backend_url = get_backend_url()
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.get(f"{backend_url}/page/detail", params={"task_id": task_id})
    except httpx.ConnectError:
        return False
    if r.status_code != 200:
        st.error(f"❌ API エラー: {r.text[:300]}")
        return False
    data = r.json()
    if "error" in data:
        st.error(f"❌ {data['error']}")
        return False
    branch_name = data.get("branch_name", "")
    st.session_state["hitl_branch_name"] = branch_name
    st.session_state["hitl_pending_base_branch"] = (base_branch_input or "main").strip()
    st.session_state["hitl_pending_repo_path"] = (repo_path_input or "").strip()
    st.session_state["hitl_markdown_content"] = data.get("markdown_content", "")
    st.session_state.pop("hitl_result", None)
    st.session_state.pop("hitl_result_detail", None)
    st.session_state.pop("hitl_requirement_md", None)
    st.session_state.pop("hitl_requirement_steps", None)

    # ローカル変更をチェック
    local_changes_msg = ""
    try:
        repo_path = st.session_state["hitl_pending_repo_path"]
        r_changes = httpx.get(
            f"{backend_url}/branch/local-changes",
            params={"repo_path": repo_path} if repo_path else {},
            timeout=10.0,
        )
        if r_changes.status_code == 200:
            changes_data = r_changes.json()
            if changes_data.get("has_changes"):
                local_changes_msg = changes_data.get("detail", "")
                st.session_state["hitl_has_local_changes"] = True
    except Exception:
        pass

    # 毎回通知を送信
    notify_body = f"{branch_name} を作成してチェックアウトしますか？"
    if local_changes_msg:
        notify_body += f"\n\n⚠️ {local_changes_msg}"

    show_desktop_notification(
        "ブランチ名が準備できました",
        notify_body,
        branch_name,
        base_branch=st.session_state["hitl_pending_base_branch"],
        repo_path=st.session_state["hitl_pending_repo_path"],
            backend_url=get_backend_url(),
        )

    return True


def poll_checkout_status(branch_name: str) -> bool:
    """チェックアウト結果を GET し、同一ブランチなら session_state に反映。反映したら True。"""
    try:
        r = httpx.get(f"{get_backend_url()}/branch/checkout/status", timeout=30.0)
        if r.status_code != 200:
            return False
        data = r.json()
        if data.get("branch_name") == branch_name and data.get("result"):
            st.session_state["hitl_result"] = data["result"]
            st.session_state["hitl_result_detail"] = data.get("detail", "")
            return True
    except Exception:
        pass
    return False


def poll_requirement_ack(branch_name: str) -> bool:
    """requirement 承認状態を GET し、同一ブランチなら session_state に反映。反映したら True。"""
    try:
        r = httpx.get(f"{get_backend_url()}/requirement/ready/ack", timeout=10.0)
        if r.status_code != 200:
            return False
        data = r.json()
        if data.get("branch_name") == branch_name and data.get("action"):
            st.session_state["hitl_requirement_ack"] = data["action"]
            return True
    except Exception:
        pass
    return False


def clear_backend_state_and_rerun():
    """クリア時にバックエンドの ack/checkout 状態をリセットし、session_state をクリアして rerun。"""
    try:
        base = get_backend_url()
        httpx.post(f"{base}/requirement/ready/ack/clear", timeout=5.0)
        httpx.post(f"{base}/branch/checkout/status/clear", timeout=5.0)
    except Exception:
        pass
    clear_hitl_state(st)
    st.rerun()


def run_requirement_stream_sse(markdown_content: str, branch_name: str, repo_path_val: str):
    """requirement ストリーミング生成を実行し、SSE をパースして session_state に格納。"""
    thinking_placeholder = st.empty()
    content_placeholder = st.empty()
    thinking_placeholder.caption("LLM の思考過程（ストリーミング）")
    thinking_box = st.empty()
    content_placeholder.caption("requirement.md 本文（ストリーミング）")
    content_box = st.empty()
    thinking_text = []
    content_text = []

    def flush_sse(current_event: str | None, data_buffer: list[str]) -> bool:
        if not current_event or not data_buffer:
            return False
        payload = "\n".join(data_buffer)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = payload
        if current_event == "thinking":
            thinking_text.append(data if isinstance(data, str) else str(data))
            thinking_box.markdown("".join(thinking_text))
        elif current_event == "content":
            content_text.append(data if isinstance(data, str) else str(data))
            content_box.markdown("".join(content_text))
        elif current_event == "done":
            if isinstance(data, dict):
                st.session_state["hitl_requirement_md"] = data.get("requirement_md", "")
                st.session_state["hitl_requirement_steps"] = data.get("steps", [])
                st.session_state["hitl_requirement_thinking"] = "".join(thinking_text)
                write_requirement_complete_notify(branch_name)
                return True
        elif current_event == "error":
            st.error(f"❌ {data}")
        return False

    with httpx.stream(
        "POST",
        f"{get_backend_url()}/requirement/generate/stream",
        json={
            "markdown_body": markdown_content,
            "branch_name": branch_name,
            "repo_path": repo_path_val.strip() or None,
        },
        timeout=180.0,
    ) as r:
        if r.status_code != 200:
            st.error(f"❌ 生成失敗: {r.text[:300]}")
            return
        current_event = None
        data_buffer = []
        for line in r.iter_lines():
            if line.startswith("event:"):
                if flush_sse(current_event, data_buffer):
                    st.rerun()
                    return
                data_buffer = []
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_buffer.append(line[5:].strip() if len(line) > 5 else "")
            elif line == "":
                if flush_sse(current_event, data_buffer):
                    st.rerun()
                    return
                data_buffer = []
                current_event = None
        if current_event and data_buffer:
            flush_sse(current_event, data_buffer)
        st.rerun()
