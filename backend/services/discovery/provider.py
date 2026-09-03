from abc import ABC, abstractmethod
from typing import List
from .models import NormalizedCandidate

class ProviderInterface(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Name of the platform, e.g., 'youtube'"""
        pass

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[NormalizedCandidate]:
        """Execute a search query and return normalized candidates."""
        pass
