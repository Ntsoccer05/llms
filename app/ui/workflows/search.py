"""文字列検索"""
import streamlit as st
from notion_api import search
from ui.components import render_accordion_result


def run() -> None:
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
