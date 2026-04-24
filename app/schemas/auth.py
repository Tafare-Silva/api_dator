from pydantic import BaseModel


class LoginRequest(BaseModel):
    usuario_login: str
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    nome_usuario: str
    grupo: str | None = None


class UsuarioLogado(BaseModel):
    fk_pessoas: int
    usuario_login: str
    nome: str | None
    grupo: str | None

    model_config = {"from_attributes": True}
