from app.ingestion.pipeline import run_ingestion
from app.retrieval.hybrid import hybrid_search

if __name__ == "__main__":
    queries = [
        "protein language models",
        "CRISPR off-target prediction",
        "single-cell spatial transcriptomics",
        "graph neural networks drug discovery",
    ]
    n = run_ingestion(queries, sources=["arxiv", "openalex"], per_query=40)
    print(f"\nIndexed {n} papers total.\n")

    print("Sample hybrid search: 'protein language models for structure prediction'")
    for i, r in enumerate(hybrid_search("protein language models for structure prediction", top_k=5), 1):
        print(f"{i}. [{r['rerank_score']:.3f}] {r['title']}  ({r['source']})")
