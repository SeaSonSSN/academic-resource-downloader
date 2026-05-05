#!/usr/bin/env python3
"""
Z-Library 全自动书籍下载工具
API方式下载,直接获取下载链接,无需浏览器
"""
import os
import re
import time
from pathlib import Path
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 账号配置
EMAIL = "ben20050618@gmail.com"
PASSWORD = "231880029"

# 代理配置
PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

# Z-Library 域名（按稳定性排序）
DOMAINS = [
    "https://z-library.sk",
    "https://1lib.sk",
    "https://zh.zlib.li",
]

# 当前使用的域名（login成功后锁定）
CURRENT_DOMAIN = DOMAINS[0]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}

OUT_DIR = Path.home() / "Desktop" / "模拟IC书籍"
LOG_FILE = Path(__file__).parent / "download_log.txt"

# 模拟IC书籍（Gray和Razavi已手动放入）
BOOKS = [
    ("CMOS Analog Circuit Design", "Phillip E. Allen"),
    ("Analog Design Essentials", "Willy M.C. Sansen"),
    ("Analog Integrated Circuit Design", "David A. Johns"),
    ("The Art of Electronics", "Paul Horowitz"),
    ("The Art of Analog Layout", "Alan Hastings"),
]


def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def make_session():
    """创建带重试的requests session"""
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=3, status_forcelist=[502, 503, 504, 522, 520])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s


_session = make_session()


def api_request(method, path, cookies=None, data=None, timeout=60):
    """使用当前域名请求，失败时尝试其他域名"""
    global CURRENT_DOMAIN

    for i in range(len(DOMAINS)):
        url = CURRENT_DOMAIN + path
        try:
            if method == "POST":
                resp = _session.post(url, data=data, cookies=cookies,
                                   headers=HEADERS, proxies=PROXY, timeout=timeout)
            else:
                resp = _session.get(url, params=data, cookies=cookies,
                                   headers=HEADERS, proxies=PROXY, timeout=timeout)
            return resp
        except Exception as e:
            if i < len(DOMAINS) - 1:
                next_domain = DOMAINS[i + 1]
                log(f"请求失败 [{CURRENT_DOMAIN}]: {e}，切换到 {next_domain}")
                CURRENT_DOMAIN = next_domain
                continue
            log(f"请求失败 [{CURRENT_DOMAIN}]: {e}")
            return None
    return None


def login():
    """登录获取session"""
    log("登录 Z-Library...")
    resp = api_request("POST", "/eapi/user/login",
                      data={"email": EMAIL, "password": PASSWORD})
    if not resp or resp.status_code != 200:
        log(f"登录失败: {resp.status_code if resp else '无响应'}")
        return None

    data = resp.json()
    if not data.get("success"):
        log(f"登录失败: {data}")
        return None

    user = data["user"]
    log(f"登录成功: {user['name']} (每日下载限额: {user['downloads_limit']})")

    return {
        "remix_userid": str(user["id"]),
        "remix_userkey": user["remix_userkey"]
    }


def search_book(cookies, title, author):
    """搜索书籍，返回最佳匹配（带重试）"""
    query = f"{title} {author}".strip()
    log(f"搜索: {query}")

    # 搜索带重试
    for attempt in range(3):
        resp = api_request("POST", "/eapi/book/search",
                           cookies=cookies,
                           data={"message": query, "limit": 8})
        if resp and resp.status_code == 200:
            break
        log(f"搜索请求失败，重试 {attempt+1}/3: {resp.status_code if resp else '无响应'}")
        time.sleep(5)
    else:
        log(f"搜索请求失败")
        return None

    try:
        books = resp.json().get("books", [])
    except:
        log(f"解析搜索结果失败")
        return None

    if not books:
        log(f"未找到书籍: {query}")
        return None

    # 选择最佳匹配（优先英文版本）
    author_lower = author.lower().replace(" ", "")
    title_keywords = [w.lower() for w in title.split() if len(w) > 3]
    # 取作者姓的前5个字符，避免长度差异导致匹配失败
    author_surname = author_lower.split()[-1][:5] if author_lower else ""

    best = None
    best_score = 0

    for b in books:
        name = b.get("title", "")
        author_str = b.get("author", "").lower().replace(" ", "")
        lang = b.get("language", "").lower()
        name_lower = name.lower()

        score = 0
        # 英文优先
        if "english" in lang or "en" == lang:
            score += 5
        # 标题关键词匹配
        for kw in title_keywords:
            if kw in name_lower:
                score += 2
        # 作者全名匹配（更高权重）
        if author_lower[:10] in author_str[:25]:
            score += 6
        # 作者姓氏匹配（次高权重）
        if author_surname and author_surname in author_str[:15]:
            score += 4
        # 模拟电路相关加分
        if "analog" in name_lower and "circuit" in name_lower:
            score += 2
        # 避免选择中文译本
        if any(c >= '一' and c <= '鿿' for c in name):
            score -= 10
        # 避开明显不匹配的作者（如搜索Johns却匹配到Carusone）
        carusone_patterns = ["carusone", "hayes"]
        for pat in carusone_patterns:
            if pat in author_str:
                score -= 8

        if score > best_score:
            best_score = score
            best = b

    log(f"选择: {best['title']} (score={best_score}, lang={best.get('language', '?')}, author={best.get('author', '?')})")
    return best


