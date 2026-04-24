from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_usuario_logado
from app.core.security import criar_token
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, TokenResponse, UsuarioLogado
from app.services.auth_service import autenticar_usuario

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login do garçom/usuário",
)
async def login(dados: LoginRequest, db: AsyncSession = Depends(get_db)):
    usuario = await autenticar_usuario(db, dados.usuario_login, dados.senha)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = criar_token({"sub": usuario.usuario_login})

    return TokenResponse(
        access_token=token,
        nome_usuario=usuario.pessoa.nome if usuario.pessoa else usuario.usuario_login,
        grupo=usuario.fk_grupo_usuario_grupo_usuario,
    )


@router.get(
    "/me",
    response_model=UsuarioLogado,
    summary="Retorna os dados do usuário logado",
)
async def me(usuario_logado: Usuario = Depends(get_usuario_logado)):
    return UsuarioLogado(
        fk_pessoas=usuario_logado.fk_pessoas,
        usuario_login=usuario_logado.usuario_login,
        nome=usuario_logado.pessoa.nome if usuario_logado.pessoa else None,
        grupo=usuario_logado.fk_grupo_usuario_grupo_usuario,
    )
