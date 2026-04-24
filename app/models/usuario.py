from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Pessoa(Base):
    __tablename__ = "pessoas"
    __table_args__ = {"schema": "cadastros"}

    chave = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, nullable=True)
    inativo = Column(Boolean, nullable=False, default=False)
    usuario = Column(Boolean, nullable=False, default=False)

    # Relacionamento
    usuario_rel = relationship("Usuario", back_populates="pessoa", uselist=False)


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "cadastros"}

    fk_pessoas = Column(
        Integer,
        ForeignKey("cadastros.pessoas.chave", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    usuario_login = Column(String, nullable=False)
    senha = Column(String(255), nullable=False)
    fk_empresas = Column(Integer, nullable=False)
    fk_grupo_usuario_grupo_usuario = Column(
        "fk_grupo_usuario$grupo_usuario", String, nullable=True
    )

    # Relacionamento
    pessoa = relationship("Pessoa", back_populates="usuario_rel")
