from pydantic import BaseModel


class LoginRequest(BaseModel):
    usuario_login: str
    senha: str
    empresa: str  # nome do banco da loja, ex: "puro_estilo_bandeirantes"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    nome_usuario: str
    grupo: str | None = None
    empresa: str
    empresa_nome: str


class UsuarioLogado(BaseModel):
    fk_pessoas: int
    usuario_login: str
    nome: str | None
    grupo: str | None

    model_config = {"from_attributes": True}
