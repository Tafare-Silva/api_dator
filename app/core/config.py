from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Credenciais separadas — evita problema com caracteres especiais na URL
    DB_HOST: str
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: str
    # Legado: antes da multi-loja, definia o único banco usado. Hoje os 3
    # bancos vêm de EMPRESAS (mais abaixo); pode remover do .env se quiser.
    DB_NAME: str | None = None

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Restaurante API"
    DEBUG: bool = False

    SECRET_KEY: str = "troque-esta-chave-em-producao"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Area do Cliente (cliente final). CLIENTE_LOGIN_MODO: 'cpf' (so CPF), 'celular' (4 ultimos
    # digitos do celular cadastrado) ou 'nascimento' (se a coluna existir no
    # banco da loja). Vazio = login do cliente DESLIGADO (503).
    CLIENTE_LOGIN_MODO: str = ''
    CLIENTE_TOKEN_MINUTOS: int = 120
    CLIENTE_MAX_TENTATIVAS: int = 5
    CLIENTE_JANELA_BLOQUEIO_MIN: int = 15

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Lojas do cliente (matriz + filiais) — mesmo host/usuário/senha, um banco
# Postgres por loja no ERP Delphi. Chave = nome do banco (também usado como
# claim "empresa" no JWT); valor = nome exibido no app.
EMPRESAS: dict[str, str] = {
    "puro_estilo_bandeirantes": "Feminino/Kids",
    "puro_estilo_kids": "Linda de Bonito",
    "puro_estilo_santa_mariana": "Masculino",
}