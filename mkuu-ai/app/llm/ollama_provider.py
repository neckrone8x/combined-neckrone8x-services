import json
import httpx
from typing import List, Dict, AsyncIterator


class OllamaProvider:
    """Talks to a local Ollama server. Keeps model warm 30 min."""

    def __init__(self, model: str = "llama3.2:3b",
                 host: str = None,
                 timeout: float = 600.0):
        import os
        self.model = model
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout

    async def chat(self, messages: List[Dict[str, str]], **options) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {"num_ctx": 4096, **options},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(f"{self.host}/api/chat", json=payload)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")

    async def stream(self, messages: List[Dict[str, str]], **options) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": "30m",
            "options": {"num_ctx": 4096, **options},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    piece = chunk.get("message", {}).get("content", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        break

    def ping(self) -> bool:
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False