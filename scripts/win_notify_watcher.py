#!/usr/bin/env python3
"""
Windows で PC デスクトップにトースト通知を出す watcher。
Docker 内の Streamlit が NOTIFY_DIR に書き出した JSON を監視し、
win11toast で表示する。ブラウザを閉じていても通知が出る。

使い方（Windows で実行）:
  pip install win11toast
  python scripts/win_notify_watcher.py [監視フォルダ]
  または環境変数 NOTIFY_DIR で監視フォルダを指定。

Docker の例:
  docker compose で streamlit に NOTIFY_DIR=/notify とボリューム ./notify_data:/notify を設定。
  Windows で: python scripts/win_notify_watcher.py C:\\path\\to\\notify_data
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

# トーストの「承認」クリック時に API を呼ぶためのペイロード（直近1件、文字列ボタンでは id を渡せないため）
_pending_checkout = None


def main():
    if len(sys.argv) >= 2:
        watch_dir = os.path.abspath(sys.argv[1])
    else:
        watch_dir = (os.environ.get("NOTIFY_DIR") or "").strip()
        if watch_dir:
            watch_dir = os.path.abspath(watch_dir)
    if not watch_dir:
        print("Usage: python win_notify_watcher.py <watch_dir>", file=sys.stderr)
        print("  Or set env NOTIFY_DIR to the watch folder.", file=sys.stderr)
        sys.exit(1)

    try:
        os.makedirs(watch_dir, exist_ok=True)
    except Exception as e:
        print(f"Cannot create watch dir: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        from win11toast import toast
    except ImportError:
        print("Need win11toast: pip install win11toast", file=sys.stderr)
        sys.exit(1)

    # 起動したことをトーストで表示（watcher が動いている・win11toast が使える確認）
    try:
        toast("Notify watcher started", f"Watching: {watch_dir}", duration="short")
    except Exception:
        pass

    print(f"Watching: {watch_dir}")
    print("Close this window to stop the watcher.")
    sys.stdout.flush()
    seen = set()
    while True:
        try:
            for name in os.listdir(watch_dir):
                if (name.startswith("notify_") or name.startswith("notify_req_")) and name.endswith(".json"):
                    path = os.path.join(watch_dir, name)
                    if path in seen:
                        continue
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        title = data.get("title", "通知")
                        body = data.get("body", "")
                        branch_name = data.get("branch_name", "")
                        backend_url = (data.get("backend_url") or "").strip()
                        base_branch = (data.get("base_branch") or "main").strip()
                        repo_path = (data.get("repo_path") or "").strip()
                        notify_type = (data.get("type") or "").strip()

                        if notify_type == "requirement_complete":
                            toast(title, body, duration="long")
                        elif notify_type == "requirement_ready":
                            req_branch = (data.get("branch_name") or "").strip()
                            req_backend = (data.get("backend_url") or "").strip()
                            if "backend" in req_backend:
                                req_backend = os.environ.get("WATCHER_BACKEND_URL", "http://localhost:8000").strip() or "http://localhost:8000"
                            if req_branch and req_backend:
                                def _req_on_click(req_branch=req_branch, req_backend=req_backend):
                                    def _click(args):
                                        a = (args.get("arguments") or "")
                                        action = "approved" if "承認" in a else "rejected"
                                        try:
                                            body_json = json.dumps({"branch_name": req_branch, "action": action}).encode("utf-8")
                                            req = urllib.request.Request(
                                                f"{req_backend.rstrip('/')}/requirement/ready/ack",
                                                data=body_json,
                                                method="POST",
                                                headers={"Content-Type": "application/json"},
                                            )
                                            urllib.request.urlopen(req, timeout=10)
                                        except Exception:
                                            pass
                                    return _click
                                toast(
                                    title,
                                    body,
                                    duration="long",
                                    buttons=[
                                        {"activationType": "protocol", "arguments": "http:承認", "content": "承認"},
                                        {"activationType": "protocol", "arguments": "http:却下", "content": "却下"},
                                    ],
                                    on_click=_req_on_click(),
                                )
                            else:
                                toast(
                                    title,
                                    body,
                                    duration="long",
                                    buttons=[
                                        {"activationType": "protocol", "arguments": "http:承認", "content": "承認"},
                                        {"activationType": "protocol", "arguments": "http:却下", "content": "却下"},
                                    ],
                                )
                        elif backend_url and branch_name:
                            global _pending_checkout
                            _pending_checkout = {
                                "backend_url": backend_url,
                                "branch_name": branch_name,
                                "base_branch": base_branch,
                                "repo_path": repo_path,
                            }

                            def on_click(args):
                                global _pending_checkout
                                a = (args.get("arguments") or "")
                                if "承認" not in a:
                                    return
                                p = _pending_checkout
                                _pending_checkout = None
                                if not p:
                                    return
                                body_json = json.dumps({
                                    "branch_name": p["branch_name"],
                                    "base_branch": p.get("base_branch") or "main",
                                    "repo_path": p.get("repo_path") or None,
                                }).encode("utf-8")
                                urls_to_try = [p["backend_url"]]
                                # Docker の backend は Windows から解決できないので localhost に置き換え
                                if "backend" in (p.get("backend_url") or ""):
                                    urls_to_try.insert(0, os.environ.get("WATCHER_BACKEND_URL", "http://localhost:8000").strip() or "http://localhost:8000")
                                ok = False
                                last_err = None
                                for url in urls_to_try:
                                    if not url:
                                        continue
                                    try:
                                        req = urllib.request.Request(
                                            f"{url.rstrip('/')}/branch/checkout",
                                            data=body_json,
                                            method="POST",
                                            headers={"Content-Type": "application/json"},
                                        )
                                        with urllib.request.urlopen(req, timeout=180) as resp:
                                            if 200 <= resp.status < 300:
                                                toast("チェックアウト完了", f"{p['branch_name']} を作成してチェックアウトしました。", duration="short")
                                                ok = True
                                                # 成功時も「requirement.md を生成しますか？」を出す（デスクトップ承認では Streamlit が write_requirement_ready_notify を呼ばないため）
                                                req_url = url.rstrip("/") if url else (p.get("backend_url") or "")
                                                if "backend" in req_url:
                                                    req_url = os.environ.get("WATCHER_BACKEND_URL", "http://localhost:8000").strip() or "http://localhost:8000"
                                                try:
                                                    req_path = os.path.join(watch_dir, f"notify_req_{int(time.time() * 1000)}.json")
                                                    with open(req_path, "w", encoding="utf-8") as f:
                                                        json.dump({
                                                            "type": "requirement_ready",
                                                            "title": "requirement.md を生成しますか？",
                                                            "body": "ブランチ結果を確認し、requirement.md を生成できます。",
                                                            "branch_name": p.get("branch_name", ""),
                                                            "backend_url": req_url,
                                                        }, f, ensure_ascii=False)
                                                except Exception:
                                                    pass
                                                break
                                    except urllib.error.HTTPError as err:
                                        msg = f"HTTP {err.code}"
                                        try:
                                            body = err.read().decode("utf-8", errors="replace")
                                            try:
                                                d = json.loads(body)
                                                msg = (d.get("detail") or body or msg)[:400]
                                            except Exception:
                                                msg = (body or msg)[:400]
                                        except Exception:
                                            pass
                                        last_err = msg
                                    except Exception as err:
                                        last_err = str(err)[:400]
                                    if last_err:
                                        continue
                                if not ok and last_err:
                                    toast("チェックアウト失敗", last_err[:350], duration="long")
                                    print(f"Checkout error: {last_err}", file=sys.stderr)
                                    # 失敗時も「requirement.md を生成しますか？」を出す
                                    try:
                                        req_path = os.path.join(watch_dir, f"notify_req_{int(time.time() * 1000)}.json")
                                        with open(req_path, "w", encoding="utf-8") as f:
                                            json.dump({
                                                "type": "requirement_ready",
                                                "title": "requirement.md を生成しますか？",
                                                "body": "ブランチ結果を確認し、requirement.md を生成できます。",
                                                "branch_name": p.get("branch_name", ""),
                                                "backend_url": p.get("backend_url", ""),
                                            }, f, ensure_ascii=False)
                                    except Exception:
                                        pass

                            toast(
                                title,
                                body,
                                duration="long",
                                buttons=[
                                    {"activationType": "protocol", "arguments": "http:承認", "content": "承認"},
                                    {"activationType": "protocol", "arguments": "http:却下", "content": "却下"},
                                ],
                                on_click=on_click,
                            )
                        else:
                            toast(title, body, duration="long")
                    except Exception as e:
                        print(f"Error {path}: {e}", file=sys.stderr)
                    try:
                        seen.add(path)
                        os.remove(path)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Watch error: {e}", file=sys.stderr)
        time.sleep(1)


if __name__ == "__main__":
    main()
