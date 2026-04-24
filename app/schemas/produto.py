from decimal import Decimal

from pydantic import BaseModel, Field


class ProdutoResponse(BaseModel):
    pk_chave: int
    nome: str | None
    preco_venda: Decimal
    tipo_produto: str
    fk_unidades_unidade_venda: str = Field(alias="fk_unidades_unidade_venda")
    inativo: bool
    categoria: str | None
    cor: str | None
    tamanho: str | None

    model_config = {"from_attributes": True}


class ProdutoResumo(BaseModel):
    
    pk_chave: int
    nome: str | None
    preco_venda: Decimal
    inativo: bool

    model_config = {"from_attributes": True}
