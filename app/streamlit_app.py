"""
Notion API 操作を Streamlit GUI で実行するアプリ
途中結果はアコーディオンで表示し、処理中のステップを明示する。
ブランチ名取得は Human-in-the-loop でデスクトップ通知後にユーザーが承認してチェックアウト可能。
"""
import fnmatch
import json
import os
import platform
import time
import streamlit as st
import streamlit.components.v1 as components
import httpx
from notion_api import (
    fetch_databases,
    fetch_datasources,
    search,
    search_by_datasource,
    fetch_page,
    fetch_page_by_id,
    fetch_blocks,
    fetch_page_detail,
)
from utils.format import blocks_to_markdown, extract_page_id_from_url


def _is_likely_docker():
    """Streamlit が Docker コンテナ内で動いているか（コンテナ内なら backend サービス名で接続する）"""
    if os.path.exists("/.dockerenv"):
        return True
    return os.environ.get("KUBERNETES_SERVICE_HOST") or os.environ.get("CONTAINER") == "true"


def get_backend_url():
    """
    バックエンド URL を取得。
    Docker 内で動いているときは BACKEND_HOST を優先（http://backend:8000）。
    ローカル実行時は BACKEND_URL（例: http://localhost:8000）を優先。
    """
    host = (os.environ.get("BACKEND_HOST") or "").strip()
    if not host:
        try:
            host = (get_settings().BACKEND_HOST or "").strip()
        except Exception:
            pass
    # Docker 内なら BACKEND_HOST でバックエンドに接続（localhost はコンテナ自身になるため）
    if _is_likely_docker() and host:
        return f"http://{host}:8000"
    url = (os.environ.get("BACKEND_URL") or "").strip()
    if not url:
        try:
            url = (get_settings().BACKEND_URL or "").strip()
        except Exception:
            pass
    if url:
        return url
    if host:
        return f"http://{host}:8000"
    return "http://localhost:8000"

st.set_page_config(page_title="Notion API GUI", layout="wide")
st.title("Notion API 操作 GUI")

# サイドバーで操作を選択
operation = st.sidebar.radio(
    "実行する操作",
    [
        "データベース情報を取得",
        "データソース情報を取得",
        "文字列検索",
        "タスクIDでデータソース検索",
        "タスクIDでページ取得",
        "タスクIDでページ詳細取得（ブロック一覧）",
        "ページ詳細＋ブランチ名取得（Human-in-the-loop）",
    ],
)

def render_accordion_result(title: str, data, expanded: bool = False):
    """途中結果をアコーディオンで表示"""
    with st.expander(title, expanded=expanded):
        if isinstance(data, (dict, list)):
            st.json(data)
        else:
            st.write(data)


def show_desktop_notification(
    title: str,
    body: str,
    branch_name: str,
    *,
    base_branch: str = "main",
    repo_path: str = "",
    backend_url: str = "",
):
    """
    ブランチ名準備完了を通知する（ブラウザを閉じていても PC に通知が出る）。
    トーストから承認・却下できるよう、checkout に必要な情報も JSON に含める。
    """
    checkout_payload = {
        "branch_name": branch_name,
        "base_branch": (base_branch or "main").strip(),
        "repo_path": (repo_path or "").strip(),
        "backend_url": (backend_url or "").strip(),
    }

    backend_url_final = backend_url or get_backend_url()
    checkout_payload["backend_url"] = backend_url_final

    # Windows ローカル実行時: win11toast でトースト＋承認/却下ボタン（承認時は API 呼び出し）
    try:
        from win11toast import toast

        def on_toast_click(args):
            # win11toast の文字列ボタンでは arguments が "http:承認" / "http:却下" になる
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
                    timeout=60.0,
                )
            except Exception:
                pass

        # 両方のボタンが表示されるよう dict で明示（protocol で arguments がコールバックに渡る）
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

    # 共有フォルダに通知を書き出し（watcher がトースト＋承認/却下ボタンで表示し、承認時は API 呼び出し）
    notify_dir = (os.environ.get("NOTIFY_DIR") or "").strip()
    if not notify_dir and platform.system() == "Windows":
        _app_dir = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(_app_dir)
        notify_dir = os.path.join(_project_root, "notify_data")
    if notify_dir:
        try:
            os.makedirs(notify_dir, exist_ok=True)
            path = os.path.join(notify_dir, f"notify_{int(time.time() * 1000)}.json")
            payload = {"title": title, "body": body, "branch_name": branch_name}
            payload["base_branch"] = checkout_payload["base_branch"]
            payload["repo_path"] = checkout_payload["repo_path"]
            # watcher は Windows 上で動くため、Docker の backend ではなくホストから届く URL を使う
            _backend_for_notify = (os.environ.get("NOTIFY_BACKEND_URL") or "").strip()
            if not _backend_for_notify:
                _backend_for_notify = checkout_payload.get("backend_url") or get_backend_url()
            if "backend" in (_backend_for_notify or ""):
                _backend_for_notify = os.environ.get("NOTIFY_BACKEND_URL", "http://localhost:8000").strip() or "http://localhost:8000"
            payload["backend_url"] = _backend_for_notify
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

    # 画面上のトースト
    st.toast(body, icon="✅", duration="long")

    # ブラウザのデスクトップ通知（iframe 内では動かないことが多いが試行）
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


