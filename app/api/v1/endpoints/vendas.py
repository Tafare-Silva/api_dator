from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_usuario_logado
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.vendas import ItemPreVendaInput, PreVendaInput, PreVendaCriadaResponse
from app.services.vendas_service import (
    criar_pre_venda,
    devolver_item_pre_venda,
    get_dashboard,
    get_pedido_venda_detalhe,
    get_pre_venda_detalhe,
    listar_pedidos_venda,
    listar_pre_vendas,
    listar_vendedores,
    restaurar_item_pre_venda,
)

router = APIRouter(prefix="/vendas", tags=["Vendas"])


# ── Vendedores ────────────────────────────────────────────────────────────────

@router.get("/vendedores", summary="Lista todos os vendedores ativos")
async def get_vendedores(
    apenas_ativos: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    return await listar_vendedores(db, apenas_ativos=apenas_ativos)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", summary="Dashboard com totais e ranking de vendedores")
async def get_dashboard_vendas(
    data_inicio: date = Query(default=None, description="Padrão: primeiro dia do mês atual"),
    data_fim: date = Query(default=None, description="Padrão: hoje"),
    db: AsyncSession = Depends(get_db),
):
    hoje = date.today()
    if not data_fim:
        data_fim = hoje
    if not data_inicio:
        data_inicio = hoje.replace(day=1)  # primeiro dia do mês

    return await get_dashboard(db, data_inicio=data_inicio, data_fim=data_fim)


# ── Pedidos de Venda ──────────────────────────────────────────────────────────

@router.get("/pedidos", summary="Lista pedidos de venda com filtros")
async def get_pedidos_venda(
    data_inicio: date = Query(default=None),
    data_fim: date = Query(default=None),
    vendedor_id: int | None = Query(default=None),
    cliente_id: int | None = Query(default=None),
    limit: int = Query(default=500, le=5000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    hoje = date.today()
    if not data_fim:
        data_fim = hoje
    if not data_inicio:
        data_inicio = hoje.replace(day=1)

    return await listar_pedidos_venda(
        db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        vendedor_id=vendedor_id,
        cliente_id=cliente_id,
        limit=limit,
        offset=offset,
    )


@router.get("/pedidos/{pedido_id}", summary="Detalhe completo de um pedido de venda")
async def get_pedido_detalhe(
    pedido_id: int,
    db: AsyncSession = Depends(get_db),
):
    pedido = await get_pedido_venda_detalhe(db, pedido_id)
    if not pedido:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Pedido {pedido_id} não encontrado.")
    return pedido


# ── Pré-Vendas ────────────────────────────────────────────────────────────────

@router.get("/pre-vendas", summary="Lista pré-vendas com filtros")
async def get_pre_vendas(
    data_inicio: date | None = Query(default=None),
    data_fim: date | None = Query(default=None),
    vendedor_id: int | None = Query(default=None),
    cliente_id: int | None = Query(default=None),
    efetivada: bool | None = Query(default=None, description="True=efetivadas, False=pendentes, omitir=todas"),
    limit: int = Query(default=500, le=5000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await listar_pre_vendas(
        db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        vendedor_id=vendedor_id,
        cliente_id=cliente_id,
        efetivada=efetivada,
        limit=limit,
        offset=offset,
    )


@router.get("/pre-vendas/{pre_venda_id}", summary="Detalhe completo de uma pré-venda")
async def get_pre_venda_detalhe_endpoint(
    pre_venda_id: int,
    db: AsyncSession = Depends(get_db),
):
    pv = await get_pre_venda_detalhe(db, pre_venda_id)
    if not pv:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Pré-venda {pre_venda_id} não encontrada.")
    return pv


@router.post(
    "/pre-vendas",
    summary="Cria uma nova pré-venda",
    response_model=PreVendaCriadaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def criar_pre_venda_endpoint(
    dados: PreVendaInput,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_logado),
):
    return await criar_pre_venda(db, dados, usuario.usuario_login)


@router.delete(
    "/pre-vendas/{pre_venda_id}/itens/{item_id}",
    summary="Devolve um item do condicional (remove o item da pré-venda)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def devolver_item_pre_venda_endpoint(
    pre_venda_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    await devolver_item_pre_venda(db, pre_venda_id, item_id)


@router.post(
    "/pre-vendas/{pre_venda_id}/itens/restaurar",
    summary="Desfaz uma devolução, recriando o item na pré-venda",
)
async def restaurar_item_pre_venda_endpoint(
    pre_venda_id: int,
    dados: ItemPreVendaInput,
    db: AsyncSession = Depends(get_db),
):
    return await restaurar_item_pre_venda(
        db,
        pre_venda_id,
        produto_id=dados.produto_id,
        quantidade=dados.quantidade,
        vr_unitario_bruto=dados.vr_unitario_bruto,
        vr_desconto_total=dados.vr_desconto_total,
        vr_acrescimo_total=dados.vr_acrescimo_total,
        vendedor_id=dados.vendedor_id,
    )