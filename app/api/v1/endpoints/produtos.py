from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.produto import ProdutoResumo, ProdutoResponse
from app.services import produto_service

router = APIRouter(prefix="/produtos", tags=["Produtos"])


@router.get(
    "/",
    response_model=list[ProdutoResumo],
    summary="Lista produtos disponíveis para lançamento",
)
async def listar_produtos(
    apenas_ativos: bool = Query(True, description="Filtra apenas produtos ativos"),
    busca: str | None = Query(None, description="Busca por nome ou categoria"),
    categoria: str | None = Query(None, description="Filtra por categoria"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await produto_service.listar_produtos(
        db,
        apenas_ativos=apenas_ativos,
        busca=busca,
        categoria=categoria,
        limit=limit,
        offset=offset,
    )


@router.get("/{produto_id}", response_model=ProdutoResponse, summary="Detalhe de um produto")
async def detalhar_produto(produto_id: int, db: AsyncSession = Depends(get_db)):
    return await produto_service.buscar_produto(db, produto_id)