def show_notion_error(error_msg: str, step_placeholder=None):
    """Notion API エラーを表示し、対処案があれば案内する"""
    if step_placeholder:
        step_placeholder.error(f"❌ エラー: {error_msg}")
    else:
        st.error(f"❌ エラー: {error_msg}")
    # データベース/インテグレーション共有に関するエラーの場合は対処案を表示
    if "database" in error_msg.lower() and "shared with your integration" in error_msg.lower():
        st.warning(
            "**対処方法:** Notion で対象のデータベース（またはデータソースが参照するデータベース）を "
            "インテグレーションと共有してください。\n\n"
            "1. Notion で該当データベースのページを開く\n"
            "2. 右上の「…」→「接続」→ 使用中のインテグレーションを追加\n"
            "3. または .env の `NOTION_DATABASE_ID` / `NOTION_DATASOURCE_ID` が正しいか確認"
        )

# --- データベース情報を取得 ---
if operation == "データベース情報を取得":
    st.subheader("データベース情報を取得")
    if st.button("実行", key="db_run"):
        step_placeholder = st.empty()
        step_placeholder.info("🔄 **処理中:** データベース情報を取得しています...")
        result = fetch_databases()
        step_placeholder.success("✅ **完了:** データベース情報を取得しました")
        render_accordion_result("取得結果", result, expanded=True)

# --- データソース情報を取得 ---
elif operation == "データソース情報を取得":
    st.subheader("データソース情報を取得")
    if st.button("実行", key="ds_run"):
        step_placeholder = st.empty()
        step_placeholder.info("🔄 **処理中:** データソース情報を取得しています...")
        result = fetch_datasources()
        step_placeholder.success("✅ **完了:** データソース情報を取得しました")
        render_accordion_result("取得結果", result, expanded=True)

# --- 文字列検索 ---
elif operation == "文字列検索":
    st.subheader("文字列検索")
    query = st.text_input("検索クエリ", placeholder="検索したい文字列を入力")
    if st.button("実行", key="search_run"):
        if not query:
            st.warning("検索クエリを入力してください")
        else:
            step_placeholder = st.empty()
            step_placeholder.info("🔄 **処理中:** 文字列検索を実行しています...")
            result = search(query)
            step_placeholder.success("✅ **完了:** 検索が完了しました")
            render_accordion_result("検索結果", result, expanded=True)

# --- タスクIDでデータソース検索 ---
elif operation == "タスクIDでデータソース検索":
    st.subheader("タスクIDでデータソース検索")
    task_id = st.text_input("タスクID", placeholder="例: ES-12345 または 12345", key="ds_task_id")
    if st.button("実行", key="ds_search_run"):
        if not task_id:
            st.warning("タスクIDを入力してください")
        else:
            step_placeholder = st.empty()
            step_placeholder.info("🔄 **処理中:** データソースをタスクIDで検索しています...")
            result = search_by_datasource(task_id)
            step_placeholder.success("✅ **完了:** 検索が完了しました")
            render_accordion_result("データソース検索結果", result, expanded=True)

