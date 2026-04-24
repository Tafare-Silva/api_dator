from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.item_mesa import ItemMesaCreate, ItemMesaResponse, ItemMesaUpdate, ResumoConta
from app.services import item_mesa_service

router = APIRouter(prefix="/mesas/{nome_mesa}/itens", tags=["Itens da Mesa"])


@router.get(
    "/",
    response_model=list[ItemMesaResponse],
    summary="Lista os itens de uma mesa",
)
async def listar_itens(nome_mesa: str, db: AsyncSession = Depends(get_db)):
    itens = await item_mesa_service.listar_itens_mesa(db, nome_mesa)
    return [ItemMesaResponse.from_orm_with_total(i) for i in itens]


@router.get(
    "/conta",
    response_model=ResumoConta,
    summary="Resumo da conta da mesa (para exibição e impressão)",
)
async def resumo_conta(nome_mesa: str, db: AsyncSession = Depends(get_db)):
    return await item_mesa_service.get_resumo_conta(db, nome_mesa)


@router.post(
    "/",
    response_model=ItemMesaResponse,
    status_code=201,
    summary="Adiciona um produto à mesa",
)
async def adicionar_item(
    nome_mesa: str,
    dados: ItemMesaCreate,
    db: AsyncSession = Depends(get_db),
):
    item = await item_mesa_service.adicionar_item(db, nome_mesa, dados)
    return ItemMesaResponse.from_orm_with_total(item)


@router.patch(
    "/{item_id}",
    response_model=ItemMesaResponse,
    summary="Atualiza quantidade ou observação de um item",
)
async def atualizar_item(
    nome_mesa: str,
    item_id: int,
    dados: ItemMesaUpdate,
    db: AsyncSession = Depends(get_db),
):
    item = await item_mesa_service.atualizar_item(db, nome_mesa, item_id, dados)
    return ItemMesaResponse.from_orm_with_total(item)


@router.delete("/{item_id}", status_code=204, summary="Remove um item da mesa")
async def remover_item(
    nome_mesa: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    await item_mesa_service.remover_item(db, nome_mesa, item_id)


@router.post(
    "/{item_id}/desdobrar",
    response_model=list[ItemMesaResponse],
    summary="Desdobra um item em dois (ex: divide uma pizza)",
)
async def desdobrar_item(
    nome_mesa: str,
    item_id: int,
    quantidade: Decimal = Query(..., gt=0, description="Quantidade a desdobrar do item original"),
    db: AsyncSession = Depends(get_db),
):
    item_original, novo_item = await item_mesa_service.desdobrar_item(
        db, nome_mesa, item_id, quantidade
    )
    return [
        ItemMesaResponse.from_orm_with_total(item_original),
        ItemMesaResponse.from_orm_with_total(novo_item),
    ]
