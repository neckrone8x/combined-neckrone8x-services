import json
import time
import uuid
from pathlib import Path
from typing import List, Dict

MEMORY_FILE = Path("data/memory.jsonl")


def _ensure_dir():
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)


def remember(question: str, answer: str, papers: List[Dict], rating: int = 0):
    """Store a Q&A episode. rating: 0=unrated, 1=good, -1=bad."""
    _ensure_dir()
    episode = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "question": question,
        "answer": answer,
        "papers": [
            {"id": p.get("id"), "title": p.get("title"),
             "source": p.get("source"), "score": p.get("rerank_score", 0)}
            for p in papers
        ],
        "rating": rating,
    }
    with MEMORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(episode) + "\n")


def load_all() -> List[Dict]:
    _ensure_dir()
    if not MEMORY_FILE.exists():
        return []
    episodes = []
    with MEMORY_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return episodes


def recent_context(n: int = 3) -> str:
    """Return a short summary of the last n questions the user asked."""
    episodes = load_all()
    if not episodes:
        return ""
    # last n, prefer ones with positive rating
    tail = episodes[-n:]
    lines = []
    for e in tail:
        q = e["question"]
        a = e["answer"].replace("\n", " ")[:200]
        lines.append(f"- Q: {q}\n  A (summary): {a}...")
    return "\n".join(lines)


def rate_last(rating: int):
    """Update the rating of the most recent episode."""
    episodes = load_all()
    if not episodes:
        return False
    episodes[-1]["rating"] = rating
    with MEMORY_FILE.open("w", encoding="utf-8") as f:
        for e in episodes:
            f.write(json.dumps(e) + "\n")
    return True

def recent_episodes(n: int = 3):
    """Return the last n episodes as dicts, for chat-style context."""
    return load_all()[-n:]