"""HITL 用 session_state キーとクリア処理（ウィジェット key とは別のキーのみ）。"""
HITL_KEYS = (
    "hitl_branch_name",
    "hitl_pending_base_branch",
    "hitl_pending_repo_path",
    "hitl_result",
    "hitl_result_detail",
)


def clear_hitl_state(st) -> None:
    for k in HITL_KEYS:
        st.session_state.pop(k, None)
