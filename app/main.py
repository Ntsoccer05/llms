import os
import logging
import tempfile
import httpx
import boto3
import subprocess
from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from config import get_settings
from utils.format import (
  blocks_to_markdown,
  extract_page_id_from_url,
  get_task_id_from_page_data,
  get_task_title_from_page_data,
)
from utils.status import check_contains_tag
from utils.branch_name import build_github_branch_name

app = FastAPI()

notion_api_key = get_settings().NOTION_API_KEY
notion_api_url = get_settings().NOTION_API_URL
datasource_id = get_settings().NOTION_DATASOURCE_ID
database_id = get_settings().NOTION_DATABASE_ID
model_id = get_settings().MODEL_ID
aws_access_key_id = get_settings().AWS_ACCESS_KEY_ID
aws_secret_access_key = get_settings().AWS_SECRET_ACCESS_KEY
aws_default_region = get_settings().AWS_DEFAULT_REGION

aws_session = boto3.Session(
  aws_access_key_id=aws_access_key_id,
  aws_secret_access_key=aws_secret_access_key,
  region_name=aws_default_region
)

github_token = get_settings().GITHUB_TOKEN
github_repo = get_settings().GITHUB_REPO
repo_path = get_settings().REPO_PATH

headers = {
  'Authorization': f"Bearer {notion_api_key}",
  'Notion-Version': '2025-09-03'
}

@app.get("/")
async def databases():
  async with httpx.AsyncClient() as client:
    response = await client.get(
      f"{notion_api_url}/databases/{database_id}",
      headers=headers,
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}
    
@app.get("/datasources")
async def datasources():
  async with httpx.AsyncClient() as client:
    response = await client.get(
      f"{notion_api_url}/data_sources/{datasource_id}",
      headers=headers,
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}

"""文字列検索"""    
@app.post("/search")
async def search(query: str):
  search_headers = headers.copy()
  add_header = {
    "Content-Type": "application/json"
  }
  search_headers.update(add_header)
  payload = {
    "query": query,
    "filter": {
        "property": "object",
        "value": "page"
    },
    "sort": {
        "timestamp": "last_edited_time",
        "direction": "ascending"
    }
  }
  async with httpx.AsyncClient() as client:
    response = await client.post(
      f"{notion_api_url}/search",
      headers=search_headers,
      json=payload
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}

"""タスクIDによる検索"""
@app.post("/search/datasource")
async def search_by_datasource(task_id: str):
  number = task_id.replace("ES-", "").replace("ES", "")
  
  payload = {
    "filter": {
        "property": "タスクID",
        "unique_id": {
            "equals": int(number)
        }
    }
  }
  
  async with httpx.AsyncClient() as client:
    response = await client.post(
      f"{notion_api_url}/data_sources/{datasource_id}/query",
      headers=headers,
      json=payload
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}
    
@app.get("/page")
async def page(task_id: str):
  datasource = await search_by_datasource(task_id)
  page_id = extract_page_id_from_url(datasource["results"][0]['url'])

  async with httpx.AsyncClient() as client:
    response = await client.get(
      f"{notion_api_url}/pages/{page_id}",
      headers=headers
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}
    
