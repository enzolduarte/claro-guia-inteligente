from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolvido a partir do módulo: o .env é encontrado mesmo quando o processo
# sobe de outro diretório de trabalho.
CORE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=CORE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    core_url: str = "http://localhost:8000"
    gemini_api_key: str = ""  # vazia → modo determinístico
    telegram_bot_token: str = ""  # vazio → adaptador não sobe (não afeta o core)
    db_path: str = "./data/telemetria.db"
    flows_path: str = "./data/flows.json"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    llm_timeout_ms: int = 3000
    core_timeout_ms: int = 2500


settings = Settings()
