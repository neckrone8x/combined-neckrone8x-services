from abc import ABC, abstractmethod
from typing import List, Dict, Any

class PaperSource(ABC):
    @abstractmethod
    def fetch(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]: ...

class VectorStore(ABC):
    @abstractmethod
    def upsert(self, ids, vectors, payloads): ...
    @abstractmethod
    def search(self, vector, top_k: int = 10): ...