def download_book(cookies, book, title):
    """下载单本书（每次重试获取新链接，尝试不同CDN节点）"""
    book_id = book.get("id")
    book_hash = book.get("hash")
    if not book_id or not book_hash:
        log(f"书籍信息不完整")
        return False

    # 构建文件名
    author = book.get("author", "").split(",")[0].strip()
    ext = book.get("extension", "pdf")
    filename = f"{title[:40]} - {author}.{ext}"
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filepath = OUT_DIR / filename

    log(f"下载: {filename}")

    # 每次重试获取新下载链接（碰巧不同CDN节点）
    last_error = None
    for attempt in range(5):
        # 获取下载链接
        for link_attempt in range(3):
            resp = api_request("GET", f"/eapi/book/{book_id}/{book_hash}/file",
                               cookies=cookies, timeout=60)
            if resp and resp.status_code == 200:
                break
            log(f"获取链接重试 {link_attempt+1}/3")
            time.sleep(5)
        else:
            log(f"获取下载链接失败")
            return False

        try:
            data = resp.json()
            dl_link = data.get("file", {}).get("downloadLink")
        except:
            log(f"解析下载链接失败")
            continue

        if not dl_link:
            log(f"下载链接为空")
            continue

        log(f"链接: {dl_link[:70]}...")

        # 下载文件
        try:
            resp = _session.get(dl_link, headers=HEADERS, proxies=PROXY,
                              stream=True, timeout=600,
                              allow_redirects=True)
            if resp.status_code != 200:
                log(f"下载失败: HTTP {resp.status_code}，重新获取链接...")
                last_error = f"HTTP {resp.status_code}"
                time.sleep(10)
                continue
        except Exception as e:
            log(f"下载异常: {e}，重新获取链接...")
            last_error = str(e)
            time.sleep(10)
            continue

        # 验证Content-Length是否合理（已知书的大小范围）
        total = int(resp.headers.get("content-length", 0))
        # 已知Allen/Holberg应该>200MB，Johns Martin>30MB，Horowitz>30MB
        min_expected = {
            "allen": 200 * 1024 * 1024,
            "johns": 30 * 1024 * 1024,
            "horowitz": 30 * 1024 * 1024,
        }
        author_lower = author.lower()
        min_size = 0
        if "allen" in title.lower() or "holberg" in author_lower:
            min_size = min_expected["allen"]
        elif "johns" in author_lower or "martin" in author_lower:
            min_size = min_expected["johns"]
        elif "horowitz" in author_lower or "hill" in author_lower:
            min_size = min_expected["horowitz"]

        if total > 0 and min_size > 0 and total < min_size:
            log(f"文件仅 {total/1024/1024:.1f}MB，远小于预期，重新获取链接...")
            resp.close()
            time.sleep(5)
            continue

        try:
            downloaded = 0
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded * 100 // total
                            print(f"\r  下载中: {pct}%", end="", flush=True)
            print()
            size = filepath.stat().st_size / 1024 / 1024
            log(f"完成: {filename} ({size:.1f} MB)")
            return True
        except Exception as e:
            log(f"保存文件异常: {e}")
            if filepath.exists():
                filepath.unlink()
            last_error = str(e)
            # 指数退避
            wait = 15 * (2 ** attempt)
            log(f"等待 {wait}s 后重试...")
            time.sleep(wait)

    log(f"下载失败: {last_error}")
    return False


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    open(LOG_FILE, "w", encoding="utf-8").close()

    log("=" * 60)
    log("Z-Library 书籍下载开始")
    log("=" * 60)

    # 登录
    session = login()
    if not session:
        log("登录失败，程序退出")
        return

    cookies = session

    # 下载每本书
    success = 0
    for title, author in BOOKS:
        log(f"\n{'=' * 60}")
        log(f"处理: {title} by {author}")

        book = search_book(cookies, title, author)
        if not book:
            log(f"搜索失败")
            time.sleep(3)
            continue

        if download_book(cookies, book, title):
            success += 1
        else:
            log(f"下载失败")

        time.sleep(3)  # 避免请求过快

    log(f"\n{'=' * 60}")
    log(f"完成: {success}/{len(BOOKS)} 本书下载成功")
    log(f"保存目录: {OUT_DIR}")
    log("=" * 60)


if __name__ == "__main__":
    main()
