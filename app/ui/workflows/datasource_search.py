"""タスクIDでデータソース検索"""
import streamlit as st
from notion_api import search_by_datasource
from ui.components import render_accordion_result


def run() -> None:
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
