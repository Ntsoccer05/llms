"""ブランチチェックアウト・状態 API。"""
import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from config import get_settings
from api.schemas import BranchCheckoutRequest
from api.state import (
    get_last_checkout_result,
    set_last_checkout_result,
    clear_checkout_result,
)
from services.branch_service import create_branch_on_github, do_local_checkout

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/branch", tags=["branch"])


@router.get("/checkout/status")
async def branch_checkout_status():
    """直近のチェックアウト結果を返す。デスクトップ通知で「承認」したあと Streamlit が連動するために使う。"""
    result = get_last_checkout_result()
    if result is None:
        return {}
    return result


@router.post("/checkout/status/clear")
async def branch_checkout_status_clear():
    """「クリアして最初から」時に Streamlit から呼ばれ、直近のチェックアウト結果を破棄する。"""
    clear_checkout_result()
    return {"ok": True}


@router.get("/repo/discover")
async def discover_repositories():
    """ホストの HOST_REPO_PATH 内にある Git リポジトリを探す（host_path はホスト側パス）。"""
    host_path_on_host = os.getenv("HOST_REPO_PATH_ON_HOST", "C:\\WorkSpace")
    container_path = "/host_repos"

    repo_paths = []
    if os.path.isdir(container_path):
        for entry in os.listdir(container_path):
            full_path = os.path.join(container_path, entry)
            if os.path.isdir(full_path) and os.path.isdir(os.path.join(full_path, ".git")):
                # ホスト側パスをWindows形式で返す
                host_side_path = os.path.join(host_path_on_host, entry).replace("/", "\\")
                repo_paths.append({
                    "name": entry,
                    "path": full_path,
                    "host_path": host_side_path,
                    "type": "git",
                })
    return {"repos": repo_paths}


@router.post("/checkout")
async def branch_checkout(body: BranchCheckoutRequest):
    """
    Human-in-the-loop: 指定ブランチを GitHub に作成し、ローカルでチェックアウトする。
    base_branch: ユーザー指定のベースブランチ（例: main, develop）。未指定時は main。
    repo_path: ユーザー指定のローカルフォルダ。未指定時は config の REPO_PATH。
    """
    logger.info(f"branch_checkout received body.branch_name={body.branch_name}, body.base_branch={body.base_branch}, body.repo_path={body.repo_path}, body.github_repo={body.github_repo}")
    settings = get_settings()
    branch_name = (body.branch_name or "").strip()
    if not branch_name:
        raise HTTPException(status_code=400, detail="branch_name is required")

    base_branch = (body.base_branch or "").strip() or "main"
    repo_path = (settings.REPO_PATH or "").strip()
    target_repo_path = (body.repo_path or "").strip() or repo_path
    if target_repo_path and not os.path.isdir(target_repo_path) and repo_path:
        target_repo_path = repo_path
    if target_repo_path and not os.path.isdir(target_repo_path):
        target_repo_path = ""

    result = {"branch_name": branch_name, "remote_created": False, "local_checked_out": False}

    # GitHub リポジトリが設定されているかチェック（ユーザー入力を優先）
    github_token = settings.GITHUB_TOKEN or ""
    github_repo = (body.github_repo or settings.GITHUB_REPO or "").strip()
    logger.info(f"branch_checkout: body.github_repo={body.github_repo}, settings.GITHUB_REPO={settings.GITHUB_REPO}, final github_repo={github_repo}")
    if github_token and github_repo and "/" in github_repo:
        try:
            remote_created = await create_branch_on_github(
                branch_name,
                base_branch,
                github_token=github_token,
                github_repo=github_repo,
            )
            result["remote_created"] = remote_created
        except RuntimeError as e:
            msg = str(e)
            logger.error("branch_checkout: %s", msg)
            set_last_checkout_result({
                "branch_name": branch_name,
                "result": "checkout_failed",
                "detail": msg[:500],
            })
            raise HTTPException(status_code=502, detail=msg)

    if target_repo_path:
        try:
            await run_in_threadpool(do_local_checkout, target_repo_path, branch_name)
            result["local_checked_out"] = True
        except Exception as e:
            logger.exception("branch checkout failed: %s", e)
            set_last_checkout_result({
                "branch_name": branch_name,
                "result": "checkout_failed",
                "detail": str(e)[:500],
            })
            raise HTTPException(status_code=502, detail=str(e))

    set_last_checkout_result({
        "branch_name": branch_name,
        "result": "checkout_ok",
        "detail": f"リモート作成: {result.get('remote_created')}, ローカルチェックアウト: {result.get('local_checked_out')}",
    })
    return result
