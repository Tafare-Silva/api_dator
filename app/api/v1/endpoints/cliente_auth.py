from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import EMPRESAS, settings
from app.core.deps_cliente import TIPO_CLIENTE, ClienteLogado, get_cliente_logado
from app.core.security import criar_token
from app.db.session import SESSION_FACTORIES
from app.services import cliente_auth_service as svc

router = APIRouter(prefix="/cliente/auth", tags=["Área do Cliente"])

_SECRET_PADRAO = "troque-esta-chave-em-producao"


class ClienteLoginRequest(BaseModel):
    cpf: str
    loja: str
    verificacao: str = ""  # só usada nos modos celular (4 últimos dígitos) e nascimento (ddmmaaaa)


class ClienteTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    nome: str
    loja: str
    loja_nome: str


@router.post("/login", response_model=ClienteTokenResponse, summary="Login do cliente final")
async def login_cliente(dados: ClienteLoginRequest, request: Request):
    # Com a chave padrão, qualquer pessoa que conheça o código forja tokens.
    if settings.SECRET_KEY == _SECRET_PADRAO:
        raise HTTPException(503, "Serviço indisponível: configuração de segurança pendente.")
    if dados.loja not in EMPRESAS:
        raise HTTPException(422, "Loja inválida.")

    cpf = svc.apenas_digitos(dados.cpf)
    ip = request.client.host if request.client else "?"
    chaves = (f"cpf:{cpf}", f"ip:{ip}")
    if svc.bloqueado(*chaves):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos e tente de novo.")

    async with SESSION_FACTORIES[dados.loja]() as db:
        if not await svc.modo_configurado_ok(db):
            raise HTTPException(503, "Login do cliente ainda não está habilitado para esta loja.")
        cliente = await svc.autenticar_cliente(db, cpf, dados.verificacao)

    if not cliente:
        svc.registrar_falha(*chaves)
        # Mesma resposta para CPF inexistente, repetido ou verificação errada.
        raise HTTPException(401, "Dados não conferem.")

    svc.limpar_falhas(*chaves)
    token = criar_token(
        {"sub": str(cliente["pessoa_id"]), "tipo": TIPO_CLIENTE, "loja": dados.loja},
        expira_minutos=settings.CLIENTE_TOKEN_MINUTOS,
    )
    return ClienteTokenResponse(
        access_token=token, nome=cliente["nome"] or "", loja=dados.loja, loja_nome=EMPRESAS[dados.loja]
    )


@router.get("/me", summary="Dados mínimos do cliente logado")
async def me(cliente: ClienteLogado = Depends(get_cliente_logado)):
    return {"pessoa_id": cliente.pessoa_id, "loja": cliente.loja, "loja_nome": EMPRESAS[cliente.loja]}
