from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://arqqa:arqqa_dev_password@localhost:5432/arqqa"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "models/gemini-2.5-flash"
    app_secret: str = "development-only-change-me"
    cors_origins: str = "http://localhost:3000"
    dashboard_password: str = ""
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    max_upload_mb: int = 20
    chunk_size: int = 900
    chunk_overlap: int = 150
    retrieval_top_k: int = 6
    retrieval_fetch_k: int = 40
    min_similarity: float = 0.3
    mmr_lambda: float = 0.65
    enable_rerank: bool = True
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    enable_multi_query: bool = False
    multi_query_count: int = 2
    rerank_candidates: int = 12
    neighbor_window: int = 1
    max_context_chars: int = 9000

settings = Settings()