from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# ── Vendedor ──────────────────────────────────────────────────────────────────

class VendedorResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pk_chave: int
    nome: str | None = None


# ── Dashboard ─────────────────────────────────────────────────────────────────

class RankingVendedor(BaseModel):
    vendedor_id: int
    vendedor_nome: str
    total_vendas: Decimal
    quantidade_pedidos: int
    ticket_medio: Decimal


class DashboardVendas(BaseModel):
    # Totais do período
    total_vendas: Decimal
    quantidade_pedidos: int
    ticket_medio: Decimal

    # Totais do dia de hoje
    total_vendas_hoje: Decimal
    quantidade_pedidos_hoje: int

    # Ranking
    ranking_vendedores: list[RankingVendedor]

    # Período consultado
    data_inicio: date
    data_fim: date


# ── Pedido de Venda ───────────────────────────────────────────────────────────

class ItemVendaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pk_chave: int
    produto_id: int
    produto_nome: str | None = None
    quantidade: Decimal
    vr_unitario_bruto: Decimal
    vr_desconto_total: Decimal
    vr_acrescimo_total: Decimal
    vr_total_liquido: Decimal  # calculado: (qtd * unitario) - desconto + acrescimo
    item_devolvido: bool = False
    quantidade_devolvida: Decimal = Decimal("0")


class PedidoVendaResumo(BaseModel):
    pk_chave: int
    data: date
    cliente_id: int | None = None
    cliente_nome: str | None = None
    vendedor_id: int
    vendedor_nome: str | None = None
    vr_total: Decimal
    vr_frete: Decimal
    quantidade_itens: int


class PedidoVendaDetalhe(PedidoVendaResumo):
    itens: list[ItemVendaResponse]


class PedidoVendaFiltros(BaseModel):
    data_inicio: date
    data_fim: date
    vendedor_id: int | None = None
    cliente_id: int | None = None


# ── Pré-Venda ─────────────────────────────────────────────────────────────────

class PreVendaResumo(BaseModel):
    pk_chave: int
    data: date
    cliente_id: int | None = None
    cliente_nome: str | None = None
    vendedor_id: int | None = None
    vendedor_nome: str | None = None
    efetivada: bool
    condicao_pagamento: str | None = None
    data_entrega: date | None = None
    vr_total: Decimal
    quantidade_itens: int


class PreVendaDetalhe(PreVendaResumo):
    itens: list[ItemVendaResponse]


class PreVendaFiltros(BaseModel):
    data_inicio: date | None = None
    data_fim: date | None = None
    vendedor_id: int | None = None
    cliente_id: int | None = None
    efetivada: bool | None = None  # None = todos, True = efetivadas, False = pendentes


# ── Vendedores ────────────────────────────────────────────────────────────────

class VendedorResponse(BaseModel):
    pk_chave: int
    nome: str | None = None
    funcao: str | None = None
    data_admissao: date | None = None
    ativo: bool  # data_desligamento is None


# ── Vendas por vendedor ───────────────────────────────────────────────────────

class VendasPorVendedor(BaseModel):
    vendedor_id: int
    vendedor_nome: str
    total_vendas: Decimal
    quantidade_pedidos: int
    ticket_medio: Decimal
    pedidos: list[PedidoVendaResumo]
