"""Autenticação do cliente final (Área do Cliente).

Token separado do token da equipe: carrega tipo="cliente", a loja e o id da
pessoa -- e NÃO carrega o claim "empresa", que é o que get_db exige. Por isso
um token de cliente é recusado em toda rota interna, e o inverso também vale.
"""
from dataclasses import dataclass
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import EMPRESAS
from app.core.security import verificar_token

TIPO_CLIENTE = "cliente"

_oauth2_cliente = OAuth2PasswordBearer(tokenUrl="/api/v1/cliente/auth/login", auto_error=False)


@dataclass(frozen=True)
class ClienteLogado:
    pessoa_id: int
    loja: str


def _nao_autenticado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão expirada. Entre novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_cliente_logado(token: str | None = Depends(_oauth2_cliente)) -> ClienteLogado:
    payload = verificar_token(token) if token else None
    if not payload or payload.get("tipo") != TIPO_CLIENTE:
        raise _nao_autenticado()
    loja = payload.get("loja")
    try:
        pessoa_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise _nao_autenticado()
    if loja not in EMPRESAS:
        raise _nao_autenticado()
    return ClienteLogado(pessoa_id=pessoa_id, loja=loja)


async def get_db_cliente(
    cliente: ClienteLogado = Depends(get_cliente_logado),
) -> AsyncGenerator[AsyncSession, None]:
    from app.db.session import SESSION_FACTORIES  # import tardio, evita ciclo

    async with SESSION_FACTORIES[cliente.loja]() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