# --- タスクIDでページ取得 ---
elif operation == "タスクIDでページ取得":
    st.subheader("タスクIDでページ取得")
    task_id = st.text_input("タスクID", placeholder="例: ES-12345", key="page_task_id")
    if st.button("実行", key="page_run"):
        if not task_id:
            st.warning("タスクIDを入力してください")
        else:
            step_placeholder = st.empty()
            accordion_container = st.container()
            # Step 1: データソース検索
            step_placeholder.info("🔄 **Step 1/2:** データソースでタスクIDを検索しています...")
            datasource_result = search_by_datasource(task_id)
            with accordion_container:
                render_accordion_result("1. データソース検索結果", datasource_result)
            if "error" in datasource_result:
                step_placeholder.error(f"❌ エラー: {datasource_result['error']}")
                st.stop()
            results = datasource_result.get("results", [])
            if not results:
                step_placeholder.error("❌ 該当するページがありません")
                st.stop()
            # Step 2: ページ取得
            step_placeholder.info("🔄 **Step 2/2:** ページ情報を取得しています...")
            page_id = extract_page_id_from_url(results[0]["url"])
            page_result = fetch_page_by_id(page_id)
            with accordion_container:
                render_accordion_result("2. ページ取得結果", page_result)
            if "error" in page_result:
                step_placeholder.error(page_result["error"])
            else:
                step_placeholder.success("✅ **完了:** ページ情報を取得しました")

# --- タスクIDでページ詳細取得（ブロック一覧） ---
elif operation == "タスクIDでページ詳細取得（ブロック一覧）":
    st.subheader("タスクIDでページ詳細取得（ブロック一覧）")
    task_id = st.text_input("タスクID", placeholder="例: ES-12345", key="detail_task_id")
    if st.button("実行", key="run_btn_detail_blocks"):
        if not task_id:
            st.warning("タスクIDを入力してください")
        else:
            step_placeholder = st.empty()
            accordion_container = st.container()
            # Step 1: データソース検索
            step_placeholder.info("🔄 **Step 1/4:** データソースでタスクIDを検索しています...")
            datasource_result = search_by_datasource(task_id)
            with accordion_container:
                render_accordion_result("1. データソース検索結果", datasource_result)
            if "error" in datasource_result:
                step_placeholder.error(f"❌ エラー: {datasource_result['error']}")
                st.stop()
            results = datasource_result.get("results", [])
            if not results:
                step_placeholder.error("❌ 該当するページがありません")
                st.stop()
            page_id = extract_page_id_from_url(results[0]["url"])
            # Step 2: ページ基本情報取得
            step_placeholder.info("🔄 **Step 2/4:** ページ基本情報を取得しています...")
            page_result = fetch_page_by_id(page_id)
            with accordion_container:
                render_accordion_result("2. ページ基本情報", page_result)
            if "error" in page_result:
                step_placeholder.error(page_result["error"])
                st.stop()
            # Step 3: ブロック一覧取得（再帰）
            step_placeholder.info("🔄 **Step 3/4:** ブロック一覧を再帰取得しています...")
            blocks = fetch_blocks(page_id)
            with accordion_container:
                render_accordion_result("3. ブロック一覧（生データ）", blocks)
            # Step 4: マークダウン変換
            step_placeholder.info("🔄 **Step 4/4:** マークダウンに変換しています...")
            markdown_content = blocks_to_markdown(blocks)
            with accordion_container:
                render_accordion_result("4. マークダウン変換結果", markdown_content)
            step_placeholder.success("✅ **完了:** ページ詳細の取得と変換が完了しました")
            # マークダウンをメインエリアにも表示
            st.divider()
            st.subheader("プレビュー（マークダウン）")
            st.markdown(markdown_content)

