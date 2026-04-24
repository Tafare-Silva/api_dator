from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Restaurante API"
    DEBUG: bool = False

    # JWT — gere uma SECRET_KEY forte em produção:
    # python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = "troque-esta-chave-em-producao"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas (turno de trabalho)

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
