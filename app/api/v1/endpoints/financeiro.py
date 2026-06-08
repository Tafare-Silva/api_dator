from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.financeiro_service import (
    listar_centros_custos,
    listar_contas_pagar,
    listar_fornecedores,
    listar_planos_contas,
    resumo_contas_pagar,
)

router = APIRouter(prefix="/financeiro", tags=["Financeiro"])


@router.get("/contas-pagar", summary="Lista contas a pagar com filtros")
async def get_contas_pagar(
    data_inicio: date | None = Query(default=None, description="Vencimento a partir de"),
    data_fim: date | None = Query(default=None, description="Vencimento até"),
    data_baixa_inicio: date | None = Query(default=None, description="Data da baixa a partir de"),
    data_baixa_fim: date | None = Query(default=None, description="Data da baixa até"),
    pessoa_id: int | None = Query(default=None),
    plano_contas_id: int | None = Query(default=None),
    centro_custos_id: int | None = Query(default=None),
    situacao: str | None = Query(default=None, description="NORMAL=pendentes; PAGAS=pagas; omitir=todas"),
    limit: int = Query(default=500, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await listar_contas_pagar(
        db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio,
        data_baixa_fim=data_baixa_fim,
        pessoa_id=pessoa_id,
        plano_contas_id=plano_contas_id,
        centro_custos_id=centro_custos_id,
        situacao=situacao,
        limit=limit,
        offset=offset,
    )


@router.get("/contas-pagar/resumo", summary="Totais das contas a pagar")
async def get_resumo_contas_pagar(
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    data_baixa_inicio: date | None = Query(default=None),
    data_baixa_fim: date | None = Query(default=None),
    pessoa_id: int | None = Query(default=None),
    plano_contas_id: int | None = Query(default=None),
    centro_custos_id: int | None = Query(default=None),
    situacao: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await resumo_contas_pagar(
        db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio,
        data_baixa_fim=data_baixa_fim,
        pessoa_id=pessoa_id,
        plano_contas_id=plano_contas_id,
        centro_custos_id=centro_custos_id,
        situacao=situacao,
    )


@router.get("/fornecedores", summary="Fornecedores com contas a pagar")
async def get_fornecedores(db: AsyncSession = Depends(get_db)):
    return await listar_fornecedores(db)


@router.get("/planos-contas", summary="Planos de contas")
async def get_planos_contas(db: AsyncSession = Depends(get_db)):
    return await listar_planos_contas(db)


@router.get("/centros-custos", summary="Centros de custo")
async def get_centros_custos(db: AsyncSession = Depends(get_db)):
    return await listar_centros_custos(db)
