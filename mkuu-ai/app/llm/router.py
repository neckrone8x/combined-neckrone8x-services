import os
import json
import httpx
from typing import List, Dict, AsyncIterator, Optional


class CloudProvider:
    """Groq cloud LLM (free tier). OpenAI-compatible API."""

    def __init__(self, model: str = "openai/gpt-oss-120b",
                 api_key: Optional[str] = None):
        self.model = model
        self.api_key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def _base_payload(self, messages, stream, options):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        # Reasoning control — GPT-OSS models burn tokens on hidden thinking
        # unless we tell them to keep it minimal.
        if "gpt-oss" in self.model:
            payload["reasoning_effort"] = "low"
            payload["reasoning_format"] = "hidden"
        # Token budget: generous enough for reasoning + answer
        max_tokens = options.get("num_predict", 400)
        payload["max_tokens"] = max_tokens
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        return payload

    async def chat(self, messages: List[Dict], **options) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        payload = self._base_payload(messages, False, options)
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(self.url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def stream(self, messages: List[Dict], **options) -> AsyncIterator[str]:
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        payload = self._base_payload(messages, True, options)
        async with httpx.AsyncClient(timeout=300) as c:
            async with c.stream("POST", self.url, headers=headers, json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        piece = delta.get("content") or ""
                        if piece:
                            yield piece
                    except Exception:
                        continue

    def ping(self) -> bool:
        return bool(self.api_key)


def get_llm(model_hint: str = "default"):
    """Cloud if GROQ_API_KEY exists, else local Ollama."""
    if os.getenv("GROQ_API_KEY"):
        return CloudProvider(model="openai/gpt-oss-120b")
    from app.llm.ollama_provider import OllamaProvider
    return OllamaProvider(
        model="llama3.2:3b" if model_hint != "chat" else "llama3.2:1b"
    )