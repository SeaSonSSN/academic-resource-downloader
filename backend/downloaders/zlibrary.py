"""
Z-Library downloader
"""
import os
import re
import time
from pathlib import Path
from typing import List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import BaseDownloader, SearchResult, DownloadTask, ResourceType


class ZLibraryDownloader(BaseDownloader):
    """Z-Library downloader - supports books"""

    DOMAINS = [
        "https://z-library.sk",
        "https://1lib.sk",
        "https://zh.zlib.li",
    ]

    def __init__(self, email: str = None, password: str = None, proxy: str = None):
        super().__init__()
        self.email = email or os.getenv("ZLIBRARY_EMAIL", "")
        self.password = password or os.getenv("ZLIBRARY_PASSWORD", "")
        self.proxy = proxy or os.getenv("PROXY", None)

        self._session = None
        self._cookies = None
        self._current_domain = self.DOMAINS[0]
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
        }

    def supports(self, resource_type: ResourceType) -> bool:
        return resource_type == ResourceType.BOOK

    def _make_session(self):
        s = requests.Session()
        retries = Retry(total=5, backoff_factor=3, status_forcelist=[502, 503, 504, 522, 520])
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.mount("http://", HTTPAdapter(max_retries=retries))
        return s

    def _api_request(self, method, path, cookies=None, data=None, timeout=60):
        for i in range(len(self.DOMAINS)):
            url = self._current_domain + path
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            try:
                if method == "POST":
                    resp = self._session.post(url, data=data, cookies=cookies,
                                              headers=self._headers, proxies=proxies, timeout=timeout)
                else:
                    resp = self._session.get(url, params=data, cookies=cookies,
                                              headers=self._headers, proxies=proxies, timeout=timeout)
                return resp
            except Exception as e:
                if i < len(self.DOMAINS) - 1:
                    self._current_domain = self.DOMAINS[i + 1]
                    continue
        return None

    def _ensure_logged_in(self) -> bool:
        if self._cookies:
            return True
        if not self.email or not self.password:
            return False

        self._session = self._make_session()

        resp = self._api_request("POST", "/eapi/user/login",
                                  data={"email": self.email, "password": self.password})
        if not resp or resp.status_code != 200:
            return False

        data = resp.json()
        if not data.get("success"):
            return False

        user = data["user"]
        self._cookies = {
            "remix_userid": str(user["id"]),
            "remix_userkey": user["remix_userkey"]
        }
        return True

    async def search(self, query: str, resource_type: ResourceType) -> List[SearchResult]:
        if not self._ensure_logged_in():
            return []

        resp = self._api_request("POST", "/eapi/book/search",
                                  cookies=self._cookies,
                                  data={"message": query, "limit": 8})
        if not resp or resp.status_code != 200:
            return []

        try:
            books = resp.json().get("books", [])
        except:
            return []

        results = []
        for b in books:
            results.append(SearchResult(
                id=str(b.get("id", "")),
                title=b.get("title", "Unknown"),
                author=b.get("author", "Unknown"),
                year=b.get("year"),
                type=ResourceType.BOOK,
                size=b.get("filesizeString"),
                format=b.get("extension", "pdf"),
                url=f"/book/{b.get('id')}/{b.get('hash')}",
                publisher=b.get("publisher"),
                language=b.get("language")
            ))

        return results

    async def download(self, result: SearchResult, save_dir: str) -> DownloadTask:
        task = DownloadTask(
            id=f"zlibrary_{result.id}",
            title=result.title,
            status="pending",
            progress=0.0
        )

        try:
            if not self._ensure_logged_in():
                task.status = "failed"
                task.error = "Not logged in"
                return task

            # Parse book id and hash from url
            parts = result.url.replace("/book/", "").split("/")
            if len(parts) < 2:
                task.status = "failed"
                task.error = "Invalid book URL"
                return task

            book_id, book_hash = parts[0], parts[1]

            # Get download link
            resp = self._api_request("GET", f"/eapi/book/{book_id}/{book_hash}/file",
                                     cookies=self._cookies, timeout=60)
            if not resp or resp.status_code != 200:
                task.status = "failed"
                task.error = "Failed to get download link"
                return task

            data = resp.json()
            dl_link = data.get("file", {}).get("downloadLink")
            if not dl_link:
                task.status = "failed"
                task.error = "No download link available"
                return task

            task.status = "downloading"

            # Download file
            os.makedirs(save_dir, exist_ok=True)
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', result.title)
            filepath = Path(save_dir) / f"{safe_title}.{result.format or 'pdf'}"

            resp = self._session.get(dl_link, headers=self._headers,
                                     proxies={"http": self.proxy, "https": self.proxy} if self.proxy else None,
                                     stream=True, timeout=600)

            if resp.status_code != 200:
                task.status = "failed"
                task.error = f"HTTP {resp.status_code}"
                return task

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            task.progress = downloaded / total

            task.status = "completed"
            task.progress = 1.0
            task.path = str(filepath)

        except Exception as e:
            task.status = "failed"
            task.error = str(e)

        return task