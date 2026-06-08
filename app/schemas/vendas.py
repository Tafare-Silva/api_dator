from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


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


# ── Criação de Pré-Venda ──────────────────────────────────────────────────────

class ItemPreVendaInput(BaseModel):
    produto_id: int
    quantidade: Decimal
    vr_unitario_bruto: Decimal
    vr_desconto_total: Decimal = Decimal("0")
    vr_acrescimo_total: Decimal = Decimal("0")
    vendedor_id: int | None = None

    @field_validator("quantidade")
    @classmethod
    def quantidade_positiva(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantidade deve ser maior que zero")
        return v

    @field_validator("vr_unitario_bruto")
    @classmethod
    def preco_positivo(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Preço unitário não pode ser negativo")
        return v


class PreVendaInput(BaseModel):
    cliente_id: int | None = None
    vendedor_id: int | None = None
    data: date | None = None
    condicao_pagamento: str | None = None
    data_entrega: date | None = None
    obs: str | None = None
    itens: list[ItemPreVendaInput]

    @field_validator("itens")
    @classmethod
    def deve_ter_itens(cls, v: list) -> list:
        if not v:
            raise ValueError("A pré-venda deve ter pelo menos um item")
        return v


class PreVendaCriadaResponse(BaseModel):
    pk_chave: int
    data: date
    cliente_id: int | None = None
    cliente_nome: str | None = None
    vendedor_id: int | None = None
    vendedor_nome: str | None = None
    vr_total: Decimal
    quantidade_itens: int
