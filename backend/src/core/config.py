from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación desde variables de entorno.

    Si falta alguna variable requerida, lanza ValidationError al instanciar.
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    environment: Literal["development", "staging", "production"]
    database_url: str = Field(description="URL de conexión PostgreSQL async")
    session_secret: str = Field(
        min_length=32,
        description="Secreto para firmar cookies, mínimo 32 caracteres",
    )
    argon2_time_cost: int = Field(default=8, ge=1, description="Argon2id time cost")
    argon2_memory_cost: int = Field(
        default=131072, ge=8, description="Argon2id memory cost en KiB"
    )
    argon2_parallelism: int = Field(default=4, ge=1, description="Argon2id parallelism")
    session_timeout_hours: int = Field(
        default=8, ge=1, description="Inactividad antes de logout"
    )
    session_max_age_days: int = Field(
        default=15, ge=1, description="Máximo absoluto de sesión"
    )
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuración global (una sola instancia por proceso)."""
    return Settings()
