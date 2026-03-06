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
                if name.startswith("notify_") and name.endswith(".json"):
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

                        if backend_url and branch_name:
                            global _pending_checkout
                            _pending_checkout = {
                                "backend_url": backend_url,
                                "branch_name": branch_name,
                                "base_branch": base_branch,
                                "repo_path": repo_path,
                            }

                            def on_click(args):
                                global _pending_checkout
                                # 文字列ボタンのとき arguments は "http:承認" または "http:却下"
                                a = (args.get("arguments") or "")
                                if "承認" not in a:
                                    return  # 却下の場合は何もしない
                                p = _pending_checkout
                                _pending_checkout = None
                                if not p:
                                    return
                                try:
                                    req = urllib.request.Request(
                                        f"{p['backend_url']}/branch/checkout",
                                        data=json.dumps({
                                            "branch_name": p["branch_name"],
                                            "base_branch": p.get("base_branch") or "main",
                                            "repo_path": p.get("repo_path") or None,
                                        }).encode("utf-8"),
                                        method="POST",
                                        headers={"Content-Type": "application/json"},
                                    )
                                    with urllib.request.urlopen(req, timeout=60) as resp:
                                        if 200 <= resp.status < 300:
                                            toast("チェックアウト完了", f"{p['branch_name']} を作成してチェックアウトしました。", duration="short")
                                except Exception as err:
                                    toast("チェックアウト失敗", str(err)[:100], duration="long")
                                    print(f"Checkout error: {err}", file=sys.stderr)

                            # 両方のボタンが表示されるよう dict で明示
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
