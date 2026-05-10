from sqlalchemy import Boolean, Column, Date, Integer, Numeric, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


class Produto(Base):
    __tablename__ = "produtos"
    __table_args__ = {"schema": "cadastros"}

    pk_chave = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, nullable=True)
    inativo = Column(Boolean, nullable=False, default=False)
    preco_venda = Column(Numeric(14, 4), nullable=False, default=0)
    tipo_produto = Column(String(21), nullable=False, default="PRODUTO ACABADO")
    aplicacao = Column(Text, nullable=True)
    tamanho = Column(String(50), nullable=True)
    cor = Column(String(50), nullable=True)
    categoria = Column(String(200), nullable=True)
    colecao = Column(String, nullable=True)
    genero = Column(String, nullable=True)
    referencia_fabrica = Column(String, nullable=True)

    fk_marcas_marca = Column("fk_marcas$marca", String, nullable=False)
    fk_divisoes_divisao = Column("fk_divisoes$divisao", String, nullable=False)
    fk_unidades_unidade_venda = Column("fk_unidades$unidade_venda", String, nullable=False)

    # Relacionamentos
    itens_mesa = relationship("ItemMesa", back_populates="produto")
    codigos_barras = relationship("CodigoBarras", back_populates="produto")


class CodigoBarras(Base):
    __tablename__ = "codigo_barras"
    __table_args__ = {"schema": "cadastros"}

    fk_produtos_produto = Column(
        "fk_produtos$produto",
        Integer,
        ForeignKey("cadastros.produtos.pk_chave"),
        primary_key=True,
    )
    codigo_barras = Column(String(13), primary_key=True, nullable=False)

    produto = relationship("Produto", back_populates="codigos_barras")