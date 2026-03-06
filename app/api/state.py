"""HITL 用のインメモリ状態（Streamlit と連動）。"""
_last_checkout_result: dict | None = None
_last_requirement_ready_ack: dict | None = None


def get_last_checkout_result() -> dict | None:
    return _last_checkout_result


def set_last_checkout_result(value: dict | None) -> None:
    global _last_checkout_result
    _last_checkout_result = value


def get_last_requirement_ready_ack() -> dict | None:
    return _last_requirement_ready_ack


def set_last_requirement_ready_ack(value: dict | None) -> None:
    global _last_requirement_ready_ack
    _last_requirement_ready_ack = value


def clear_checkout_result() -> None:
    set_last_checkout_result(None)


def clear_requirement_ready_ack() -> None:
    set_last_requirement_ready_ack(None)
