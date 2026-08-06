from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import quote_plus
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings, EMPRESAS


def _url_para(db_name: str) -> str:
    return (
        f"postgresql+asyncpg://{settings.DB_USER}:"
        f"{quote_plus(settings.DB_PASSWORD)}@"
        f"{settings.DB_HOST}:{settings.DB_PORT}/{db_name}"
    )


class Base(DeclarativeBase):
    pass


# Uma engine + sessionmaker por loja — mesmo host/usuário/senha, um banco
# Postgres por loja. Montadas uma vez na importação do módulo.
SESSION_FACTORIES: dict[str, async_sessionmaker[AsyncSession]] = {
    db_name: async_sessionmaker(
        bind=create_async_engine(
            _url_para(db_name),
            echo=settings.DEBUG,
            pool_size=10,
            max_overflow=20,
        ),
        class_=AsyncSession,
        expire_on_commit=False,
    )
    for db_name in EMPRESAS
}

for db_name in EMPRESAS:
    print(f"🔗 Loja registrada: {db_name} -> postgresql+asyncpg://{settings.DB_USER}:***@{settings.DB_HOST}:{settings.DB_PORT}/{db_name}")


# auto_error=False: /auth/login roda sem token nenhum (a loja vem explícita
# no corpo da requisição, não do JWT), então get_db não pode exigir token
# incondicionalmente na resolução de dependência — quem decide isso é o
# corpo de get_db abaixo.
_oauth2_scheme_opcional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_db(
    token: str | None = Depends(_oauth2_scheme_opcional),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency de banco usada por (quase) todos os endpoints. A loja (banco)
    a usar vem do claim "empresa" gravado no JWT no login — por isso todo
    endpoint que depende disso passa a exigir um token válido, mesmo que não
    declare `Depends(get_usuario_logado)` explicitamente.
    """
    from app.core.security import verificar_token  # import tardio evita ciclo com core.security

    erro_sessao = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão expirada ou loja não definida. Faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verificar_token(token) if token else None
    empresa = payload.get("empresa") if payload else None
    if empresa not in EMPRESAS:
        raise erro_sessao

    async with SESSION_FACTORIES[empresa]() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