@app.get("/page/detail")
async def page_detail(task_id: str):
  bug_tag = False
  datasource = await search_by_datasource(task_id)
  page_id = extract_page_id_from_url(datasource["results"][0]['url'])
  async with httpx.AsyncClient() as client:
    # ページ基本情報を取得
    page_response = await client.get(
      f"{notion_api_url}/pages/{page_id}",
      headers=headers
    )

    if page_response.status_code != 200:
      return {"error": page_response.text}

    page_data = page_response.json()

    # すべてのブロックを取得（ページネーション + 子ブロック対応）
    async def get_blocks_recursive(block_id):
      all_blocks = []
      next_cursor = None

      while True:
        params = {}
        if next_cursor:
          params['start_cursor'] = next_cursor

        blocks_response = await client.get(
          f"{notion_api_url}/blocks/{block_id}/children",
          headers=headers,
          params=params
        )

        if blocks_response.status_code != 200:
          break

        blocks_data = blocks_response.json()

        # 各ブロックについて、has_children なら子ブロックも取得
        for block in blocks_data.get("results", []):
          if block.get("has_children"):
            block["children"] = await get_blocks_recursive(block["id"])
          all_blocks.append(block)

        if not blocks_data.get("has_more"):
          break

        next_cursor = blocks_data.get("next_cursor")

      return all_blocks

    blocks = await get_blocks_recursive(page_id)

    # マークダウンに変換
    markdown_content = blocks_to_markdown(blocks)

    # チェック
    if check_contains_tag(page_data, "バグ"):
      bug_tag = True

    # GitHub ブランチ名: bug/{タスクID}/{スラッグ} または feature/{タスクID}/{スラッグ}
    task_id = get_task_id_from_page_data(page_data)
    task_title = get_task_title_from_page_data(page_data)
    branch_name = await run_in_threadpool(
      build_github_branch_name,
      task_id,
      task_title,
      bug_tag,
      model_id,
      aws_session,
    )

    return {
      "bug_tag": bug_tag,
      "branch_name": branch_name,
      "markdown_content": markdown_content,
    }


class BranchCheckoutRequest(BaseModel):
  branch_name: str
  base_branch: str | None = None   # どのブランチをベースに切るか（未指定時は main）
  repo_path: str | None = None     # ローカルリポジトリのパス（未指定時は config の REPO_PATH）


