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

    gemini_api_key: str = ""  # vazia → modo determinístico
    gemini_model: str = "gemini-flash-lite-latest"
    db_path: str = "./data/telemetria.db"
    flows_path: str = "./data/flows.json"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    llm_timeout_ms: int = 8000


# Três variáveis do projeto NÃO moram aqui, e a ausência é intencional:
#
#   CORE_URL           onde achar o núcleo. Quem precisa saber é quem chama de
#                      fora: o BFF do site e o adaptador de Telegram. O núcleo
#                      não liga para si mesmo.
#   CORE_TIMEOUT_MS    quanto esperar pelo núcleo. Mesma coisa: é limite de
#                      paciência de quem chama, não de quem responde.
#   TELEGRAM_BOT_TOKEN lido só pelo adapters/telegram/bot.py, que é um processo
#                      separado e não importa nada deste pacote.
#
# Elas estavam declaradas aqui e nunca eram lidas, o que sugeria que o núcleo as
# consultava. O `extra="ignore"` acima garante que estar no .env não quebra nada.


settings = Settings()
