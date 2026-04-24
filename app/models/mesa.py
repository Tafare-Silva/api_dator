from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Mesa(Base):
    __tablename__ = "mesas"
    __table_args__ = {"schema": "marilia"}

    nome = Column(String, primary_key=True)
    observacoes = Column(Text, nullable=True)

    # Relacionamentos
    itens = relationship("ItemMesa", back_populates="mesa", cascade="all, delete-orphan")
