import httpx
from typing import List, Dict, Any
from app.core.interfaces import PaperSource
from app.core.config import settings

class OpenAlexSource(PaperSource):
    BASE = "https://api.openalex.org/works"

    def fetch(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        params = {
            "search": query,
            "per-page": min(max_results, 200),
            "filter": "is_oa:true",
        }
        if settings.openalex_mailto:
            params["mailto"] = settings.openalex_mailto

        r = httpx.get(self.BASE, params=params, timeout=30)
        r.raise_for_status()

        out = []
        for w in r.json().get("results", []):
            oa_id = w["id"].split("/")[-1]
            doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
            concepts = w.get("concepts", [])
            out.append({
                "id": f"openalex:{oa_id}",
                "source": "openalex",
                "source_id": oa_id,
                "doi": doi,
                "title": w.get("title") or "",
                "abstract": self._reconstruct_abstract(w.get("abstract_inverted_index")),
                "authors": [a["author"]["display_name"] for a in w.get("authorships", [])],
                "categories": [c["display_name"] for c in concepts[:10]],
                "fields": [c["display_name"] for c in concepts if c.get("score", 0) > 0.4][:5],
                "published": w.get("publication_date"),
                "url": w.get("id"),
                "extra": {"cited_by_count": w.get("cited_by_count", 0)},
            })
        return out

    @staticmethod
    def _reconstruct_abstract(inv) -> str:
        if not inv:
            return ""
        pairs = []
        for word, positions in inv.items():
            for p in positions:
                pairs.append((p, word))
        pairs.sort()
        return " ".join(w for _, w in pairs)
