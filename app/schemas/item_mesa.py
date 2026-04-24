from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ItemMesaCreate(BaseModel):
    fk_produtos_produto: int = Field(..., description="Código (pk_chave) do produto")
    quantidade: Decimal = Field(..., gt=0, description="Quantidade do item")
    vr_unitario_bruto: Decimal = Field(..., ge=0, description="Valor unitário bruto")
    observacoes_item: str | None = Field(None, max_length=250, description="Ex: sem açúcar, bem passado")
    desdobramento: bool = Field(False, description="True se este item originou de um desdobramento")

    @field_validator("quantidade")
    @classmethod
    def quantidade_positiva(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantidade deve ser maior que zero")
        return v


class ItemMesaUpdate(BaseModel):
    quantidade: Decimal | None = Field(None, gt=0)
    observacoes_item: str | None = Field(None, max_length=250)
    vr_unitario_bruto: Decimal | None = Field(None, ge=0)


class ProdutoEmItem(BaseModel):
    pk_chave: int
    nome: str | None

    model_config = {"from_attributes": True}


class ItemMesaResponse(BaseModel):
    pk_chave: int
    fk_mesas_mesa: str | None
    fk_produtos_produto: int
    quantidade: Decimal
    vr_unitario_bruto: Decimal
    vr_total: Decimal  # campo calculado
    data_hora_inclusao: datetime
    observacoes_item: str | None
    desdobramento: bool
    produto: ProdutoEmItem | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_total(cls, item) -> "ItemMesaResponse":
        return cls(
            pk_chave=item.pk_chave,
            fk_mesas_mesa=item.fk_mesas_mesa,
            fk_produtos_produto=item.fk_produtos_produto,
            quantidade=item.quantidade,
            vr_unitario_bruto=item.vr_unitario_bruto,
            vr_total=item.quantidade * item.vr_unitario_bruto,
            data_hora_inclusao=item.data_hora_inclusao,
            observacoes_item=item.observacoes_item,
            desdobramento=item.desdobramento,
            produto=item.produto,
        )


class ResumoConta(BaseModel):
    """Resumo da conta de uma mesa para exibição/impressão."""
    mesa: str
    itens: list[ItemMesaResponse]
    total_bruto: Decimal
    quantidade_itens: int
