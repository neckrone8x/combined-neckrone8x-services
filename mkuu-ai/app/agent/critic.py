from app.llm.ollama_provider import OllamaProvider

CRITIC_PROMPT = """You are a scientific fact-checker.

Given a QUESTION, an ANSWER, and a list of SOURCE PAPERS, check whether:
1. Every claim in the ANSWER is supported by the papers.
2. Every citation number in the ANSWER points to a paper that actually supports that claim.
3. Any claim is unsupported or overreaching.

Return your verdict as plain text in exactly this format:
VERDICT: OK
or
VERDICT: ISSUES
ISSUES:
- <list any problems, one per line>
"""


async def critique(question: str, answer: str, paper_block: str) -> dict:
    llm = OllamaProvider(model="llama3.2:3b")
    messages = [
        {"role": "system", "content": CRITIC_PROMPT},
        {"role": "user", "content":
            f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nSOURCE PAPERS:\n{paper_block}"},
    ]
    text = await llm.chat(messages)

    verdict_ok = "VERDICT: OK" in text.upper()
    issues = []
    if not verdict_ok and "ISSUES:" in text:
        after = text.split("ISSUES:", 1)[1]
        for line in after.splitlines():
            line = line.strip().lstrip("-").strip()
            if line:
                issues.append(line)

    return {"ok": verdict_ok, "issues": issues, "raw": text}
    