"""Central application configuration.

Loaded once at import time and shared everywhere. Keeping the SQLite
busy-timeout and database URL here (rather than hard-coded in database.py)
means concurrency behavior can be tuned via environment without code changes.

The ranking-weight fields are declared now for visibility but are not consumed
until the ranking service is implemented in a later step.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEDGERRANK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database / concurrency ---
    database_url: str = "sqlite:///./data/ledgerrank.db"
    sqlite_busy_timeout_ms: int = 5000
    sql_echo: bool = False

    # --- Ranking weights (consumed later; kept here as the single source) ---
    weight_amount: float = 0.5
    weight_count: float = 0.3
    weight_recency: float = 0.2
    recency_tau_days: float = 7.0


# A single shared settings instance.
settings = Settings()
