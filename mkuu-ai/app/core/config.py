from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NECKRONE_", env_file=".env", extra="ignore"
    )
    app_name: str = "Neckrone8x Research AI"

    pg_dsn: str = "postgresql+psycopg2://neckrone:neckrone@localhost:5432/neckrone"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "papers"

    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 768

    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    dense_top_k: int = 15
    lexical_top_k: int = 15
    rerank_top_k: int = 4
    rrf_k: int = 60

    offline: bool = False
    openalex_mailto: str = ""

settings = Settings()
