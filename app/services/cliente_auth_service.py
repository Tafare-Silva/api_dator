"""Login do cliente final: CPF + uma segunda verificação configurável."""
import hmac
import re
import time
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

MODOS_VALIDOS = ("cpf", "celular", "nascimento")

# Falhas recentes por chave (cpf / ip). Em memória: vale por processo, e a API
# roda com 1 worker. Se passar a ter vários, trocar por Redis ou tabela.
_falhas: dict[str, list[float]] = defaultdict(list)


def apenas_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def _recentes(chave: str, agora: float) -> list[float]:
    janela = settings.CLIENTE_JANELA_BLOQUEIO_MIN * 60
    _falhas[chave] = [t for t in _falhas[chave] if agora - t < janela]
    return _falhas[chave]


def bloqueado(*chaves: str) -> bool:
    agora = time.time()
    return any(len(_recentes(c, agora)) >= settings.CLIENTE_MAX_TENTATIVAS for c in chaves)


def registrar_falha(*chaves: str) -> None:
    agora = time.time()
    for c in chaves:
        _recentes(c, agora).append(agora)


def limpar_falhas(*chaves: str) -> None:
    for c in chaves:
        _falhas.pop(c, None)


_tem_nascimento: dict[str, bool] = {}


async def _banco_tem_nascimento(db: AsyncSession) -> bool:
    banco = db.get_bind().url.database
    if banco not in _tem_nascimento:
        r = await db.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_schema='cadastros' "
            "AND table_name='pessoas' AND column_name='dt_nascimento'"))
        _tem_nascimento[banco] = r.first() is not None
    return _tem_nascimento[banco]


async def modo_configurado_ok(db: AsyncSession) -> bool:
    modo = settings.CLIENTE_LOGIN_MODO
    if modo not in MODOS_VALIDOS:
        return False
    if modo == "nascimento":
        return await _banco_tem_nascimento(db)
    return True


async def autenticar_cliente(db: AsyncSession, cpf: str, verificacao: str) -> dict | None:
    """Devolve {"pessoa_id", "nome"} ou None. Sempre None se o CPF não
    identificar exatamente UM cliente ativo (homônimo ou repetido não entra)."""
    cpf = apenas_digitos(cpf)
    if len(cpf) != 11:
        return None

    colunas = "p.chave, p.nome, p.celular_principal"
    if settings.CLIENTE_LOGIN_MODO == "nascimento":
        colunas += ", p.dt_nascimento"
    linhas = (await db.execute(
        text(f"""
            SELECT {colunas} FROM cadastros.pessoas p
            WHERE p.cliente AND NOT coalesce(p.inativo, false)
              AND regexp_replace(coalesce(p.cpf_cnpj,''), '\\D', '', 'g') = :cpf
            LIMIT 2
        """),
        {"cpf": cpf},
    )).mappings().all()
    if len(linhas) != 1:
        return None
    p = linhas[0]

    if settings.CLIENTE_LOGIN_MODO == "cpf":
        # Só CPF: quem souber o CPF de um cliente cadastrado entra como ele.
        # A defesa fica no bloqueio por tentativas e nos limites do condicional.
        ok = True
    elif settings.CLIENTE_LOGIN_MODO == "celular":
        esperado = apenas_digitos(p["celular_principal"])[-4:]
        informado = apenas_digitos(verificacao)
        ok = len(esperado) == 4 and hmac.compare_digest(esperado, informado)
    else:  # nascimento
        nasc = p["dt_nascimento"]
        ok = nasc is not None and hmac.compare_digest(
            nasc.strftime("%d%m%Y"), apenas_digitos(verificacao))
    return {"pessoa_id": p["chave"], "nome": p["nome"]} if ok else None
