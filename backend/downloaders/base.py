from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class ResourceType(Enum):
    BOOK = "book"
    PAPER = "paper"
    JOURNAL = "journal"


@dataclass
class SearchResult:
    id: str
    title: str
    author: str
    year: Optional[int]
    type: ResourceType
    size: Optional[str] = None
    format: Optional[str] = None
    url: Optional[str] = None
    publisher: Optional[str] = None
    language: Optional[str] = None


@dataclass
class DownloadTask:
    id: str
    title: str
    status: str  # pending, downloading, completed, failed
    progress: float  # 0.0 to 1.0
    path: Optional[str] = None
    error: Optional[str] = None


class BaseDownloader(ABC):
    """Base class for all downloaders. Implement search() and download() to add new sources."""

    def __init__(self):
        self.name = self.__class__.__name__

    @abstractmethod
    async def search(self, query: str, resource_type: ResourceType) -> List[SearchResult]:
        """Search for resources and return list of matches."""
        pass

    @abstractmethod
    async def download(self, result: SearchResult, save_dir: str) -> DownloadTask:
        """Download the resource to save_dir. Returns task with progress updates."""
        pass

    def supports(self, resource_type: ResourceType) -> bool:
        """Return True if this downloader supports the given resource type."""
        return True