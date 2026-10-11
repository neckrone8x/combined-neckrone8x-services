import os
import time
import httpx
from typing import List


class GeminiEmbedder:
    """Google Gemini gemini-embedding-2 — 768 dims, rate-limit aware."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        self.base = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-embedding-2"
        self.dim = 768
        self.batch_size = 20          # smaller batches = gentler on rate limit
        self.sleep_between = 5.0      # seconds between requests

    def _call(self, texts: List[str], task_type: str) -> List[List[float]]:
        url = f"{self.base}/models/{self.model}:batchEmbedContents"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        body = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                    "outputDimensionality": self.dim,
                }
                for t in texts
            ]
        }
        for attempt in range(5):
            try:
                with httpx.Client(timeout=60) as c:
                    r = c.post(url, headers=headers, json=body)
                    if r.status_code == 429:
                        wait = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
                        print(f"  [gemini] rate limited, waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    r.raise_for_status()
                    return [e["values"] for e in r.json()["embeddings"]]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 4:
                    wait = 2 ** attempt
                    print(f"  [gemini] 429, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError("Gemini rate limit not resolved after 5 attempts")

    def embed(self, texts: List[str]) -> List[List[float]]:
        out = []
        n = len(texts)
        bs = self.batch_size
        for i in range(0, n, bs):
            chunk = texts[i:i + bs]
            print(f"  [gemini] embedding {i}–{i+len(chunk)-1} of {n}")
            out.extend(self._call(chunk, "RETRIEVAL_DOCUMENT"))
            if i + bs < n:
                time.sleep(self.sleep_between)
        return out

    def embed_one(self, text: str) -> List[float]:
        return self._call([text], "RETRIEVAL_QUERY")[0]