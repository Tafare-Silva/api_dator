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

    # Area do Cliente. Login: CPF -> codigo enviado ao celular cadastrado.
    # CLIENTE_ENVIO_PROVEDOR: '' = desligado (503); 'log' = so grava o codigo no
    # log do servidor (TESTE, nao envia nada); provedores reais entram em
    # app/services/notificacao_service.py.
    CLIENTE_ENVIO_PROVEDOR: str = ''  # '', 'log' ou 'evolution'
    # Evolution API (WhatsApp nao oficial): URL base, nome da instancia e apikey.
    EVOLUTION_URL: str = ''
    EVOLUTION_INSTANCE: str = ''
    EVOLUTION_API_KEY: str = ''
    CLIENTE_CODIGO_VALIDADE_MIN: int = 10
    CLIENTE_CODIGO_REENVIO_SEG: int = 60
    # Vendedor que recebe os condicionais gerados pelo app. Achado pelo NOME EXATO
    # (sem diferenciar maiusculas/espacos) entre os cadastros ativos; se houver
    # zero ou mais de um, o condicional e recusado. Para fixar por loja use
    # CLIENTE_VENDEDOR_IDS="banco1:123,banco2:456" (codigo da pessoa em cada banco).
    CLIENTE_VENDEDOR_PADRAO: str = 'LOJA FEMININO'
    CLIENTE_VENDEDOR_IDS: str = ''
    CLIENTE_MAX_ITENS_CONDICIONAL: int = 10
    CLIENTE_MAX_CONDICIONAIS_ABERTOS: int = 2
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