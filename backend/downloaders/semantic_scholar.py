"""
Semantic Scholar paper downloader
"""
import os
import time
from pathlib import Path
from typing import List
import requests

from .base import BaseDownloader, SearchResult, DownloadTask, ResourceType


class SemanticScholarDownloader(BaseDownloader):
    """Semantic Scholar paper downloader - free API"""

    API_URL = "https://api.semanticscholar.org/graph/v1"
    # Free tier: 100 requests/5min, 10/sec
    RATE_LIMIT_DELAY = 0.5

    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
        self._last_request_time = 0

    def supports(self, resource_type: ResourceType) -> bool:
        return resource_type == ResourceType.PAPER

    def _respect_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get_headers(self):
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def search(self, query: str, resource_type: ResourceType) -> List[SearchResult]:
        results = []
        try:
            self._respect_rate_limit()

            params = {
                "query": query,
                "limit": 20,
                "fields": "title,authors,year,venue,paperId,externalIds,openAccessPdf,abstract"
            }

            resp = requests.get(
                f"{self.API_URL}/paper/search",
                params=params,
                headers=self._get_headers(),
                timeout=30
            )

            if resp.status_code != 200:
                return []

            data = resp.json()
            for paper in data.get("data", []):
                # Get PDF URL
                pdf_url = None
                oa_pdf = paper.get("openAccessPdf", {})
                if oa_pdf and oa_pdf.get("url"):
                    pdf_url = oa_pdf["url"]

                # Fallback to arXiv if available
                ext_ids = paper.get("externalIds", {})
                if not pdf_url and ext_ids.get("ArXiv"):
                    pdf_url = f"https://arxiv.org/pdf/{ext_ids['ArXiv']}.pdf"

                authors = ", ".join([a.get("name", "") for a in paper.get("authors", [])[:3]])
                if len(paper.get("authors", [])) > 3:
                    authors += " et al."

                results.append(SearchResult(
                    id=paper.get("paperId", ""),
                    title=paper.get("title", "Unknown"),
                    author=authors,
                    year=paper.get("year"),
                    type=ResourceType.PAPER,
                    format="pdf",
                    url=pdf_url,
                    publisher=paper.get("venue")  # venue = journal/conference
                ))

        except Exception as e:
            pass

        return results

    async def download(self, result: SearchResult, save_dir: str) -> DownloadTask:
        task = DownloadTask(
            id=f"semantic_{result.id}",
            title=result.title,
            status="downloading",
            progress=0.0
        )

        if not result.url:
            task.status = "failed"
            task.error = "No PDF URL available"
            return task

        try:
            os.makedirs(save_dir, exist_ok=True)
            safe_title = "".join(c for c in result.title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
            filepath = Path(save_dir) / f"{safe_title}.pdf"

            resp = requests.get(result.url, stream=True, timeout=300)
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