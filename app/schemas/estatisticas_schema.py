from decimal import Decimal
from datetime import date
from pydantic import BaseModel


class ItemCurvaABC(BaseModel):
    produto_id: int
    produto_nome: str | None
    total_vendido: Decimal
    quantidade_vendida: Decimal
    quantidade_pedidos: int
    pct_individual: Decimal
    pct_acumulado: Decimal
    curva: str  # A, B ou C


class ItemVendasPorGrupo(BaseModel):
    nome: str
    total_vendido: Decimal
    quantidade_vendida: Decimal
    quantidade_pedidos: int
    pct: float


class FiltrosDisponiveis(BaseModel):
    marcas: list[str]
    divisoes: list[dict]
    colecoes: list[str]