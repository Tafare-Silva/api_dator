from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import EMPRESAS
from app.core.deps import get_usuario_logado
from app.core.security import criar_token
from app.db.session import SESSION_FACTORIES
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, TokenResponse, UsuarioLogado
from app.services.auth_service import autenticar_usuario

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login do garçom/usuário",
)
async def login(dados: LoginRequest):
    if dados.empresa not in EMPRESAS:
        raise HTTPException(status_code=422, detail="Loja inválida.")

    # Sem token ainda (é o que este endpoint gera) -- a loja escolhida pelo
    # usuário decide direto qual banco abrir, sem passar por get_db.
    async with SESSION_FACTORIES[dados.empresa]() as db:
        usuario = await autenticar_usuario(db, dados.usuario_login, dados.senha)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = criar_token({"sub": usuario.usuario_login, "empresa": dados.empresa})

    return TokenResponse(
        access_token=token,
        nome_usuario=usuario.pessoa.nome if usuario.pessoa else usuario.usuario_login,
        grupo=usuario.fk_grupo_usuario_grupo_usuario,
        empresa=dados.empresa,
        empresa_nome=EMPRESAS[dados.empresa],
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
