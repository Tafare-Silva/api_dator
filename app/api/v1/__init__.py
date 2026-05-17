from app.api.v1.endpoints import auth, impressao, itens_mesa, mesas, produtos, vendas, estatisticas

from fastapi import APIRouter, Depends

from app.core.deps import get_usuario_logado

autenticado = Depends(get_usuario_logado)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(mesas.router, dependencies=[autenticado])
api_router.include_router(itens_mesa.router, dependencies=[autenticado])
api_router.include_router(produtos.router, dependencies=[autenticado])
api_router.include_router(impressao.router, dependencies=[autenticado])
api_router.include_router(vendas.router, dependencies=[autenticado])
api_router.include_router(estatisticas.router, dependencies=[autenticado])