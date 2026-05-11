from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.produto import ProdutoResumo, ProdutoDetalhe
from app.services import produto_service

router = APIRouter(prefix="/produtos", tags=["Produtos"])


@router.get(
    "/",
    response_model=list[ProdutoResumo],
    summary="Lista produtos com busca por nome, referência, código ou código de barras",
)
async def listar_produtos(
    apenas_ativos: bool = Query(True),
    busca: str | None = Query(None, description="Busca por nome ou referência"),
    categoria: str | None = Query(None),
    codigo_barras: str | None = Query(None, description="Busca por código de barras ou pk_chave"),
    pk_chave_exato: int | None = Query(None, description="Busca exata por código interno (pk_chave)"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await produto_service.listar_produtos(
        db,
        apenas_ativos=apenas_ativos,
        busca=busca,
        categoria=categoria,
        codigo_barras=codigo_barras,
        pk_chave_exato=pk_chave_exato,
        limit=limit,
        offset=offset,
    )


@router.get("/{produto_id}", response_model=ProdutoDetalhe, summary="Detalhe completo de um produto")
async def detalhar_produto(produto_id: int, db: AsyncSession = Depends(get_db)):
    return await produto_service.buscar_produto(db, produto_id)