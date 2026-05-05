"""
arXiv paper downloader
"""
import os
import time
from pathlib import Path
from typing import List
import requests

from .base import BaseDownloader, SearchResult, DownloadTask, ResourceType


class ArxivDownloader(BaseDownloader):
    """arXiv paper downloader - no login required"""

    BASE_URL = "https://export.arxiv.org/api/query"
    RATE_LIMIT_DELAY = 3.0  # arXiv requires 1 request per 3 seconds

    def __init__(self, proxy: str = None):
        super().__init__()
        self.proxy = proxy or os.getenv("PROXY", None)
        self._last_request_time = 0

    def supports(self, resource_type: ResourceType) -> bool:
        return resource_type == ResourceType.PAPER

    def _get_proxies(self):
        if self.proxy:
            return {"http": self.proxy, "https": self.proxy}
        return None

    def _respect_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    async def search(self, query: str, resource_type: ResourceType) -> List[SearchResult]:
        results = []
        try:
            self._respect_rate_limit()

            resp = requests.get(
                self.BASE_URL,
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": 20,
                    "sort_by": "relevance"
                },
                proxies=self._get_proxies(),
                timeout=60
            )

            if resp.status_code == 429:
                return []  # Rate limited, return empty

            if resp.status_code != 200:
                return []

            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)

            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                title = entry.find("{http://www.w3.org/2005/Atom}title")
                author_list = entry.findall("{http://www.w3.org/2005/Atom}author")
                authors = ", ".join([a.find("{http://www.w3.org/2005/Atom}name").text for a in author_list])
                published = entry.find("{http://www.w3.org/2005/Atom}published")

                # Get PDF link
                pdf_link = None
                for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
                    if link.get("title") == "pdf":
                        pdf_link = link.get("href")

                if pdf_link:
                    results.append(SearchResult(
                        id=entry.find("{http://www.w3.org/2005/Atom}id").text.split("/")[-1],
                        title=title.text.replace("\n", " ").strip() if title is not None else "Unknown",
                        author=authors,
                        year=int(published.text[:4]) if published is not None else None,
                        type=ResourceType.PAPER,
                        format="pdf",
                        url=pdf_link
                    ))

        except requests.RequestException as e:
            pass
        except Exception as e:
            pass

        return results

    async def download(self, result: SearchResult, save_dir: str) -> DownloadTask:
        task = DownloadTask(
            id=f"arxiv_{result.id}",
            title=result.title,
            status="downloading",
            progress=0.0
        )

        try:
            os.makedirs(save_dir, exist_ok=True)
            filepath = Path(save_dir) / f"{result.id}.pdf"

            resp = requests.get(result.url, stream=True, timeout=300, proxies=self._get_proxies())
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

        except requests.RequestException as e:
            task.status = "failed"
            task.error = str(e)
        except IOError as e:
            task.status = "failed"
            task.error = f"File error: {str(e)}"
        except Exception as e:
            task.status = "failed"
            task.error = str(e)

        return task