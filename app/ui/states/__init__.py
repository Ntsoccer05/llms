"""HITL 用 session_state キーとクリア処理（ウィジェット key とは別のキーのみ）。"""
HITL_KEYS = (
    "hitl_branch_name",
    "hitl_pending_base_branch",
    "hitl_pending_repo_path",
    "hitl_result",
    "hitl_result_detail",
    "hitl_markdown_content",
    "hitl_requirement_md",
    "hitl_requirement_steps",
    "hitl_requirement_thinking",
    "hitl_requirement_ack",
    "hitl_requirement_ack_triggered",
    "hitl_available_repos",
    "hitl_container_repo_path",
    "hitl_prev_selected_idx",
)


def clear_hitl_state(st) -> None:
    for k in HITL_KEYS:
        st.session_state.pop(k, None)