# --- ページ詳細＋ブランチ名取得（Human-in-the-loop）---
elif operation == "ページ詳細＋ブランチ名取得（Human-in-the-loop）":
    st.subheader("ページ詳細＋ブランチ名取得（Human-in-the-loop）")
    st.caption("バックエンド API でページ詳細とブランチ名を取得します。準備できたら通知し、あなたが「作成してチェックアウト」を選ぶまでブランチは切りません。")

    # デスクトップ通知について（ブラウザを閉じても PC に通知を出したい場合）
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
- **スタートアップに登録**（おすすめ）: `scripts\\install_watcher_startup.bat` をダブルクリックで実行すると、PC 起動時に watcher が自動で動きます。**毎回コマンドを打つ必要はありません。**
- **手動で 1 回起動**: プロジェクトルートで `python scripts/win_notify_watcher.py notify_data` を実行し、そのターミナルは閉じずにそのままにしておく。Docker で何度ブランチ名取得しても通知が届く。

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
        # 入力は一番最初: ベースブランチ ＋ リポジトリ（フォルダ選択）
        base_branch_input = st.text_input(
            "ベースブランチ*",
            value="main",
            key="hitl_base_branch",
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

    # .gitignore に含まれるパターンに一致するファイルはアップロード対象から外す
    if uploaded_dir:
        try:
            _ignore_patterns = []
            for _root in (
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                os.getcwd(),
                os.path.dirname(os.path.abspath(__file__)),
            ):
                _gitignore_path = os.path.join(_root, ".gitignore")
                if os.path.isfile(_gitignore_path):
                    with open(_gitignore_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip().split("#")[0].strip()
                            if line and not line.startswith("!"):
                                _ignore_patterns.append(line.rstrip("/"))
                    break
            # .gitignore が無い場合（Docker 等）は最低限のパターンで除外
            if not _ignore_patterns:
                _ignore_patterns = [
                    ".env", "__pycache__", "*.pyc", "*.pyo", "*.pyd",
                    ".venv", "venv", "env", "notify_data", ".idea", ".vscode", ".DS_Store", "*.log",
                ]
            def _should_ignore(path: str) -> bool:
                if not path:
                    return False
                # C:\Workspace\AI-Agent 選択時は AI-Agent/app/.env や app\.env 形式で渡る
                p = path.replace("\\", "/").strip("/")
                parts = [x for x in p.split("/") if x]
                base = parts[-1] if parts else ""
                # ファイル名が .env または パスが /.env で終わる場合は常に除外
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
            uploaded_dir = [f for f in uploaded_dir if not _should_ignore(getattr(f, "name", "") or "")]
        except Exception:
            pass

    # ディレクトリからフォルダ名を取得（アップロードでは絶対パスが取れないため、パス用の入力も用意）
    repo_folder_name = ""
    if uploaded_dir and len(uploaded_dir) > 0:
        first_name = getattr(uploaded_dir[0], "name", "") or ""
        repo_folder_name = first_name.split("/")[0] if "/" in first_name else first_name.split("\\")[0]

    repo_path_input = st.text_input(
        "リポジトリのパス（バックエンドから参照できる絶対パス）",
        value="",
        key="hitl_repo_path",
        placeholder="C:\\Workspace\\AI-Agent または /app（Docker 時はコンテナ内パス）",
        help="チェックアウトを実行する絶対パス。バックエンドが Docker のときはコンテナ内のパス（例: /app）を指定し、そのフォルダがホストのリポジトリをマウントしている必要があります。未入力時は .env の REPO_PATH を使用。",
    )

    # 接続先表示
    _backend_url = get_backend_url()
    st.caption(f"接続先: `{_backend_url}`")

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
                        st.subheader("提案ブランチ名")
                        st.code(branch_name, language="text")
                        # トースト本文は短くすると「承認」ボタンが隠れにくい
                        show_desktop_notification(
                            "ブランチ名が準備できました",
                            f"{branch_name} を作成してチェックアウトしますか？",
                            branch_name,
                            base_branch=(base_branch_input or "main").strip(),
                            repo_path=(repo_path_input or "").strip(),
                            backend_url=get_backend_url(),
                        )
                        st.info(
                            "💡 **PC にトースト通知を出しました。** トーストに「承認」「却下」ボタンが出る環境では押すとチェックアウトされます。"
                            " ボタンが出ない場合は、下の「このブランチを作成してチェックアウトする」を押してください（上で指定したベースブランチ・リポジトリパスを使用）。"
                        )
                        if st.button("このブランチを作成してチェックアウトする", key="hitl_checkout"):
                            with st.spinner("GitHub にブランチ作成・ローカルでチェックアウトしています..."):
                                try:
                                    payload = {
                                        "branch_name": branch_name,
                                        "base_branch": (base_branch_input or "main").strip(),
                                    }
                                    if (repo_path_input or "").strip():
                                        payload["repo_path"] = repo_path_input.strip()
                                    cr = httpx.post(
                                        f"{get_backend_url()}/branch/checkout",
                                        json=payload,
                                        timeout=60.0,
                                    )
                                    if cr.status_code == 200:
                                        res = cr.json()
                                        st.success(
                                            f"✅ リモート作成: {res.get('remote_created')}, "
                                            f"ローカルチェックアウト: {res.get('local_checked_out')}"
                                        )
                                    else:
                                        st.error(f"❌ チェックアウト失敗: {cr.text[:300]}")
                                except Exception as e:
                                    st.error(f"❌ エラー: {e}")
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
