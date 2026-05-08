from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Credenciais separadas — evita problema com caracteres especiais na URL
    DB_HOST: str
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Restaurante API"
    DEBUG: bool = False

    SECRET_KEY: str = "troque-esta-chave-em-producao"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()