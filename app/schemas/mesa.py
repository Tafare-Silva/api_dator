from pydantic import BaseModel, Field


class MesaBase(BaseModel):
    nome: str = Field(..., description="Nome/identificação da mesa. Ex: Mesa 01, Balcão 02")
    observacoes: str | None = Field(None, description="Observações gerais da mesa")


class MesaCreate(MesaBase):
    pass


class MesaUpdate(BaseModel):
    observacoes: str | None = None


class MesaResponse(MesaBase):
    model_config = {"from_attributes": True}
