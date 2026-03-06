"""共通 UI コンポーネント。"""
import streamlit as st


def render_accordion_result(title: str, data, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        if isinstance(data, (dict, list)):
            st.json(data)
        else:
            st.write(data)


def show_notion_error(error_msg: str, step_placeholder=None) -> None:
    if step_placeholder:
        step_placeholder.error(f"❌ エラー: {error_msg}")
    else:
        st.error(f"❌ エラー: {error_msg}")
    if "database" in error_msg.lower() and "shared with your integration" in error_msg.lower():
        st.warning(
            "**対処方法:** Notion で対象のデータベース（またはデータソースが参照するデータベース）を "
            "インテグレーションと共有してください。\n\n"
            "1. Notion で該当データベースのページを開く\n"
            "2. 右上の「…」→「接続」→ 使用中のインテグレーションを追加\n"
            "3. または .env の `NOTION_DATABASE_ID` / `NOTION_DATASOURCE_ID` が正しいか確認"
        )
