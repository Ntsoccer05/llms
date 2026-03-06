"""Notion API 操作の Streamlit GUI。"""
import streamlit as st

from ui.workflows import OPERATIONS, run_workflow

st.set_page_config(page_title="Notion - GitHub AIエージェント", layout="wide")
st.title("Notion - GitHub AIエージェント")

operation = st.sidebar.radio("実行する操作", OPERATIONS)
run_workflow(operation)
