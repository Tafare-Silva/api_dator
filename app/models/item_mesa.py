from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class ItemMesa(Base):
    __tablename__ = "itens_mesa"
    __table_args__ = {"schema": "marilia"}

    pk_chave = Column(Integer, primary_key=True, autoincrement=True)
    fk_mesas_mesa = Column(
        "fk_mesas$mesa",
        String,
        ForeignKey("marilia.mesas.nome", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=True,
    )
    fk_produtos_produto = Column(
        "fk_produtos$produto",
        Integer,
        ForeignKey("cadastros.produtos.pk_chave"),
        nullable=False,
    )
    quantidade = Column(Numeric(14, 4), nullable=False)
    vr_unitario_bruto = Column(Numeric(14, 4), nullable=False)
    data_hora_inclusao = Column(DateTime, nullable=False, server_default=func.now())
    observacoes_item = Column(String(250), nullable=True)
    desdobramento = Column(Boolean, nullable=False, default=False)

    # Relacionamentos
    mesa = relationship("Mesa", back_populates="itens")
    produto = relationship("Produto", back_populates="itens_mesa")
