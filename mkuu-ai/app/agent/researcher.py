import asyncio
from typing import List, Dict
from app.llm.ollama_provider import OllamaProvider
from app.retrieval.hybrid import hybrid_search
from app.agent.memory import remember, rate_last, recent_episodes
from app.agent.critic import critique


SYSTEM_RESEARCH = """You are Neckrone8x, a scientific research assistant.

Answer the user's question using ONLY the numbered papers provided below.
Every factual claim must cite the paper number in square brackets, like [1] or [3].
If the papers do not contain enough evidence, say so clearly.
Do not invent facts or citations. Be concise: 3-5 short bullet points maximum.

Papers:
{papers}
"""

SYSTEM_CHAT = """You are Neckrone8x, a scientific research assistant.
The user asked something that isn't a research question. Answer
conversationally using the conversation history. Be very brief. No citations.
"""

MIN_USEFUL_SCORE = 0.5


def format_papers(results: List[Dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        abstract = r.get("abstract", "").strip()
        if len(abstract) > 500:
            abstract = abstract[:500] + "..."
        source = r.get("source", "?")
        year = (r.get("published") or "")[:4]
        lines.append(f"[{i}] {title} ({source}, {year})\n{abstract}")
    return "\n\n".join(lines)


async def ask(question: str, top_k: int = 4, use_critic: bool = False) -> Dict:
    print(f"\nSearching papers for: {question}")
    results = hybrid_search(question, top_k=top_k)

    best = max((p.get("rerank_score", 0) for p in results), default=0)
    useful = best >= MIN_USEFUL_SCORE

    if useful:
        print(f"Found {len(results)} relevant papers (best {best:.3f}).\n")
        paper_block = format_papers(results)
        system = SYSTEM_RESEARCH.format(papers=paper_block)
    else:
        print(f"No strong match (best {best:.3f}). Conversation mode.\n")
        paper_block = ""
        system = SYSTEM_CHAT
        results = []

    history = recent_episodes(n=2)
    messages = [{"role": "system", "content": system}]
    for ep in history:
        messages.append({"role": "user", "content": ep["question"]})
        prev = ep["answer"][:300] + ("..." if len(ep["answer"]) > 300 else "")
        messages.append({"role": "assistant", "content": prev})
    messages.append({"role": "user", "content": question})

    model_name = "llama3.2:3b" if useful else "llama3.2:1b"
    llm = OllamaProvider(model=model_name)

    print(f"Asking {model_name}...\n")
    print("-" * 60)
    parts = []
    async for chunk in llm.stream(messages, num_predict=200):
        print(chunk, end="", flush=True)
        parts.append(chunk)
    print("\n" + "-" * 60)

    answer = "".join(parts)

    if use_critic and useful:
        print("\nCritic reviewing...\n")
        verdict = await critique(question, answer, paper_block)
        print("Critic: OK\n" if verdict["ok"] else "Critic issues:\n")
        for issue in verdict["issues"]:
            print(f"  - {issue}")
        print()

    remember(question, answer, results, rating=0)
    return {"answer": answer, "papers": results}


def main():
    print("Neckrone8x Research Agent v0.5 (fast mode)")
    print("Commands: quit, +1/-1, 'critic on', 'critic off'\n")
    use_critic = False
    while True:
        try:
            q = input("Question> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in ("quit", "exit", "q"):
            break
        if q in ("+1", "-1"):
            ok = rate_last(1 if q == "+1" else -1)
            print("Rated.\n" if ok else "No prior answer.\n")
            continue
        if q.lower() == "critic on":
            use_critic = True
            print("Critic ON.\n")
            continue
        if q.lower() == "critic off":
            use_critic = False
            print("Critic OFF.\n")
            continue

        result = asyncio.run(ask(q, use_critic=use_critic))

        if result["papers"]:
            print("Sources:")
            for i, p in enumerate(result["papers"], 1):
                print(f"  [{i}] {p.get('title','')[:70]}  "
                      f"({p.get('source','?')}, {p.get('rerank_score',0):.3f})")
        print()


if __name__ == "__main__":
    main()