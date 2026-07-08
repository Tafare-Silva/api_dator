from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_admin
from app.db.session import get_db
from app.services.financeiro_service import (
    listar_centros_custos,
    listar_financeiro,
    listar_pessoas_financeiro,
    listar_planos_contas,
    resumo_financeiro,
)

router = APIRouter(prefix="/financeiro", tags=["Financeiro"])


# --- Contas a PAGAR (somente administradores) ---

@router.get("/contas-pagar", summary="Lista contas a pagar (P)")
async def get_contas_pagar(
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    data_baixa_inicio: date | None = Query(default=None),
    data_baixa_fim: date | None = Query(default=None),
    pessoa_id: int | None = Query(default=None),
    plano_contas_id: int | None = Query(default=None),
    centro_custos_id: int | None = Query(default=None),
    situacao: str | None = Query(default=None),
    limit: int = Query(default=500, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_admin),
):
    return await listar_financeiro(
        db, tipo_titulo='P',
        data_inicio=data_inicio, data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio, data_baixa_fim=data_baixa_fim,
        pessoa_id=pessoa_id, plano_contas_id=plano_contas_id,
        centro_custos_id=centro_custos_id, situacao=situacao,
        limit=limit, offset=offset,
    )


@router.get("/contas-pagar/resumo")
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
    _admin=Depends(get_admin),
):
    return await resumo_financeiro(
        db, tipo_titulo='P',
        data_inicio=data_inicio, data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio, data_baixa_fim=data_baixa_fim,
        pessoa_id=pessoa_id, plano_contas_id=plano_contas_id,
        centro_custos_id=centro_custos_id, situacao=situacao,
    )


# --- Contas a RECEBER (qualquer usuário autenticado: vendedores, caixas, admins) ---

@router.get("/contas-receber", summary="Lista contas a receber (R)")
async def get_contas_receber(
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    data_baixa_inicio: date | None = Query(default=None),
    data_baixa_fim: date | None = Query(default=None),
    pessoa_id: int | None = Query(default=None),
    plano_contas_id: int | None = Query(default=None),
    centro_custos_id: int | None = Query(default=None),
    situacao: str | None = Query(default=None),
    limit: int = Query(default=500, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await listar_financeiro(
        db, tipo_titulo='R',
        data_inicio=data_inicio, data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio, data_baixa_fim=data_baixa_fim,
        pessoa_id=pessoa_id, plano_contas_id=plano_contas_id,
        centro_custos_id=centro_custos_id, situacao=situacao,
        limit=limit, offset=offset,
    )


@router.get("/contas-receber/resumo")
async def get_resumo_contas_receber(
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
    return await resumo_financeiro(
        db, tipo_titulo='R',
        data_inicio=data_inicio, data_fim=data_fim,
        data_baixa_inicio=data_baixa_inicio, data_baixa_fim=data_baixa_fim,
        pessoa_id=pessoa_id, plano_contas_id=plano_contas_id,
        centro_custos_id=centro_custos_id, situacao=situacao,
    )


# --- Auxiliares ---

@router.get("/fornecedores")
async def get_fornecedores(db: AsyncSession = Depends(get_db), _admin=Depends(get_admin)):
    return await listar_pessoas_financeiro(db, tipo_titulo='P')


@router.get("/clientes")
async def get_clientes(db: AsyncSession = Depends(get_db)):
    return await listar_pessoas_financeiro(db, tipo_titulo='R')


@router.get("/planos-contas")
async def get_planos_contas(db: AsyncSession = Depends(get_db)):
    return await listar_planos_contas(db)


@router.get("/centros-custos")
async def get_centros_custos(db: AsyncSession = Depends(get_db)):
    return await listar_centros_custos(db)