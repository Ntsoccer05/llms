"""requirement.md 生成・承認状態 API。"""
import json
import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from config import get_settings
from api.schemas import RequirementGenerateRequest, RequirementReadyAckRequest
from api.state import (
    get_last_requirement_ready_ack,
    set_last_requirement_ready_ack,
    clear_requirement_ready_ack,
)
from utils.requirement_generate import generate_requirement_md, stream_requirement_md_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/requirement", tags=["requirement"])


def _resolve_repo_path(repo_path_from_body: str | None) -> str:
    settings = get_settings()
    repo_path = (settings.REPO_PATH or "").strip()
    target = (repo_path_from_body or "").strip() or repo_path
    if target and not os.path.isdir(target) and repo_path:
        target = repo_path
    if target and not os.path.isdir(target):
        target = ""
    return target


@router.post("/ready/ack")
async def requirement_ready_ack(body: RequirementReadyAckRequest):
    """デスクトップ通知「requirement.md を生成しますか？」の承認・却下を記録する。"""
    action = (body.action or "").strip().lower()
    if action not in ("approved", "rejected"):
        action = "rejected"
    set_last_requirement_ready_ack({
        "branch_name": (body.branch_name or "").strip(),
        "action": action,
    })
    return {"ok": True}


@router.get("/ready/ack")
async def requirement_ready_ack_status():
    """直近の「requirement.md を生成しますか？」承認・却下を返す。"""
    data = get_last_requirement_ready_ack()
    if data is None:
        return {}
    return data


@router.post("/ready/ack/clear")
async def requirement_ready_ack_clear():
    """「クリアして最初から」時に Streamlit から呼ばれ、直近の承認・却下を破棄する。"""
    clear_requirement_ready_ack()
    return {"ok": True}


@router.post("/generate")
async def requirement_generate(body: RequirementGenerateRequest):
    """
    Notion の本文（マークダウン）と対象フォルダを元に LLM で requirement.md を生成する。
    戻り値: branch_name, requirement_md, steps（アコーディオン用）
    """
    settings = get_settings()
    import boto3
    markdown_body = (body.markdown_body or "").strip()
    branch_name = (body.branch_name or "").strip()
    target_repo_path = _resolve_repo_path(body.repo_path)
    aws_session = boto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or "",
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or "",
        region_name=settings.AWS_DEFAULT_REGION or "us-east-1",
    )

    def _generate():
        return generate_requirement_md(
            markdown_body,
            branch_name,
            target_repo_path or None,
            settings.MODEL_ID or "",
            aws_session,
        )

    try:
        requirement_md, steps = await run_in_threadpool(_generate)
        return {
            "branch_name": branch_name,
            "requirement_md": requirement_md,
            "steps": steps,
        }
    except Exception as e:
        logger.exception("requirement generate failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/generate/stream")
async def requirement_generate_stream(body: RequirementGenerateRequest):
    """
    requirement.md をストリーミング生成する。SSE で思考過程（thinking）と本文（content）を送り、最後に done で requirement_md と steps を返す。
    """
    settings = get_settings()
    import boto3
    markdown_body = (body.markdown_body or "").strip()
    branch_name = (body.branch_name or "").strip()
    target_repo_path = _resolve_repo_path(body.repo_path)
    aws_session = boto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or "",
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or "",
        region_name=settings.AWS_DEFAULT_REGION or "us-east-1",
    )

    async def sse_events():
        try:
            async for kind, data in stream_requirement_md_async(
                markdown_body,
                branch_name,
                target_repo_path or None,
                settings.MODEL_ID or "",
                aws_session,
            ):
                payload = json.dumps(data, ensure_ascii=False)
                yield f"event: {kind}\ndata: {payload}\n\n"
        except Exception as e:
            logger.exception("requirement generate stream failed: %s", e)
            yield f"event: error\ndata: {json.dumps(str(e), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
