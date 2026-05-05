#!/usr/bin/env python3
"""
Z-Library Login - 一次性登录，保存会话状态
首次运行此脚本完成手动登录，之后 download_books.py 可全自动运行
"""
import asyncio
import json
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright 未安装，正在安装...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    from playwright.sync_api import sync_playwright


SESSION_FILE = Path(__file__).parent / "zlibrary_session.json"
ZLIBS = [
    "https://zh.zlib.li/",
    "https://z-library.sk/",
    "https://1lib.sk/",
]


def save_session(cookies: dict, userid: str = None, userkey: str = None):
    data = {
        "cookies": cookies,
        "remix_userid": userid,
        "remix_userkey": userkey,
    }
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n会话已保存到: {SESSION_FILE}")


def try_get_tokens_from_cookies(cookies: list) -> tuple:
    """从cookies中提取remix_userid和remix_userkey"""
    cookie_dict = {c["name"]: c["value"] for c in cookies}
    userid = cookie_dict.get("remix_userid")
    userkey = cookie_dict.get("remix_userkey")
    return userid, userkey


def zlibrary_login():
    """使用Playwright登录Z-Library并保存会话"""
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(Path.home() / ".zlibrary_browser"),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        for url in ZLIBS:
            print(f"\n尝试访问: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                if "z-library" in page.url.lower() or "zlib" in page.url.lower():
                    print(f"成功访问: {page.url}")
                    break
            except Exception as e:
                print(f"  访问失败: {e}")
                continue

        print("\n" + "=" * 60)
        print("Z-Library 登录")
        print("=" * 60)
        print("\n请在浏览器中:")
        print("  1. 如未登录，请先登录账号")
        print("  2. 等待页面完全加载")
        print("  3. 回到此窗口按 ENTER")
        print("=" * 60)

        input("\n已完成登录？按 ENTER 保存会话... ")

        # 获取cookies
        cookies = page.context.cookies()
        userid, userkey = try_get_tokens_from_cookies(cookies)

        if not userid or not userkey:
            print("\n未找到 remix_userid/remix_userkey cookie，尝试从页面提取...")

            try:
                userid = page.evaluate("() => localStorage.getItem('remix_userid')")
                userkey = page.evaluate("() => localStorage.getItem('remix_userkey')")
            except:
                pass

        if userid and userkey:
            print(f"找到用户ID: {userid}")
            save_session({}, userid, userkey)
        else:
            # 保存所有cookies作为后备
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            save_session(cookie_dict, None, None)
            print("\n警告: 未找到完整的登录凭证，已保存cookies")
            print("如果后续下载失败，请重新运行此脚本")

        browser.close()


def check_session():
    """检查现有会话是否有效"""
    if not SESSION_FILE.exists():
        return False, "会话文件不存在"

    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        userid = data.get("remix_userid")
        userkey = data.get("remix_userkey")

        if userid and userkey:
            return True, f"会话有效 (userid={userid})"
        else:
            return False, "会话不完整，缺少userid或userkey"
    except Exception as e:
        return False, f"读取会话失败: {e}"


if __name__ == "__main__":
    if "--check" in sys.argv:
        ok, msg = check_session()
        print(f"会话状态: {'有效' if ok else '无效'} - {msg}")
        sys.exit(0 if ok else 1)

    print("=" * 60)
    print("Z-Library 登录工具")
    print("=" * 60)

    ok, msg = check_session()
    if ok:
        print(f"\n已有有效会话: {msg}")
        resp = input("是否重新登录？(y/N): ").strip().lower()
        if resp != "y":
            print("退出")
            sys.exit(0)

    zlibrary_login()
