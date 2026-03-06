#!/usr/bin/env python3
"""
win11toast でトーストにボタンが表示されるか確認するテスト。
実行: python scripts/test_toast_button.py
「承認」ボタンまたは「Test」ボタンが表示されれば、環境ではボタンがサポートされています。
"""
import sys

def main():
    try:
        from win11toast import toast
    except ImportError:
        print("win11toast がありません: pip install win11toast")
        sys.exit(1)

    def on_click(args):
        print("Clicked:", args.get("arguments"))

    # 単一ボタンで試す（環境によってはこちらだけ表示される）
    print("Showing toast with single button '承認'...")
    toast("テスト", "ボタンが表示されますか？", duration="long", button="承認", on_click=on_click)
    print("If you saw a button on the toast, it works. Check the toast on your taskbar.")


if __name__ == "__main__":
    main()
