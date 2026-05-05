"""
Academic Resource Downloader - FastAPI Backend
"""
import os
import uuid
from pathlib import Path
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .downloaders import BaseDownloader, SearchResult, DownloadTask, ResourceType
from .downloaders.zlibrary import ZLibraryDownloader
from .downloaders.arxiv import ArxivDownloader
from .downloaders.semantic_scholar import SemanticScholarDownloader
from .downloaders.crossref import CrossrefDownloader

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "backend" / "static"

app = FastAPI(title="Academic Downloader", description="Download books, papers, and more")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Global settings (in-memory, not persisted)
class Settings:
    zlibrary_email: Optional[str] = None
    zlibrary_password: Optional[str] = None
    proxy: Optional[str] = None
    @property
    def download_dir(self) -> str:
        # Auto-detect Downloads folder regardless of username
        home = Path.home()
        downloads = home / "Downloads"
        if downloads.exists():
            return str(downloads)
        # Fallback to home directory
        return str(home)

settings = Settings()

# Task storage for download progress tracking
download_tasks: Dict[str, dict] = {}

# Initialize downloaders (without credentials - will be passed at runtime)
downloaders: Dict[str, BaseDownloader] = {}

def get_downloader_configs():
    """Return downloader instances with current settings"""
    return {
        "zlibrary": ZLibraryDownloader(
            email=settings.zlibrary_email,
            password=settings.zlibrary_password,
            proxy=settings.proxy
        ),
        "arxiv": ArxivDownloader(proxy=settings.proxy),
        "semantic": SemanticScholarDownloader(),
        "crossref": CrossrefDownloader(),
    }


class SearchRequest(BaseModel):
    query: str
    resource_type: str  # "book", "paper", "journal"


class DownloadRequest(BaseModel):
    result: dict


class SettingsRequest(BaseModel):
    zlibrary_email: Optional[str] = None
    zlibrary_password: Optional[str] = None
    proxy: Optional[str] = None
    download_dir: Optional[str] = None


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/settings")
async def get_settings():
    """Get current settings (password masked)"""
    return {
        "zlibrary_email": settings.zlibrary_email or "",
        "zlibrary_password": "***" if settings.zlibrary_password else "",
        "proxy": settings.proxy or "",
        "download_dir": settings.download_dir
    }


@app.post("/api/settings")
async def update_settings(request: SettingsRequest):
    """Update settings"""
    if request.zlibrary_email is not None:
        settings.zlibrary_email = request.zlibrary_email or None
    if request.zlibrary_password is not None:
        settings.zlibrary_password = request.zlibrary_password or None
    if request.proxy is not None:
        settings.proxy = request.proxy or None
    if request.download_dir is not None:
        settings.download_dir = request.download_dir or str(Path.home() / "Downloads")
    return {"status": "ok"}


@app.get("/api/downloaders")
async def list_downloaders():
    """List available downloaders and their supported types"""
    configs = get_downloader_configs()
    return {
        name: [rt.value for rt in ResourceType if dl.supports(rt)]
        for name, dl in configs.items()
    }


@app.post("/api/search")
async def search(request: SearchRequest):
    """Search across all applicable downloaders"""
    try:
        resource_type = ResourceType(request.resource_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resource type")

    results = []
    configs = get_downloader_configs()
    for name, dl in configs.items():
        if dl.supports(resource_type):
            results.extend(await dl.search(request.query, resource_type))

    return {"results": [vars(r) for r in results]}


@app.post("/api/download")
async def download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Start a download task - returns immediately with task_id"""
    result_dict = request.result
    result_type = ResourceType(result_dict.get("type", "book"))
    result = SearchResult(
        id=result_dict["id"],
        title=result_dict["title"],
        author=result_dict["author"],
        year=result_dict.get("year"),
        type=result_type,
        size=result_dict.get("size"),
        format=result_dict.get("format"),
        url=result_dict.get("url"),
        publisher=result_dict.get("publisher"),
        language=result_dict.get("language"),
    )

    # Create task entry
    task_id = str(uuid.uuid4())
    download_tasks[task_id] = {
        "id": task_id,
        "title": result.title,
        "status": "starting",
        "progress": 0.0,
        "path": None,
        "error": None
    }

    # Start download in background
    background_tasks.add_task(run_download, task_id, result, result_type)

    return {"task_id": task_id, "task": download_tasks[task_id]}


async def run_download(task_id: str, result: SearchResult, result_type: ResourceType):
    """Background task that performs the download and updates progress"""
    try:
        configs = get_downloader_configs()
        for name, dl in configs.items():
            if dl.supports(result_type):
                download_tasks[task_id]["status"] = "downloading"
                final_task = await dl.download(result, settings.download_dir)
                download_tasks[task_id].update({
                    "status": final_task.status,
                    "progress": final_task.progress,
                    "path": final_task.path,
                    "error": final_task.error
                })
                return

        download_tasks[task_id]["status"] = "failed"
        download_tasks[task_id]["error"] = "No downloader found"
    except Exception as e:
        download_tasks[task_id]["status"] = "failed"
        download_tasks[task_id]["error"] = str(e)


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get download task status and progress"""
    if task_id not in download_tasks:
        return {"error": "Task not found"}
    return {"task": download_tasks[task_id]}


@app.get("/api/tasks")
async def list_tasks():
    """List all tasks"""
    return {"tasks": list(download_tasks.values())}