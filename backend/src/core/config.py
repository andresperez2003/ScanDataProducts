from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración de la aplicación desde variables de entorno.

    Si falta alguna variable requerida, lanza ValidationError al instanciar.
    """

    environment: str = Field(..., description="development, staging, production")
    database_url: str = Field(..., description="URL de conexión PostgreSQL async")
    session_secret: str = Field(
        ...,
        min_length=32,
        description="Secreto para firmar cookies, mínimo 32 caracteres"
    )
    argon2_time_cost: int = Field(default=3, ge=1, description="Argon2id time cost")
    argon2_memory_cost: int = Field(default=65536, ge=8, description="Argon2id memory cost en KiB")
    argon2_parallelism: int = Field(default=4, ge=1, description="Argon2id parallelism")
    session_timeout_hours: int = Field(default=8, ge=1, description="Inactividad antes de logout")
    session_max_age_days: int = Field(default=15, ge=1, description="Máximo absoluto de sesión")
    log_level: str = Field(default="info", description="Nivel de logging: debug, info, warning, error")
    allowed_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    class Config:
        env_file = ".env"
        case_sensitive = False

    @validator("environment")
    def validate_environment(cls, v):
        valid = {"development", "staging", "production"}
        if v not in valid:
            raise ValueError(f"ENVIRONMENT debe ser uno de {valid}")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        valid = {"debug", "info", "warning", "error", "critical"}
        if v not in valid:
            raise ValueError(f"LOG_LEVEL debe ser uno de {valid}")
        return v


def get_settings() -> Settings:
    """Obtiene la configuración global (singleton)."""
    return Settings()
