"""データソース情報を取得"""
import streamlit as st
from notion_api import fetch_datasources
from ui.components import render_accordion_result


def run() -> None:
    st.subheader("データソース情報を取得")
    if st.button("実行", key="ds_run"):
        step_placeholder = st.empty()
        step_placeholder.info("🔄 **処理中:** データソース情報を取得しています...")
        result = fetch_datasources()
        step_placeholder.success("✅ **完了:** データソース情報を取得しました")
        render_accordion_result("取得結果", result, expanded=True)
