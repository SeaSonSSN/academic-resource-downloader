"""
Crossref paper downloader
Uses Crossref for search + Unpaywall for PDF download
"""
import os
import time
from pathlib import Path
from typing import List
import requests

from .base import BaseDownloader, SearchResult, DownloadTask, ResourceType


class CrossrefDownloader(BaseDownloader):
    """Crossref + Unpaywall paper downloader - free APIs"""

    CROSSREF_URL = "https://api.crossref.org/works"
    UNPAYWALL_URL = "https://api.unpaywall.org/v2"

    # Simple rate limiting
    RATE_LIMIT_DELAY = 1.0

    def __init__(self, email: str = None):
        super().__init__()
        self.email = email or os.getenv("CROSSREF_EMAIL", "anonymous@example.com")
        self._last_request_time = 0

    def supports(self, resource_type: ResourceType) -> bool:
        return resource_type == ResourceType.PAPER

    def _respect_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    async def search(self, query: str, resource_type: ResourceType) -> List[SearchResult]:
        results = []
        try:
            self._respect_rate_limit()

            params = {
                'query': query,
                'rows': 20,
                'select': 'title,author,published,DOI,container-title,type,volume'
            }

            resp = requests.get(
                self.CROSSREF_URL,
                params=params,
                headers={"User-Agent": f"mailto:{self.email}"},
                timeout=30
            )

            if resp.status_code != 200:
                return []

            import json
            data = json.loads(resp.text)
            items = data.get('message', {}).get('items', [])

            for item in items:
                title = item.get('title', ['Unknown'])[0]
                authors = item.get('author', [])
                author_str = ", ".join([
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in authors[:3]
                ])
                if len(authors) > 3:
                    author_str += " et al."

                year = None
                published = item.get('published', {})
                if published:
                    date_parts = published.get('date-parts', [[]])
                    if date_parts and date_parts[0]:
                        year = date_parts[0][0]

                results.append(SearchResult(
                    id=item.get('DOI', ''),
                    title=title,
                    author=author_str or 'Unknown',
                    year=year,
                    type=ResourceType.PAPER,
                    format='pdf',
                    url=None,  # Will be resolved during download
                    publisher=item.get('container-title', [''])[0] if item.get('container-title') else None
                ))

        except Exception as e:
            pass

        return results

    async def download(self, result: SearchResult, save_dir: str) -> DownloadTask:
        task = DownloadTask(
            id=f"crossref_{result.id}",
            title=result.title,
            status="downloading",
            progress=0.0
        )

        doi = result.id
        if not doi:
            task.status = "failed"
            task.error = "No DOI available"
            return task

        try:
            self._respect_rate_limit()

            # Get PDF URL from Unpaywall
            resp = requests.get(
                f"{self.UNPAYWALL_URL}/{doi}",
                params={'email': self.email},
                timeout=30
            )

            pdf_url = None
            if resp.status_code == 200:
                import json
                data = json.loads(resp.text)
                best_oa = data.get('best_oa_location', {})
                if best_oa:
                    pdf_url = best_oa.get('url_for_pdf')

            if not pdf_url:
                # Try to find any PDF link
                resp2 = requests.get(
                    self.CROSSREF_URL,
                    params={'query.doi': doi},
                    headers={"User-Agent": f"mailto:{self.email}"},
                    timeout=30
                )
                if resp2.status_code == 200:
                    import json
                    data = resp2.json()
                    links = data.get('message', {}).get('link', [])
                    for link in links:
                        if link.get('content-type', '').startswith('application/pdf'):
                            pdf_url = link.get('URL')
                            break

            if not pdf_url:
                task.status = "failed"
                task.error = "No PDF available for this paper"
                return task

            # Download PDF
            os.makedirs(save_dir, exist_ok=True)
            safe_title = "".join(c for c in result.title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
            filepath = Path(save_dir) / f"{safe_title}.pdf"

            resp = requests.get(pdf_url, stream=True, timeout=300)
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