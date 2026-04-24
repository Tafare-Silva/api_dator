from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class MovimentacaoEstoque(Base):
    __tablename__ = "movimentacao_estoque"
    __table_args__ = {"schema": "marilia"}

    pk_chave = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(Date, nullable=False)
    fk_pessoas_pessoa = Column("fk_pessoas$pessoa", Integer, ForeignKey("cadastros.pessoas.chave"), nullable=True)
    fk_tipos_movimentacao_tipo_movimento = Column("fk_tipos_movimentacao$tipo_movimento", String, nullable=False)
    obs = Column(Text, nullable=True)
    usuario = Column(String(80), nullable=True)
    cliente = Column(String(200), nullable=True)

    pedido_venda = relationship("PedidoVenda", back_populates="movimentacao", uselist=False)
    pre_venda = relationship("PreVenda", back_populates="movimentacao", uselist=False)
    itens = relationship("ItemMovimentacaoEstoque", back_populates="movimentacao")
    pessoa = relationship("Pessoa", foreign_keys=[fk_pessoas_pessoa])


class ItemMovimentacaoEstoque(Base):
    __tablename__ = "itens_movimentacao_estoque"
    __table_args__ = {"schema": "marilia"}

    pk_chave = Column(Integer, primary_key=True, autoincrement=True)
    fk_movimentacao_estoque_movimentacao_estoque = Column(
        "fk_movimentacao_estoque$movimentacao_estoque",
        Integer, ForeignKey("marilia.movimentacao_estoque.pk_chave"), nullable=False,
    )
    fk_produtos_produto = Column(
        "fk_produtos$produto", Integer, ForeignKey("cadastros.produtos.pk_chave"), nullable=False
    )
    quantidade = Column(Numeric(14, 6), nullable=False)
    fk_local_estoque_local = Column("fk_local_estoque$local", String, nullable=False)
    vr_desconto_total = Column(Numeric(14, 4), nullable=False)
    vr_unitario_bruto = Column(Numeric(14, 4), nullable=False)
    observacoes = Column(Text, nullable=True)
    vr_comissao = Column(Numeric(14, 4), nullable=False, default=0)
    vr_acrescimo_total = Column(Numeric(14, 4), nullable=False, default=0)

    movimentacao = relationship("MovimentacaoEstoque", back_populates="itens")
    produto = relationship("Produto", foreign_keys=[fk_produtos_produto])
    item_pedido_venda = relationship("ItemMovimentacaoEstoquePedidoVenda", back_populates="item_movimentacao", uselist=False)
    item_pre_venda = relationship("ItemMovimentacaoEstoquePreVenda", back_populates="item_movimentacao", uselist=False)


class PedidoVenda(Base):
    __tablename__ = "pedido_venda"
    __table_args__ = {"schema": "marilia"}

    fk_movimentacao_estoque_movimentacao_estoque = Column(
        "fk_movimentacao_estoque$movimentacao_estoque",
        Integer, ForeignKey("marilia.movimentacao_estoque.pk_chave"), primary_key=True,
    )
    fk_pessoas_vendedor = Column(
        "fk_pessoas$vendedor", Integer, ForeignKey("cadastros.pessoas.chave"), nullable=False
    )
    vr_frete = Column(Numeric(14, 4), nullable=False, default=0)
    data_registro_caixa = Column(DateTime, nullable=True)
    fila = Column(Integer, nullable=True)
    fk_pessoas_parceiro = Column("fk_pessoas$parceiro", Integer, nullable=True)

    movimentacao = relationship("MovimentacaoEstoque", back_populates="pedido_venda")
    vendedor = relationship("Pessoa", foreign_keys=[fk_pessoas_vendedor])


class ItemMovimentacaoEstoquePedidoVenda(Base):
    __tablename__ = "itens_movimentacao_estoque_pedido_venda"
    __table_args__ = {"schema": "marilia"}

    fk_itens_movimentacao_estoque_item_movimentacao = Column(
        "fk_itens_movimentacao_estoque$item_movimentacao",
        Integer, ForeignKey("marilia.itens_movimentacao_estoque.pk_chave"), primary_key=True,
    )
    fk_tipo_entrega_tipo_entrega = Column("fk_tipo_entrega$tipo_entrega", String, nullable=False)
    data_previsao_entrega = Column(Date, nullable=True)
    quantidade_entregar = Column(Numeric(14, 4), nullable=True)
    vr_custo_venda = Column(Numeric(14, 4), nullable=False, default=0)
    fk_pessoas_vendedor = Column(
        "fk_pessoas$vendedor", Integer, ForeignKey("cadastros.pessoas.chave"), nullable=True
    )
    quantidade_devolvida = Column(Numeric(14, 6), nullable=False, default=0)
    item_devolvido = Column(Boolean, nullable=False, default=False)

    item_movimentacao = relationship("ItemMovimentacaoEstoque", back_populates="item_pedido_venda")
    vendedor = relationship("Pessoa", foreign_keys=[fk_pessoas_vendedor])


class PreVenda(Base):
    __tablename__ = "pre_venda"
    __table_args__ = {"schema": "marilia"}

    fk_movimentacao_estoque_movimentacao_estoque = Column(
        "fk_movimentacao_estoque$movimentacao_estoque",
        Integer, ForeignKey("marilia.movimentacao_estoque.pk_chave"), primary_key=True,
    )
    fk_pessoas_vendedor = Column(
        "fk_pessoas$vendedor", Integer, ForeignKey("cadastros.pessoas.chave"), nullable=True
    )
    efetivada = Column(Boolean, nullable=False, default=False)
    condicao_pagamento = Column(String, nullable=True)
    data_entrega = Column(Date, nullable=True)

    movimentacao = relationship("MovimentacaoEstoque", back_populates="pre_venda")
    vendedor = relationship("Pessoa", foreign_keys=[fk_pessoas_vendedor])


class ItemMovimentacaoEstoquePreVenda(Base):
    __tablename__ = "itens_movimentacao_estoque_pre_venda"
    __table_args__ = {"schema": "marilia"}

    fk_itens_movimentacao_estoque_item_movimentacao = Column(
        "fk_itens_movimentacao_estoque$item_movimentacao",
        Integer, ForeignKey("marilia.itens_movimentacao_estoque.pk_chave"), primary_key=True,
    )
    fk_pessoas_vendedor = Column(
        "fk_pessoas$vendedor", Integer, ForeignKey("cadastros.pessoas.chave"), nullable=True
    )
    quantidade_devolvida = Column(Numeric(14, 6), nullable=False, default=0)
    item_devolvido = Column(Boolean, nullable=False, default=False)

    item_movimentacao = relationship("ItemMovimentacaoEstoque", back_populates="item_pre_venda")
    vendedor = relationship("Pessoa", foreign_keys=[fk_pessoas_vendedor])


class Funcionario(Base):
    __tablename__ = "funcionarios"
    __table_args__ = {"schema": "cadastros"}

    fk_pessoas_pessoa = Column(
        "fk_pessoas$pessoa", Integer, ForeignKey("cadastros.pessoas.chave"), primary_key=True
    )
    salario = Column(Numeric(14, 4), nullable=True)
    data_admissao = Column(Date, nullable=True)
    data_desligamento = Column(Date, nullable=True)
    e_vendedor = Column(Boolean, nullable=False, default=False)
    funcao = Column(String, nullable=True)

    pessoa = relationship("Pessoa", foreign_keys=[fk_pessoas_pessoa])