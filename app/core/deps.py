from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import verificar_token
from app.db.session import get_db
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_usuario_logado(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """
    Dependency que protege rotas autenticadas.
    Extrai o usuário do token JWT e valida que ainda existe e está ativo.
    """
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verificar_token(token)
    if not payload:
        raise credenciais_invalidas

    login: str | None = payload.get("sub")
    if not login:
        raise credenciais_invalidas

    result = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.pessoa))
        .where(Usuario.usuario_login == login)
    )
    usuario = result.scalar_one_or_none()

    if not usuario:
        raise credenciais_invalidas

    if usuario.pessoa and usuario.pessoa.inativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo. Contate o administrador.",
        )

    return usuario
