from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import estatisticas_service

router = APIRouter(prefix="/estatisticas", tags=["Estatísticas"])


@router.get("/filtros", summary="Retorna marcas, divisões e coleções disponíveis")
async def get_filtros(db: AsyncSession = Depends(get_db)):
    return await estatisticas_service.get_filtros_disponiveis(db)


@router.get("/curva-abc", summary="Curva ABC de produtos por valor vendido")
async def get_curva_abc(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    vendedor_id: int | None = Query(None),
    marca: str | None = Query(None),
    divisao: str | None = Query(None),
    colecao: str | None = Query(None),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await estatisticas_service.get_curva_abc(
        db, data_inicio=data_inicio, data_fim=data_fim,
        vendedor_id=vendedor_id, marca=marca, divisao=divisao,
        colecao=colecao, limit=limit,
    )


@router.get("/por-marca", summary="Vendas agrupadas por marca")
async def get_por_marca(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    vendedor_id: int | None = Query(None),
    divisao: str | None = Query(None),
    colecao: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await estatisticas_service.get_vendas_por_marca(
        db, data_inicio=data_inicio, data_fim=data_fim,
        vendedor_id=vendedor_id, divisao=divisao, colecao=colecao,
    )


@router.get("/por-divisao", summary="Vendas agrupadas por divisão")
async def get_por_divisao(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    vendedor_id: int | None = Query(None),
    marca: str | None = Query(None),
    colecao: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await estatisticas_service.get_vendas_por_divisao(
        db, data_inicio=data_inicio, data_fim=data_fim,
        vendedor_id=vendedor_id, marca=marca, colecao=colecao,
    )


@router.get("/por-colecao", summary="Vendas agrupadas por coleção")
async def get_por_colecao(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    vendedor_id: int | None = Query(None),
    marca: str | None = Query(None),
    divisao: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await estatisticas_service.get_vendas_por_colecao(
        db, data_inicio=data_inicio, data_fim=data_fim,
        vendedor_id=vendedor_id, marca=marca, divisao=divisao,
    )


@router.get("/por-genero", summary="Vendas agrupadas por gênero")
async def get_por_genero(
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    vendedor_id: int | None = Query(None),
    marca: str | None = Query(None),
    divisao: str | None = Query(None),
    colecao: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await estatisticas_service.get_vendas_por_genero(
        db, data_inicio=data_inicio, data_fim=data_fim,
        vendedor_id=vendedor_id, marca=marca, divisao=divisao, colecao=colecao,
    )