@app.post("/branch/checkout")
async def branch_checkout(body: BranchCheckoutRequest):
  """
  Human-in-the-loop: 指定ブランチを GitHub に作成し、ローカルでチェックアウトする。
  base_branch: ユーザー指定のベースブランチ（例: main, develop）。未指定時は main。
  repo_path: ユーザー指定のローカルフォルダ。未指定時は config の REPO_PATH。
  """
  branch_name = (body.branch_name or "").strip()
  if not branch_name:
    raise HTTPException(status_code=400, detail="branch_name is required")

  base_branch = (body.base_branch or "").strip() or "main"
  target_repo_path = (body.repo_path or "").strip() or repo_path
  # バックエンドが Docker のとき、渡されたパスがコンテナに無い（例: C:\...）場合は config の REPO_PATH を使う
  if target_repo_path and not os.path.isdir(target_repo_path) and repo_path:
    target_repo_path = repo_path
  if target_repo_path and not os.path.isdir(target_repo_path):
    target_repo_path = ""

  result = {"branch_name": branch_name, "remote_created": False, "local_checked_out": False}

  # リモートにブランチ作成（GITHUB_TOKEN + GITHUB_REPO がある場合）
  if github_token and github_repo and "/" in github_repo:
    owner, repo = github_repo.strip().split("/", 1)
    gh_headers = {
      "Authorization": f"Bearer {github_token}",
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
      # ユーザー指定のベースブランチの SHA を取得
      ref_res = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{base_branch}",
        headers=gh_headers,
      )
      if ref_res.status_code != 200:
        msg = f"GitHub ref fetch failed (base_branch={base_branch}): {ref_res.text[:200]}"
        logger.error("branch_checkout: %s", msg)
        raise HTTPException(status_code=502, detail=msg)
      sha = ref_res.json()["object"]["sha"]
      create_res = await client.post(
        f"https://api.github.com/repos/{owner}/{repo}/git/refs",
        headers=gh_headers,
        json={"ref": f"refs/heads/{branch_name}", "sha": sha},
      )
      if create_res.status_code in (200, 201):
        result["remote_created"] = True
      elif create_res.status_code == 422:
        # ブランチが既に存在する場合はそのままローカル checkout へ
        pass
      else:
        msg = f"GitHub create branch failed ({create_res.status_code}): {create_res.text[:300]}"
        logger.error("branch_checkout: %s", msg)
        raise HTTPException(status_code=502, detail=msg)

  # ローカルでチェックアウト（repo_path がある場合）
  # 注意: バックエンドが Docker のときは target_repo_path はコンテナ内のパス。ホストのフォルダで checkout したい場合はバックエンドをローカルで実行するか、コンテナにマウントされたパスを指定する。
  if target_repo_path:
    def _git_checkout():
      if not os.path.isdir(os.path.join(target_repo_path, ".git")):
        raise RuntimeError(f"Not a git repo: {target_repo_path}")

      settings = get_settings()
      token = (settings.GITHUB_TOKEN or "").strip()
      repo_spec = (settings.GITHUB_REPO or "").strip()

      # git 実行時の環境（HTTPS で認証を聞かれないようにする）
      run_env = os.environ.copy()
      askpass_script = None
      if token:
        fd, askpass_script = tempfile.mkstemp(prefix="git_askpass_", suffix=".sh")
        os.close(fd)
        with open(askpass_script, "w") as f:
          f.write(
            "#!/bin/sh\n"
            "case \"$1\" in *[Pp]assword*) echo \"${GITHUB_TOKEN}\";; *) echo \"x-access-token\";; esac\n"
          )
        os.chmod(askpass_script, 0o700)
        run_env["GIT_ASKPASS"] = askpass_script
        run_env["GITHUB_TOKEN"] = token
      try:
        def run(cmd, timeout=60):
          r = subprocess.run(
            ["git", "-C", target_repo_path] + cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
          )
          return r.returncode, (r.stdout or "") + (r.stderr or "")

        # 0) origin をトークン付き URL にしておく（fetch で認証を通す）
        if token and repo_spec and "/" in repo_spec:
          owner, repo = repo_spec.split("/", 1)
          auth_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
          code0, _ = run(["remote", "set-url", "origin", auth_url], timeout=5)
          if code0 != 0:
            run(["remote", "add", "origin", auth_url], timeout=5)

        # 1) fetch でリモートの最新を取得
        code, out = run(["fetch", "origin"], timeout=60)
        if code != 0:
          raise RuntimeError(f"git fetch failed: {out}")

        # 2) 既にローカルにブランチがある → git checkout のみ
        code, _ = run(["rev-parse", "--verify", "-q", branch_name], timeout=5)
        if code == 0:
          code2, out2 = run(["checkout", branch_name], timeout=15)
          if code2 != 0:
            raise RuntimeError(f"git checkout failed: {out2}")
          return True

        # 3) リモートにブランチがある → git checkout -b で追跡付き作成
        code, _ = run(["rev-parse", "--verify", "-q", f"origin/{branch_name}"], timeout=5)
        if code == 0:
          code2, out2 = run(["checkout", "-b", branch_name, f"origin/{branch_name}"], timeout=15)
          if code2 != 0:
            raise RuntimeError(f"git checkout -b failed: {out2}")
          return True

        # 4) どちらにも無い（直前に GitHub で作成した場合など）→ もう一度 fetch してから試す
        run(["fetch", "origin", branch_name], timeout=30)
        code, _ = run(["rev-parse", "--verify", "-q", f"origin/{branch_name}"], timeout=5)
        if code == 0:
          code2, out2 = run(["checkout", "-b", branch_name, f"origin/{branch_name}"], timeout=15)
          if code2 != 0:
            raise RuntimeError(f"git checkout -b failed: {out2}")
          return True

        # 5) まだ無い場合は現在 HEAD から -b で作成（フォールバック）
        code2, out2 = run(["checkout", "-b", branch_name], timeout=15)
        if code2 != 0:
          raise RuntimeError(f"git checkout -b failed: {out2}")
        return True
      finally:
        if askpass_script and os.path.isfile(askpass_script):
          try:
            os.unlink(askpass_script)
          except OSError:
            pass

    try:
      await run_in_threadpool(_git_checkout)
      result["local_checked_out"] = True
    except Exception as e:
      logger.exception("branch checkout failed: %s", e)
      raise HTTPException(status_code=502, detail=str(e))

  return result