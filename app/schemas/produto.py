from decimal import Decimal
from pydantic import BaseModel


class ProdutoResumo(BaseModel):
    pk_chave: int
    nome: str | None
    referencia_fabrica: str | None = None
    preco_venda: Decimal
    estoque: Decimal = Decimal("0")
    inativo: bool
    categoria: str | None = None
    cor: str | None = None
    tamanho: str | None = None
    colecao: str | None = None
    marca: str | None = None
    divisao: str | None = None
    genero: str | None = None

    model_config = {"from_attributes": True}


class ProdutoDetalhe(ProdutoResumo):
    tipo_produto: str | None = None
    unidade_venda: str | None = None
    aplicacao: str | None = None
    codigos_barras: list[str] = []

    model_config = {"from_attributes": True}