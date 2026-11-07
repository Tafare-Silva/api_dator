"""Login do cliente final: CPF -> código de 6 dígitos enviado ao celular cadastrado."""
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

# Estado em memória: vale por processo, e a API roda com 1 worker. Se passar a
# ter vários, trocar por Redis ou tabela.
_falhas: dict[str, list[float]] = defaultdict(list)
_codigos: dict[tuple[str, str], dict] = {}  # (loja, cpf) -> {hash, exp, erros, enviado}
MAX_ERROS_CODIGO = 5


def apenas_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


# ---- trava por tentativas (cpf / ip) ----
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


# ---- cadastro ----
def normalizar_celular(valor: str | None) -> str | None:
    """Só dígitos com DDI 55, ou None se não parecer telefone BR."""
    d = apenas_digitos(valor)
    if len(d) in (12, 13) and d.startswith("55"):
        return d
    if len(d) in (10, 11):
        return "55" + d
    return None


def mascarar(celular: str) -> str:
    return f"(**) *****-{celular[-4:]}"


async def buscar_cliente(db: AsyncSession, cpf: str) -> dict | None | str:
    """dict = cliente único; None = sem cadastro; 'duplicado' = CPF em mais de um cadastro."""
    if len(cpf) != 11:
        return None
    linhas = (await db.execute(text(r"""
        SELECT p.chave, p.nome, p.celular_principal FROM cadastros.pessoas p
        WHERE p.cliente AND NOT coalesce(p.inativo, false)
          AND regexp_replace(coalesce(p.cpf_cnpj,''), '\D', '', 'g') = :cpf
        LIMIT 2"""), {"cpf": cpf})).mappings().all()
    if not linhas:
        return None
    if len(linhas) > 1:
        return "duplicado"
    p = linhas[0]
    return {"pessoa_id": p["chave"], "nome": p["nome"],
            "celular": normalizar_celular(p["celular_principal"])}


# ---- código ----
def _hash(loja: str, cpf: str, codigo: str) -> str:
    msg = f"{loja}:{cpf}:{codigo}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def segundos_para_reenvio(loja: str, cpf: str) -> int:
    c = _codigos.get((loja, cpf))
    if not c:
        return 0
    return max(0, int(c["enviado"] + settings.CLIENTE_CODIGO_REENVIO_SEG - time.time()))


def gerar_codigo(loja: str, cpf: str) -> str:
    codigo = f"{secrets.randbelow(10**6):06d}"
    _codigos[(loja, cpf)] = {
        "hash": _hash(loja, cpf, codigo),
        "exp": time.time() + settings.CLIENTE_CODIGO_VALIDADE_MIN * 60,
        "erros": 0, "enviado": time.time(),
    }
    return codigo


def descartar_codigo(loja: str, cpf: str) -> None:
    _codigos.pop((loja, cpf), None)


def conferir_codigo(loja: str, cpf: str, informado: str) -> bool:
    """Código vale uma vez; erra MAX_ERROS_CODIGO vezes e ele é invalidado."""
    c = _codigos.get((loja, cpf))
    if not c or time.time() > c["exp"]:
        _codigos.pop((loja, cpf), None)
        return False
    if hmac.compare_digest(c["hash"], _hash(loja, cpf, apenas_digitos(informado))):
        _codigos.pop((loja, cpf), None)
        return True
    c["erros"] += 1
    if c["erros"] >= MAX_ERROS_CODIGO:
        _codigos.pop((loja, cpf), None)
    return False
