"""タスクIDでページ詳細取得（ブロック一覧）"""
import streamlit as st
from notion_api import search_by_datasource, fetch_page_by_id, fetch_blocks
from utils.format import extract_page_id_from_url, blocks_to_markdown
from ui.components import render_accordion_result


def run() -> None:
    st.subheader("タスクIDでページ詳細取得（ブロック一覧）")
    task_id = st.text_input("タスクID", placeholder="例: ES-12345", key="detail_task_id")
    if st.button("実行", key="run_btn_detail_blocks"):
        if not task_id:
            st.warning("タスクIDを入力してください")
        else:
            step_placeholder = st.empty()
            accordion_container = st.container()
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
            step_placeholder.info("🔄 **Step 2/4:** ページ基本情報を取得しています...")
            page_result = fetch_page_by_id(page_id)
            with accordion_container:
                render_accordion_result("2. ページ基本情報", page_result)
            if "error" in page_result:
                step_placeholder.error(page_result["error"])
                st.stop()
            step_placeholder.info("🔄 **Step 3/4:** ブロック一覧を再帰取得しています...")
            blocks = fetch_blocks(page_id)
            with accordion_container:
                render_accordion_result("3. ブロック一覧（生データ）", blocks)
            step_placeholder.info("🔄 **Step 4/4:** マークダウンに変換しています...")
            markdown_content = blocks_to_markdown(blocks)
            with accordion_container:
                render_accordion_result("4. マークダウン変換結果", markdown_content)
            step_placeholder.success("✅ **完了:** ページ詳細の取得と変換が完了しました")
            st.divider()
            st.subheader("プレビュー（マークダウン）")
            st.markdown(markdown_content)
