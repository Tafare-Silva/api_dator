from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.usuario import Usuario


async def autenticar_usuario(
    db: AsyncSession, login: str, senha: str
) -> Usuario | None:
    """
    Busca o usuário pelo login e compara a senha.
    Retorna o Usuario se válido, None caso contrário.

    """
    result = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.pessoa))
        .where(Usuario.usuario_login == login)
    )
    usuario = result.scalar_one_or_none()

    if not usuario:
        return None

    # Comparação direta — texto puro
    if usuario.senha != senha:
        return None

    # Garante que a pessoa vinculada está ativa
    if usuario.pessoa and usuario.pessoa.inativo:
        return None

    return usuario
