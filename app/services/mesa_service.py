from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.mesa import Mesa
from app.schemas.mesa import MesaCreate, MesaUpdate


async def listar_mesas(db: AsyncSession) -> list[Mesa]:
    result = await db.execute(select(Mesa).order_by(Mesa.nome))
    return list(result.scalars().all())


async def buscar_mesa(db: AsyncSession, nome: str) -> Mesa:
    result = await db.execute(
        select(Mesa)
        .options(selectinload(Mesa.itens))
        .where(Mesa.nome == nome)
    )
    mesa = result.scalar_one_or_none()
    if not mesa:
        raise NotFoundError("Mesa", nome)
    return mesa


async def criar_mesa(db: AsyncSession, dados: MesaCreate) -> Mesa:
    # Verifica duplicidade
    existente = await db.execute(select(Mesa).where(Mesa.nome == dados.nome))
    if existente.scalar_one_or_none():
        raise BusinessRuleError(f"Já existe uma mesa com o nome '{dados.nome}'.")

    mesa = Mesa(**dados.model_dump())
    db.add(mesa)
    await db.flush()
    await db.refresh(mesa)
    return mesa


async def atualizar_mesa(db: AsyncSession, nome: str, dados: MesaUpdate) -> Mesa:
    mesa = await buscar_mesa(db, nome)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(mesa, campo, valor)
    await db.flush()
    await db.refresh(mesa)
    return mesa


async def excluir_mesa(db: AsyncSession, nome: str) -> None:
    mesa = await buscar_mesa(db, nome)
    await db.delete(mesa)
