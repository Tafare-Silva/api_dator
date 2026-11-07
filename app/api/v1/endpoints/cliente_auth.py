import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import EMPRESAS, settings
from app.core.deps_cliente import TIPO_CLIENTE, ClienteLogado, get_cliente_logado
from app.core.security import criar_token
from app.db.session import SESSION_FACTORIES
from app.services import cliente_auth_service as svc
from app.services import notificacao_service as notif

router = APIRouter(prefix="/cliente/auth", tags=["Área do Cliente"])
log = logging.getLogger("cliente_auth")

_SECRET_PADRAO = "troque-esta-chave-em-producao"


class SolicitarCodigoRequest(BaseModel):
    cpf: str
    loja: str


class VerificarCodigoRequest(SolicitarCodigoRequest):
    codigo: str


class ClienteTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    nome: str
    loja: str
    loja_nome: str


def _validar_base(loja: str):
    # Com a chave padrão, qualquer pessoa que conheça o código forja tokens.
    if settings.SECRET_KEY == _SECRET_PADRAO or not notif.provedor_ativo():
        raise HTTPException(503, "Serviço indisponível no momento.")
    if loja not in EMPRESAS:
        raise HTTPException(422, "Loja inválida.")


def _chaves(request: Request, cpf: str):
    ip = request.client.host if request.client else "?"
    return (f"cpf:{cpf}", f"ip:{ip}")


@router.post("/solicitar-codigo", summary="Valida o CPF e envia o código ao celular cadastrado")
async def solicitar_codigo(dados: SolicitarCodigoRequest, request: Request):
    _validar_base(dados.loja)
    cpf = svc.apenas_digitos(dados.cpf)
    chaves = _chaves(request, cpf)
    if svc.bloqueado(*chaves):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos e tente de novo.")

    async with SESSION_FACTORIES[dados.loja]() as db:
        cliente = await svc.buscar_cliente(db, cpf)

    # Consulta sem cadastro conta como tentativa (evita varrer CPFs para descobrir cadastros).
    if cliente is None or cliente == "duplicado":
        svc.registrar_falha(*chaves)
        raise HTTPException(404, {"codigo": "sem_cadastro", "mensagem":
            "Não encontramos cadastro com este CPF. Entre em contato com a loja para se cadastrar."})
    if not cliente["celular"]:
        raise HTTPException(422, {"codigo": "sem_celular", "mensagem":
            "Seu cadastro está sem celular. Procure a loja para atualizar o cadastro."})

    espera = svc.segundos_para_reenvio(dados.loja, cpf)
    if espera:
        raise HTTPException(429, f"Aguarde {espera}s para pedir um novo código.")

    codigo = svc.gerar_codigo(dados.loja, cpf)
    try:
        await notif.enviar_codigo(cliente["celular"], codigo)
    except Exception:
        svc.descartar_codigo(dados.loja, cpf)
        log.exception("falha ao enviar código")
        raise HTTPException(503, "Não foi possível enviar o código agora. Tente novamente.")
    svc.registrar_falha(chaves[1])  # limita pedidos de código por IP
    return {"enviado_para": svc.mascarar(cliente["celular"]),
            "validade_min": settings.CLIENTE_CODIGO_VALIDADE_MIN}


@router.post("/verificar-codigo", response_model=ClienteTokenResponse, summary="Troca o código pelo token")
async def verificar_codigo(dados: VerificarCodigoRequest, request: Request):
    _validar_base(dados.loja)
    cpf = svc.apenas_digitos(dados.cpf)
    chaves = _chaves(request, cpf)
    if svc.bloqueado(*chaves):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos e tente de novo.")

    if not svc.conferir_codigo(dados.loja, cpf, dados.codigo):
        svc.registrar_falha(*chaves)
        raise HTTPException(401, "Código inválido ou expirado.")

    async with SESSION_FACTORIES[dados.loja]() as db:
        cliente = await svc.buscar_cliente(db, cpf)
    if not isinstance(cliente, dict):
        raise HTTPException(401, "Código inválido ou expirado.")

    svc.limpar_falhas(*chaves)
    token = criar_token(
        {"sub": str(cliente["pessoa_id"]), "tipo": TIPO_CLIENTE, "loja": dados.loja},
        expira_minutos=settings.CLIENTE_TOKEN_MINUTOS,
    )
    return ClienteTokenResponse(
        access_token=token, nome=cliente["nome"] or "", loja=dados.loja, loja_nome=EMPRESAS[dados.loja])


@router.get("/me", summary="Dados mínimos do cliente logado")
async def me(cliente: ClienteLogado = Depends(get_cliente_logado)):
    return {"pessoa_id": cliente.pessoa_id, "loja": cliente.loja, "loja_nome": EMPRESAS[cliente.loja]}
