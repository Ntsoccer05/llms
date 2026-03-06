"""タスクIDでページ取得"""
import streamlit as st
from notion_api import search_by_datasource, fetch_page_by_id
from utils.format import extract_page_id_from_url
from ui.components import render_accordion_result


def run() -> None:
    st.subheader("タスクIDでページ取得")
    task_id = st.text_input("タスクID", placeholder="例: ES-12345", key="page_task_id")
    if st.button("実行", key="page_run"):
        if not task_id:
            st.warning("タスクIDを入力してください")
        else:
            step_placeholder = st.empty()
            accordion_container = st.container()
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
            step_placeholder.info("🔄 **Step 2/2:** ページ情報を取得しています...")
            page_id = extract_page_id_from_url(results[0]["url"])
            page_result = fetch_page_by_id(page_id)
            with accordion_container:
                render_accordion_result("2. ページ取得結果", page_result)
            if "error" in page_result:
                step_placeholder.error(page_result["error"])
            else:
                step_placeholder.success("✅ **完了:** ページ情報を取得しました")
