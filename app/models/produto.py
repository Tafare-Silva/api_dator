from sqlalchemy import Boolean, Column, Date, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Produto(Base):
    """
    Reflete a tabela cadastros.produtos do Dator.
    Este model é somente leitura para o app de mesas — 
    a manutenção de produtos continua sendo feita pelo Dator.
    """
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

    # Chaves estrangeiras (texto, padrão do ERP)
    fk_marcas_marca = Column("fk_marcas$marca", String, nullable=False)
    fk_divisoes_divisao = Column("fk_divisoes$divisao", String, nullable=False)
    fk_unidades_unidade_venda = Column("fk_unidades$unidade_venda", String, nullable=False)

    # Relacionamentos
    itens_mesa = relationship("ItemMesa", back_populates="produto")
