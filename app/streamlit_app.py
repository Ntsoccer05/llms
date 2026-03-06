"""Notion API 操作の Streamlit GUI。"""
import streamlit as st

from ui.workflows import OPERATIONS, run_workflow

st.set_page_config(page_title="Notion API GUI", layout="wide")
st.title("Notion API 操作 GUI")

operation = st.sidebar.radio("実行する操作", OPERATIONS)
run_workflow(operation)
