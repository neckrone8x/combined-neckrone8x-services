import arxiv
from typing import List, Dict, Any
from app.core.interfaces import PaperSource

class ArxivSource(PaperSource):
    def fetch(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        out = []
        for r in client.results(search):
            aid = r.entry_id.split("/")[-1]
            out.append({
                "id": f"arxiv:{aid}",
                "source": "arxiv",
                "source_id": aid,
                "doi": r.doi,
                "title": r.title.strip(),
                "abstract": r.summary.strip().replace("\n", " "),
                "authors": [a.name for a in r.authors],
                "categories": list(r.categories),
                "fields": list(r.categories)[:3],
                "published": r.published.isoformat(),
                "url": r.entry_id,
                "extra": {"primary_category": r.primary_category},
            })
        return out
