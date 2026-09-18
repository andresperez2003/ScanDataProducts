import os
import pytest
from pydantic import ValidationError


def test_missing_session_secret_raises_error(monkeypatch):
    """T001: Falta SESSION_SECRET lanza error al instanciar Settings."""
    # Limpiar la variable si existe
    monkeypatch.delenv("SESSION_SECRET", raising=False)

    # Las demás variables deben estar presentes para aislar el error a SESSION_SECRET
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("ARGON2_TIME_COST", "3")
    monkeypatch.setenv("ARGON2_MEMORY_COST", "65536")
    monkeypatch.setenv("ARGON2_PARALLELISM", "4")
    monkeypatch.setenv("SESSION_TIMEOUT_HOURS", "8")
    monkeypatch.setenv("SESSION_MAX_AGE_DAYS", "15")

    # Importar Settings aquí para que use las variables monkeypatched
    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    # Verificar que el error menciona SESSION_SECRET
    assert "SESSION_SECRET" in str(exc_info.value)


def test_complete_env_loads_correctly(monkeypatch):
    """T001: Con todas las variables definidas, Settings carga correctamente."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)  # 32 caracteres mínimo
    monkeypatch.setenv("ARGON2_TIME_COST", "3")
    monkeypatch.setenv("ARGON2_MEMORY_COST", "65536")
    monkeypatch.setenv("ARGON2_PARALLELISM", "4")
    monkeypatch.setenv("SESSION_TIMEOUT_HOURS", "8")
    monkeypatch.setenv("SESSION_MAX_AGE_DAYS", "15")
    monkeypatch.setenv("LOG_LEVEL", "info")

    from src.core.config import Settings

    settings = Settings()

    assert settings.environment == "development"
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/db"
    assert settings.session_secret == "a" * 32
    assert settings.argon2_time_cost == 3
    assert settings.argon2_memory_cost == 65536
    assert settings.argon2_parallelism == 4
    assert settings.session_timeout_hours == 8
    assert settings.session_max_age_days == 15
    assert settings.log_level == "info"


def test_session_secret_minimum_length(monkeypatch):
    """T001: SESSION_SECRET debe tener longitud mínima."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("SESSION_SECRET", "short")  # < 32 caracteres
    monkeypatch.setenv("ARGON2_TIME_COST", "3")
    monkeypatch.setenv("ARGON2_MEMORY_COST", "65536")
    monkeypatch.setenv("ARGON2_PARALLELISM", "4")
    monkeypatch.setenv("SESSION_TIMEOUT_HOURS", "8")
    monkeypatch.setenv("SESSION_MAX_AGE_DAYS", "15")

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "SESSION_SECRET" in str(exc_info.value)
