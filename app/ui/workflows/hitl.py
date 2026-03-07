"""HITL: ページ詳細＋ブランチ名取得。"""
import time
import streamlit as st
import httpx

from ui.config import get_backend_url
from ui.workflows.hitl_helpers import (
    render_notification_help,
    fetch_page_detail_and_notify,
    poll_checkout_status,
    poll_requirement_ack,
    clear_backend_state_and_rerun,
    run_requirement_stream_sse,
    write_requirement_ready_notify,
)


def _get_github_owner() -> str:
    """env の GITHUB_REPO から owner を抽出する（owner/repo 形式）。"""
    from config import get_settings
    try:
        github_repo = (get_settings().GITHUB_REPO or "").strip()
        if github_repo and "/" in github_repo:
            owner = github_repo.split("/", 1)[0]
            return owner
    except Exception:
        pass
    return ""


def run() -> None:
    # 初回ロード時のデフォルト値を設定（widget より前に実行）
    if "hitl_github_repo" not in st.session_state:
        from config import get_settings
        default_repo = (get_settings().GITHUB_REPO or "").strip()
        st.session_state["hitl_github_repo"] = default_repo

    st.caption(
        "バックエンド API でページ詳細とブランチ名を取得します。"
        "準備できたら通知し、あなたが「作成してチェックアウト」を選ぶまでブランチは切りません。"
    )
    render_notification_help()

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
        task_id = st.text_input("タスクID*", placeholder="例: ES-1", key="hitl_task_id", help="Notion タスクの ID。")
    

    # 初回ロード時にリポジトリを自動読み込み
    if not st.session_state.get("hitl_available_repos"):
        try:
            # ローカル環境: tkinter で フォルダ選択を試みる
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes('-topmost', 1)
            folder = filedialog.askdirectory()
            root.destroy()
            if folder:
                st.session_state["hitl_input_repo"] = folder
                st.rerun()
        except Exception:
            # Docker 環境: API でリスト取得
            try:
                r = httpx.get(f"{get_backend_url()}/branch/repo/discover", timeout=10.0)
                if r.status_code == 200:
                    repos = r.json().get("repos", [])
                    if repos:
                        # Git リポジトリのみをフィルタ（type が git のもの）
                        git_repos = [r for r in repos if r.get("type") == "git"]
                        if git_repos:
                            st.session_state["hitl_available_repos"] = git_repos
            except Exception:
                pass

    # フォルダ選択（ローカル tkinter または API）
    col_select, col_input = st.columns([1, 3])

    with col_select:
        # リポジトリが読み込まれている場合、selectbox を表示
        available_repos = st.session_state.get("hitl_available_repos", [])
        if available_repos:
            repo_labels = [f"{r['name']} ({r['type']})" for r in available_repos]
            selected_idx = st.selectbox(
                "リポジトリ",
                options=range(len(repo_labels)),
                format_func=lambda i: repo_labels[i],
                key="hitl_repo_selector"
            )
            # 前回の選択値と比較して、変更があった場合のみ更新
            prev_selected_idx = st.session_state.get("hitl_prev_selected_idx")
            if selected_idx is not None and selected_idx != prev_selected_idx:
                st.session_state["hitl_prev_selected_idx"] = selected_idx
                selected_repo = available_repos[selected_idx]
                # テキストボックスに表示するのはホスト側パス
                display_path = selected_repo.get("host_path", selected_repo["path"])
                st.session_state["hitl_input_repo"] = display_path
                # チェックアウト時に使うコンテナ内パスを保存
                st.session_state["hitl_container_repo_path"] = selected_repo["path"]
                # GitHub リポジトリを自動設定（owner は .env から、repo はフォルダ名）
                owner = _get_github_owner()
                repo_name = selected_repo["name"]
                if owner:
                    github_repo_value = f"{owner}/{repo_name}"
                else:
                    github_repo_value = repo_name
                # テキスト入力フィールドのキーを直接更新して動的に反映
                st.session_state["hitl_github_repo"] = github_repo_value
                st.rerun()

        if st.button("📂 再読み込み", key="hitl_dir_select", help="リポジトリを再度読み込みます"):
            try:
                # ローカル環境: tkinter
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.wm_attributes('-topmost', 1)
                folder = filedialog.askdirectory()
                root.destroy()
                if folder:
                    st.session_state["hitl_input_repo"] = folder
                    st.rerun()
            except Exception:
                # Docker 環境: API でリスト取得
                try:
                    r = httpx.get(f"{get_backend_url()}/branch/repo/discover", timeout=10.0)
                    if r.status_code == 200:
                        repos = r.json().get("repos", [])
                        if repos:
                            # Git リポジトリのみをフィルタ（.git フォルダを持つもの）
                            git_repos = [r for r in repos if r.get("is_git", False)]
                            if git_repos:
                                st.session_state["hitl_available_repos"] = git_repos
                                st.success("✅ リポジトリを読み込みました")
                            else:
                                st.warning("Git リポジトリがありません。パスを手動入力してください。")
                        else:
                            st.warning("利用可能なリポジトリがありません。パスを手動入力してください。")
                except Exception:
                    st.warning(f"フォルダ選択が使えません。パスを手動入力してください。")

    with col_input:
        repo_path_input = st.text_input(
            "リポジトリのパス",
            key="hitl_input_repo",
            placeholder="C:\\Workspace\\AI-Agent または /workspace",
            help="チェックアウトを実行する絶対パス。未入力時は .env の REPO_PATH を使用。",
        )

    github_repo_input = st.text_input(
        "GitHub リポジトリ（オプション）",
        placeholder="owner/repo",
        key="hitl_github_repo",
        help="GitHub リポジトリ（owner/repo 形式）。未指定時は .env の設定を使用。",
    )

    base_ok = bool((base_branch_input or "main").strip())
    task_id_ok = bool((task_id or "").strip())
    repo_path_ok = bool((repo_path_input or "").strip())
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
                ok = fetch_page_detail_and_notify(task_id, base_branch_input, repo_path_input)
                if ok:
                    step_placeholder.success("✅ ブランチ名が準備できました")
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

    if not st.session_state.get("hitl_branch_name"):
        return

    branch_name = st.session_state["hitl_branch_name"]
    base_branch = st.session_state.get("hitl_pending_base_branch", "main")
    repo_path_val = st.session_state.get("hitl_pending_repo_path", "")

    # ローカル変更の警告
    if st.session_state.get("hitl_has_local_changes"):
        st.warning("⚠️ ローカルに変更があります。チェックアウト前に自動的に stash に保存されます。")

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
        st.caption("デスクトップ通知で「承認」した場合、約2秒ごとに自動で反映されます。")
        if st.button("状態を確認", key="hitl_refresh_status"):
            if poll_checkout_status(branch_name):
                st.toast("状態を反映しました", icon="✅")
                st.rerun()
            else:
                try:
                    r = httpx.get(f"{get_backend_url()}/branch/checkout/status", timeout=30.0)
                    if r.status_code == 200 and r.json():
                        st.info("直近のチェックアウト結果は別ブランチです。")
                    else:
                        st.warning("状態の取得に失敗しました。")
                except Exception:
                    st.warning("状態の取得に失敗しました。")
        # デスクトップ通知で承認した場合にバックエンド結果を検知するため、フラグメントでポーリング（ブロックせず約2秒ごとに更新）
        @st.fragment(run_every=2.0)
        def _poll_desktop_checkout():
            if st.session_state.get("hitl_result"):
                return
            bn = st.session_state.get("hitl_branch_name")
            if not bn:
                return
            if poll_checkout_status(bn):
                st.rerun()

        _poll_desktop_checkout()
    else:
        approved = False
        rejected = False

    if approved:
        with st.spinner("GitHub にブランチ作成・ローカルでチェックアウトしています..."):
            try:
                payload = {"branch_name": branch_name, "base_branch": base_branch}
                # チェックアウト時に使うパスを取得（コンテナ内パスを優先）
                checkout_repo_path = st.session_state.get("hitl_container_repo_path", repo_path_val)
                if (checkout_repo_path or "").strip():
                    payload["repo_path"] = checkout_repo_path.strip()
                # GitHub リポジトリを指定（ユーザー入力を優先、なければ .env の値）
                from config import get_settings
                github_repo_val = (github_repo_input or get_settings().GITHUB_REPO or "").strip()
                if github_repo_val:
                    payload["github_repo"] = github_repo_val
                cr = httpx.post(f"{get_backend_url()}/branch/checkout", json=payload, timeout=180.0)
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
    if not st.session_state.get("hitl_result"):
        return

    result = st.session_state["hitl_result"]
    detail = st.session_state.get("hitl_result_detail", "")
    st.subheader("結果")
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
            run_requirement_stream_sse(markdown_content, branch_name, repo_path_val)

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

    # クリアボタンは常に表示（ack 待ちで rerun する前に描画する）
    if st.button("クリアして最初から", key="hitl_clear"):
        clear_backend_state_and_rerun()

    if not st.session_state.get("hitl_requirement_ack"):
        time.sleep(3)
        if poll_requirement_ack(branch_name):
            st.rerun()
        st.rerun()
