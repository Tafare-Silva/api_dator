from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.apuracao_service import (
    apuracao_resultado,
    despesas_por_centro_custo,
    despesas_por_plano_contas,
    receitas_por_plano_contas,
    vendido_vs_recebido,
)

router = APIRouter(prefix="/financeiro", tags=["Apuração"])


@router.get("/despesas/por-plano-contas", summary="Despesas agrupadas por plano de contas")
async def get_despesas_por_plano_contas(
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    data_baixa_inicio: date | None = Query(default=None),
    data_baixa_fim: date | None = Query(default=None),
    situacao: str | None = Query(default=None),
    centro_custos_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await despesas_por_plano_contas(
        db, data_inicio=data_inicio, data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio, data_baixa_fim=data_baixa_fim,
        situacao=situacao, centro_custos_id=centro_custos_id,
    )


@router.get("/despesas/por-centro-custo", summary="Despesas agrupadas por centro de custos")
async def get_despesas_por_centro_custo(
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    data_baixa_inicio: date | None = Query(default=None),
    data_baixa_fim: date | None = Query(default=None),
    situacao: str | None = Query(default=None),
    plano_contas_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await despesas_por_centro_custo(
        db, data_inicio=data_inicio, data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio, data_baixa_fim=data_baixa_fim,
        situacao=situacao, plano_contas_id=plano_contas_id,
    )


@router.get("/receitas/por-plano-contas", summary="Receitas agrupadas por plano de contas")
async def get_receitas_por_plano_contas(
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    data_baixa_inicio: date | None = Query(default=None),
    data_baixa_fim: date | None = Query(default=None),
    situacao: str | None = Query(default=None),
    centro_custos_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await receitas_por_plano_contas(
        db, data_inicio=data_inicio, data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio, data_baixa_fim=data_baixa_fim,
        situacao=situacao, centro_custos_id=centro_custos_id,
    )


@router.get("/dre", summary="Apuração de resultado simplificada (receitas x despesas x saldo)")
async def get_dre(
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    data_baixa_inicio: date | None = Query(default=None),
    data_baixa_fim: date | None = Query(default=None),
    situacao: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await apuracao_resultado(
        db, data_inicio=data_inicio, data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio, data_baixa_fim=data_baixa_fim,
        situacao=situacao,
    )


@router.get("/vendido-vs-recebido", summary="Total vendido no período x total efetivamente recebido no caixa")
async def get_vendido_vs_recebido(
    data_inicio: date = Query(...),
    data_fim: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await vendido_vs_recebido(db, data_inicio=data_inicio, data_fim=data_fim)
