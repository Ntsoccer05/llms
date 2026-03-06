"""操作ごとの Workflow（1 操作 = 1 モジュール）。"""
import streamlit as st

from .database import run as run_database
from .datasource import run as run_datasource
from .search import run as run_search
from .datasource_search import run as run_datasource_search
from .page_get import run as run_page_get
from .page_detail_blocks import run as run_page_detail_blocks
from .hitl import run as run_hitl

OPERATIONS = [
    "データベース情報を取得",
    "データソース情報を取得",
    "文字列検索",
    "タスクIDでデータソース検索",
    "タスクIDでページ取得",
    "タスクIDでページ詳細取得（ブロック一覧）",
    "ページ詳細＋ブランチ名取得（Human-in-the-loop）",
]

WORKFLOW_MAP = {
    "データベース情報を取得": run_database,
    "データソース情報を取得": run_datasource,
    "文字列検索": run_search,
    "タスクIDでデータソース検索": run_datasource_search,
    "タスクIDでページ取得": run_page_get,
    "タスクIDでページ詳細取得（ブロック一覧）": run_page_detail_blocks,
    "ページ詳細＋ブランチ名取得（Human-in-the-loop）": run_hitl,
}


def run_workflow(operation: str) -> None:
    fn = WORKFLOW_MAP.get(operation)
    if fn:
        fn()
    else:
        st.warning(f"未実装: {operation}")
