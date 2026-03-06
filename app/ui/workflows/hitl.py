"""HITL: ページ詳細＋ブランチ名取得。"""
import fnmatch
import os
import streamlit as st
import streamlit.components.v1 as components
import httpx

from ui.config import get_backend_url
from ui.notifications import show_desktop_notification
from ui.states import clear_hitl_state


def _gitignore_roots():
    _file = os.path.abspath(__file__)
    _workflows = os.path.dirname(_file)
    _ui = os.path.dirname(_workflows)
    _app = os.path.dirname(_ui)
    _project = os.path.dirname(_app)
    return [_project, _app, os.getcwd(), _workflows]


def _filter_uploaded_by_gitignore(uploaded_dir):
    if not uploaded_dir:
        return uploaded_dir
    try:
        _ignore_patterns = []
        for _root in _gitignore_roots():
            _gitignore_path = os.path.join(_root, ".gitignore")
            if os.path.isfile(_gitignore_path):
                with open(_gitignore_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip().split("#")[0].strip()
                        if line and not line.startswith("!"):
                            _ignore_patterns.append(line.rstrip("/"))
                break
        if not _ignore_patterns:
            _ignore_patterns = [
                ".env", "__pycache__", "*.pyc", "*.pyo", "*.pyd",
                ".venv", "venv", "env", "notify_data", ".idea", ".vscode", ".DS_Store", "*.log",
            ]

        def _should_ignore(path: str) -> bool:
            if not path:
                return False
            p = path.replace("\\", "/").strip("/")
            parts = [x for x in p.split("/") if x]
            base = parts[-1] if parts else ""
            if base == ".env" or p.endswith("/.env"):
                return True
            for pat in _ignore_patterns:
                if not pat:
                    continue
                if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(base, pat):
                    return True
                if pat in parts or pat == base:
                    return True
                if "/" + pat in p or p.endswith("/" + pat) or "\\" + pat in p:
                    return True
            return False

        return [f for f in uploaded_dir if not _should_ignore(getattr(f, "name", "") or "")]
    except Exception:
        return uploaded_dir


def run() -> None:
    st.subheader("ページ詳細＋ブランチ名取得（Human-in-the-loop）")
    st.caption("バックエンド API でページ詳細とブランチ名を取得します。準備できたら通知し、あなたが「作成してチェックアウト」を選ぶまでブランチは切りません。")

    with st.expander("🔔 ブラウザを閉じても PC に通知を出す方法"):
        st.caption(
            "**Windows で Streamlit をローカル実行している場合** — まず **watcher を起動したまま**にしてください。"
            "通知はプロジェクト直下の `notify_data` に書き出され、watcher が PC にトースト表示します（ブラウザを閉じていても表示されます）。"
        )
        st.caption(
            "**Docker で実行している場合** — 同じく **watcher を起動したまま**にすると、コンテナが `notify_data` に書き出した通知を watcher が表示します。"
            "watcher は 1 回起動したら閉じずにそのままにしておけば OK です。"
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

    st.subheader("1. ブランチ作成の設定（先に入力）")
    col1, col2 = st.columns(2)
    with col1:
        base_branch_input = st.text_input(
            "ベースブランチ*",
            value="main",
            key="hitl_input_base",
            placeholder="main",
            help="どのブランチをベースに新しいブランチを切るか指定します（例: main, develop）。",
        )
    with col2:
        try:
            uploaded_dir = st.file_uploader(
                "リポジトリのフォルダを選択",
                accept_multiple_files="directory",
                key="hitl_dir_upload",
                help="Git で管理しているフォルダを選択してください。",
            )
        except TypeError:
            uploaded_dir = st.file_uploader(
                "リポジトリのフォルダを選択（複数ファイル可）",
                accept_multiple_files=True,
                key="hitl_dir_upload",
                help="Git で管理しているフォルダ内のファイルを選択してください。",
            )
    uploaded_dir = _filter_uploaded_by_gitignore(uploaded_dir)

    repo_path_input = st.text_input(
        "リポジトリのパス（バックエンドから参照できる絶対パス）",
        value="",
        key="hitl_input_repo",
        placeholder="C:\\Workspace\\AI-Agent または /workspace（Docker 時はコンテナ内パス）",
        help="チェックアウトを実行する絶対パス。バックエンドが Docker のときはコンテナ内のパスを指定。未入力時は .env の REPO_PATH を使用。",
    )

    st.caption(f"接続先: `{get_backend_url()}`")

    st.subheader("2. ブランチ名を取得")
    task_id = st.text_input("タスクID", placeholder="例: ES-1", key="hitl_task_id")
    if st.button("実行（ブランチ名を取得）", key="hitl_run"):
        if not task_id:
            st.warning("タスクIDを入力してください")
        else:
            step_placeholder = st.empty()
            step_placeholder.info("🔄 バックエンドでページ詳細・ブランチ名を取得しています（他タブで作業して問題ありません）...")
            try:
                backend_url = get_backend_url()
                with httpx.Client(timeout=120.0) as client:
                    r = client.get(f"{backend_url}/page/detail", params={"task_id": task_id})
                if r.status_code != 200:
                    step_placeholder.error(f"❌ API エラー: {r.text[:300]}")
                else:
                    data = r.json()
                    if "error" in data:
                        step_placeholder.error(f"❌ {data['error']}")
                    else:
                        branch_name = data.get("branch_name", "")
                        step_placeholder.success("✅ ブランチ名が準備できました")
                        st.session_state["hitl_branch_name"] = branch_name
                        st.session_state["hitl_pending_base_branch"] = (base_branch_input or "main").strip()
                        st.session_state["hitl_pending_repo_path"] = (repo_path_input or "").strip()
                        st.session_state.pop("hitl_result", None)
                        st.session_state.pop("hitl_result_detail", None)
                        show_desktop_notification(
                            "ブランチ名が準備できました",
                            f"{branch_name} を作成してチェックアウトしますか？",
                            branch_name,
                            base_branch=st.session_state["hitl_pending_base_branch"],
                            repo_path=st.session_state["hitl_pending_repo_path"],
                            backend_url=get_backend_url(),
                        )
            except httpx.ConnectError:
                step_placeholder.error(
                    f"❌ バックエンドに接続できません: {get_backend_url()}\n\n"
                    "・**Docker で両方動かす場合**: `docker compose up -d` で backend と streamlit を起動し、"
                    "`.env` に `BACKEND_HOST=backend` を設定（streamlit 用）。\n\n"
                    "・**Streamlit だけローカルで動かす場合**: `.env` に `BACKEND_URL=http://localhost:8000` を設定し、"
                    "バックエンドは `docker compose up -d backend` で起動してください。（BACKEND_URL が優先されます）"
                )
            except Exception as e:
                step_placeholder.error(f"❌ {e}")

    if st.session_state.get("hitl_branch_name"):
        branch_name = st.session_state["hitl_branch_name"]
        base_branch = st.session_state.get("hitl_pending_base_branch", "main")
        repo_path_val = st.session_state.get("hitl_pending_repo_path", "")

        st.subheader("提案ブランチ名")
        st.code(branch_name, language="text")

        has_result = bool(st.session_state.get("hitl_result"))
        if not has_result:
            st.toast(f"**{branch_name}** を作成してチェックアウトしますか？ 承認または却下を選んでください。", icon="📌")
            col_approve, col_reject, _ = st.columns([1, 1, 2])
            with col_approve:
                approved = st.button("承認", key="hitl_approve", type="primary")
            with col_reject:
                rejected = st.button("却下", key="hitl_reject")
        else:
            approved = False
            rejected = False

        if approved:
            with st.spinner("GitHub にブランチ作成・ローカルでチェックアウトしています..."):
                try:
                    payload = {"branch_name": branch_name, "base_branch": base_branch}
                    if (repo_path_val or "").strip():
                        payload["repo_path"] = repo_path_val.strip()
                    cr = httpx.post(
                        f"{get_backend_url()}/branch/checkout",
                        json=payload,
                        timeout=60.0,
                    )
                    if cr.status_code == 200:
                        res = cr.json()
                        st.session_state["hitl_result"] = "checkout_ok"
                        st.session_state["hitl_result_detail"] = (
                            f"リモート作成: {res.get('remote_created')}, ローカルチェックアウト: {res.get('local_checked_out')}"
                        )
                        st.toast("✅ チェックアウト完了", icon="✅")
                    else:
                        st.session_state["hitl_result"] = "checkout_failed"
                        st.session_state["hitl_result_detail"] = cr.text[:300]
                        st.toast("❌ チェックアウト失敗", icon="❌")
                except Exception as e:
                    st.session_state["hitl_result"] = "checkout_failed"
                    st.session_state["hitl_result_detail"] = str(e)
                    st.toast("❌ エラー", icon="❌")
            st.rerun()
        if rejected:
            st.session_state["hitl_result"] = "rejected"
            st.session_state["hitl_result_detail"] = "却下しました"
            st.toast("却下しました", icon="🚫")
            st.rerun()

        if st.session_state.get("hitl_result"):
            st.subheader("結果")
            result = st.session_state["hitl_result"]
            detail = st.session_state.get("hitl_result_detail", "")
            if result == "checkout_ok":
                st.success(f"✅ {detail}")
            elif result == "rejected":
                st.info(f"🚫 {detail}")
            else:
                st.error(f"❌ {detail}")
            if st.button("クリアして最初から", key="hitl_clear"):
                clear_hitl_state(st)
                st.rerun()
