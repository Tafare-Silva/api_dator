from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps_cliente import ClienteLogado, get_cliente_logado, get_db_cliente
from app.services import cliente_area_service as svc

router = APIRouter(prefix="/cliente", tags=["Área do Cliente"])


class ItemCarrinho(BaseModel):
    produto_id: int
    quantidade: int = Field(1, ge=1, le=20)


class CondicionalRequest(BaseModel):
    itens: list[ItemCarrinho] = Field(min_length=1, max_length=50)


@router.post("/condicionais", summary="Gera o condicional do carrinho para o cliente logado")
async def gerar_condicional(
    dados: CondicionalRequest,
    cliente: ClienteLogado = Depends(get_cliente_logado),
    db: AsyncSession = Depends(get_db_cliente),
):
    # Cliente vem do token; preço, estoque e vendedor são resolvidos no servidor.
    return await svc.criar_condicional(
        db, cliente.pessoa_id, [(i.produto_id, i.quantidade) for i in dados.itens])


@router.get("/titulos", summary="Títulos em aberto do cliente logado")
async def titulos(
    cliente: ClienteLogado = Depends(get_cliente_logado),
    db: AsyncSession = Depends(get_db_cliente),
):
    return await svc.titulos_em_aberto(db, cliente.pessoa_id)
