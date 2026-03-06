"""HITL: ページ詳細＋ブランチ名取得。"""
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

    st.subheader("1. ブランチ作成の設定")
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

    task_id = st.text_input("タスクID", placeholder="例: ES-1", key="hitl_task_id")

    base_ok = bool((base_branch_input or "main").strip())
    task_id_ok = bool((task_id or "").strip())
    repo_path_ok = bool((repo_path_input or "").strip()) or (
        uploaded_dir is not None and len(uploaded_dir) > 0
    )
    run_enabled = base_ok and task_id_ok and repo_path_ok

    if st.button("実行（ブランチ名を取得）", key="hitl_run", disabled=not run_enabled):
        if not task_id_ok:
            st.warning("タスクIDを入力してください")
        elif not repo_path_ok:
            st.warning("「リポジトリのパス」を入力するか「リポジトリのフォルダを選択」でフォルダを選んでください。")
        else:
            step_placeholder = st.empty()
            step_placeholder.info("🔄 バックエンドでページ詳細・ブランチ名を取得しています（他タブで作業して問題ありません）...")
            try:
                backend_url = get_backend_url()
                with httpx.Client(timeout=180.0) as client:
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
                        st.session_state["hitl_markdown_content"] = data.get("markdown_content", "")
                        st.session_state.pop("hitl_result", None)
                        st.session_state.pop("hitl_result_detail", None)
                        st.session_state.pop("hitl_requirement_md", None)
                        st.session_state.pop("hitl_requirement_steps", None)
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
            st.caption("デスクトップ通知で「承認」した場合、数秒以内に自動で反映されます。")
            if st.button("状態を確認", key="hitl_refresh_status"):
                try:
                    r = httpx.get(f"{get_backend_url()}/branch/checkout/status", timeout=30.0)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("branch_name") == branch_name and data.get("result"):
                            st.session_state["hitl_result"] = data["result"]
                            st.session_state["hitl_result_detail"] = data.get("detail", "")
                            st.toast("状態を反映しました", icon="✅")
                            st.rerun()
                        elif data:
                            st.info("直近のチェックアウト結果は別ブランチです。")
                    else:
                        st.warning("状態の取得に失敗しました。")
                except Exception as e:
                    st.warning(f"状態の取得に失敗しました: {e}")
            else:
                # 承認・却下をまだ押していない → 数秒ごとに自動でチェックアウト結果を確認
                time.sleep(3)
                try:
                    r = httpx.get(f"{get_backend_url()}/branch/checkout/status", timeout=30.0)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("branch_name") == branch_name and data.get("result"):
                            st.session_state["hitl_result"] = data["result"]
                            st.session_state["hitl_result_detail"] = data.get("detail", "")
                            st.rerun()
                except Exception:
                    pass
                st.rerun()
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
                        timeout=180.0,
                    )
                    if cr.status_code == 200:
                        res = cr.json()
                        st.session_state["hitl_result"] = "checkout_ok"
                        st.session_state["hitl_result_detail"] = (
                            f"リモート作成: {res.get('remote_created')}, ローカルチェックアウト: {res.get('local_checked_out')}"
                        )
                        write_requirement_ready_notify(branch_name, get_backend_url())
                        st.toast("✅ チェックアウト完了", icon="✅")
                    else:
                        st.session_state["hitl_result"] = "checkout_failed"
                        st.session_state["hitl_result_detail"] = cr.text[:300]
                        write_requirement_ready_notify(branch_name, get_backend_url())
                        st.toast("❌ チェックアウト失敗", icon="❌")
                except Exception as e:
                    st.session_state["hitl_result"] = "checkout_failed"
                    st.session_state["hitl_result_detail"] = str(e)
                    st.toast("❌ エラー", icon="❌")
            st.rerun()
        if rejected:
            st.session_state["hitl_result"] = "rejected"
            st.session_state["hitl_result_detail"] = "却下しました"
            write_requirement_ready_notify(branch_name, get_backend_url())
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
                st.caption("チェックアウトは行われていませんが、以下で requirement.md の作成・ダウンロードができます。")

            st.divider()
            st.subheader("requirement.md を生成")
            ack = st.session_state.get("hitl_requirement_ack")
            ack_triggered = st.session_state.get("hitl_requirement_ack_triggered")
            if ack and ack != "approved":
                st.caption("デスクトップで却下しました。")
            markdown_content = st.session_state.get("hitl_markdown_content", "")
            # ボタンクリック、またはデスクトップで承認済みで未生成なら自動で生成を開始
            run_generate = st.button("requirement.md を生成", key="hitl_gen_req")
            if not run_generate and ack == "approved" and not ack_triggered and not st.session_state.get("hitl_requirement_md") and markdown_content:
                run_generate = True
                st.session_state["hitl_requirement_ack_triggered"] = True
            if run_generate:
                if not markdown_content:
                    st.warning("Notion 本文がありません。最初から「実行（ブランチ名を取得）」を実行してください。")
                else:
                    if ack == "approved" and ack_triggered:
                        st.caption("デスクトップで承認しました。requirement.md を生成しています…")
                    thinking_placeholder = st.empty()
                    content_placeholder = st.empty()
                    thinking_placeholder.caption("LLM の思考過程（ストリーミング）")
                    thinking_box = st.empty()
                    content_placeholder.caption("requirement.md 本文（ストリーミング）")
                    content_box = st.empty()
                    thinking_text = []
                    content_text = []
                    got_done = False

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

                    try:
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
                            else:
                                current_event = None
                                data_buffer = []
                                for line in r.iter_lines():
                                    if line.startswith("event:"):
                                        if flush_sse(current_event, data_buffer):
                                            got_done = True
                                            break
                                        data_buffer = []
                                        current_event = line.split(":", 1)[1].strip()
                                    elif line.startswith("data:"):
                                        data_buffer.append(line[5:].strip() if len(line) > 5 else "")
                                    elif line == "":
                                        if flush_sse(current_event, data_buffer):
                                            got_done = True
                                            break
                                        data_buffer = []
                                        current_event = None
                                if not got_done and current_event and data_buffer:
                                    got_done = flush_sse(current_event, data_buffer)
                                if got_done:
                                    st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

            if st.session_state.get("hitl_requirement_md"):
                st.caption("ブランチ名（ドラッグで選択 → Ctrl+C でコピー）")
                st.code(branch_name, language="text")
                st.download_button(
                    "requirement.md をダウンロード",
                    data=st.session_state.get("hitl_requirement_md", ""),
                    file_name="requirement.md",
                    mime="text/markdown",
                    key="hitl_dl_req",
                )
                thinking_req = st.session_state.get("hitl_requirement_thinking", "")
                if thinking_req:
                    with st.expander("LLM の思考過程", expanded=False):
                        st.markdown(thinking_req)
                steps_req = st.session_state.get("hitl_requirement_steps") or []
                if steps_req:
                    with st.expander("途中の思考過程（参照URL・生成結果）", expanded=False):
                        for step in steps_req:
                            st.markdown(f"**{step.get('title', '')}**")
                            st.text(step.get("content", ""))
                            st.divider()
                st.markdown("---")
                st.caption("requirement.md（選択してコピー）")
                st.code(st.session_state.get("hitl_requirement_md", ""), language="markdown")
            if not st.session_state.get("hitl_requirement_ack"):
                time.sleep(3)
                try:
                    r = httpx.get(f"{get_backend_url()}/requirement/ready/ack", timeout=10.0)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("branch_name") == branch_name and data.get("action"):
                            st.session_state["hitl_requirement_ack"] = data["action"]
                            st.rerun()
                except Exception:
                    pass
                st.rerun()
            if st.button("クリアして最初から", key="hitl_clear"):
                try:
                    base = get_backend_url()
                    httpx.post(f"{base}/requirement/ready/ack/clear", timeout=5.0)
                    httpx.post(f"{base}/branch/checkout/status/clear", timeout=5.0)
                except Exception:
                    pass
                clear_hitl_state(st)
                st.rerun()
