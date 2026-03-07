"""GitHub ブランチ作成とローカル git チェックアウト。"""
import os
import subprocess
import tempfile

import httpx

from config import get_settings

async def create_branch_on_github(
    branch_name: str,
    base_branch: str,
    *,
    github_token: str,
    github_repo: str,
) -> bool:
    """
    リモートにブランチを作成する。既に存在する場合は 422 を無視して False を返す。
    戻り値: 作成した場合 True、既存の場合は False。
    """
    if not github_token or not github_repo or "/" not in github_repo:
        return False
    owner, repo = github_repo.strip().split("/", 1)
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        ref_res = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{base_branch}",
            headers=headers,
        )
        if ref_res.status_code != 200:
            raise RuntimeError(
                f"GitHub ref fetch failed (base_branch={base_branch}): {ref_res.text[:200]}"
            )
        sha = ref_res.json()["object"]["sha"]
        create_res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )
        if create_res.status_code in (200, 201):
            return True
        if create_res.status_code == 422:
            return False
        raise RuntimeError(
            f"GitHub create branch failed ({create_res.status_code}): {create_res.text[:300]}"
        )


def do_local_checkout(target_repo_path: str, branch_name: str) -> None:
    """
    ローカルで指定ブランチをチェックアウトする。同期関数。
    run_in_threadpool で呼ぶこと。
    """
    if not os.path.isdir(os.path.join(target_repo_path, ".git")):
        raise RuntimeError(f"Not a git repo: {target_repo_path}")
    settings = get_settings()
    token = (settings.GITHUB_TOKEN or "").strip()

    run_env = os.environ.copy()
    askpass_script = None
    if token:
        fd, askpass_script = tempfile.mkstemp(prefix="git_askpass_", suffix=".sh")
        os.close(fd)
        with open(askpass_script, "w") as f:
            f.write(
                "#!/bin/sh\n"
                'case "$1" in *[Pp]assword*) echo "${GITHUB_TOKEN}";; *) echo "x-access-token";; esac\n'
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

        run(["config", "core.autocrlf", "false"], timeout=5)
        run(["config", "core.eol", "lf"], timeout=5)

        # ローカルリポジトリの既存リモート設定を使用する（origin を変更しない）
        # ユーザーが指定したローカルリポジトリが正しく設定されていることを前提

        code, out = run(["fetch", "origin"], timeout=60)
        if code != 0:
            raise RuntimeError(f"git fetch failed: {out}")

        code, _ = run(["rev-parse", "--verify", "-q", branch_name], timeout=5)
        if code == 0:
            code2, out2 = run(["checkout", branch_name], timeout=15)
            if code2 != 0:
                raise RuntimeError(f"git checkout failed: {out2}")
            return

        code, _ = run(["rev-parse", "--verify", "-q", f"origin/{branch_name}"], timeout=5)
        if code == 0:
            code2, out2 = run(["checkout", "-b", branch_name, f"origin/{branch_name}"], timeout=15)
            if code2 != 0:
                raise RuntimeError(f"git checkout -b failed: {out2}")
            return

        run(["fetch", "origin", branch_name], timeout=30)
        code, _ = run(["rev-parse", "--verify", "-q", f"origin/{branch_name}"], timeout=5)
        if code == 0:
            code2, out2 = run(["checkout", "-b", branch_name, f"origin/{branch_name}"], timeout=15)
            if code2 != 0:
                raise RuntimeError(f"git checkout -b failed: {out2}")
            return

        code2, out2 = run(["checkout", "-b", branch_name], timeout=15)
        if code2 != 0:
            raise RuntimeError(f"git checkout -b failed: {out2}")
    finally:
        if askpass_script and os.path.isfile(askpass_script):
            try:
                os.unlink(askpass_script)
            except OSError:
                pass
