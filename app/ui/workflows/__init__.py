"""操作ごとの Workflow（1 操作 = 1 モジュール）。"""
import streamlit as st

from .hitl import run as run_hitl

OPERATIONS = [
    "ページ詳細＋ブランチ名取得",
]

WORKFLOW_MAP = {
    "ページ詳細＋ブランチ名取得": run_hitl,
}


def run_workflow(operation: str) -> None:
    fn = WORKFLOW_MAP.get(operation)
    if fn:
        fn()
    else:
        st.warning(f"未実装: {operation}")
