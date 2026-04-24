from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.item_mesa import ItemMesa
from app.models.mesa import Mesa
from app.models.produto import Produto
from app.schemas.item_mesa import ItemMesaCreate, ItemMesaUpdate, ResumoConta
from app.schemas.item_mesa import ItemMesaResponse


async def _get_produto_ativo(db: AsyncSession, produto_id: int) -> Produto:
    """Busca produto e garante que está ativo."""
    result = await db.execute(
        select(Produto).where(Produto.pk_chave == produto_id)
    )
    produto = result.scalar_one_or_none()
    if not produto:
        raise NotFoundError("Produto", produto_id)
    if produto.inativo:
        raise BusinessRuleError(
            f"O produto '{produto.nome}' está inativo e não pode ser lançado."
        )
    return produto


async def _get_mesa(db: AsyncSession, nome_mesa: str) -> Mesa:
    result = await db.execute(select(Mesa).where(Mesa.nome == nome_mesa))
    mesa = result.scalar_one_or_none()
    if not mesa:
        raise NotFoundError("Mesa", nome_mesa)
    return mesa


async def listar_itens_mesa(db: AsyncSession, nome_mesa: str) -> list[ItemMesa]:
    await _get_mesa(db, nome_mesa)
    result = await db.execute(
        select(ItemMesa)
        .options(selectinload(ItemMesa.produto))
        .where(ItemMesa.fk_mesas_mesa == nome_mesa)
        .order_by(ItemMesa.data_hora_inclusao)
    )
    return list(result.scalars().all())


async def adicionar_item(
    db: AsyncSession, nome_mesa: str, dados: ItemMesaCreate
) -> ItemMesa:
    await _get_mesa(db, nome_mesa)
    produto = await _get_produto_ativo(db, dados.fk_produtos_produto)

    # Se não foi informado valor, usa o preço de venda cadastrado
    vr_unitario = dados.vr_unitario_bruto if dados.vr_unitario_bruto else produto.preco_venda

    item = ItemMesa(
        fk_mesas_mesa=nome_mesa,
        fk_produtos_produto=dados.fk_produtos_produto,
        quantidade=dados.quantidade,
        vr_unitario_bruto=vr_unitario,
        observacoes_item=dados.observacoes_item,
        desdobramento=dados.desdobramento,
    )
    db.add(item)
    await db.flush()

    # Recarrega com o produto para retornar completo
    result = await db.execute(
        select(ItemMesa)
        .options(selectinload(ItemMesa.produto))
        .where(ItemMesa.pk_chave == item.pk_chave)
    )
    return result.scalar_one()


async def atualizar_item(
    db: AsyncSession, nome_mesa: str, item_id: int, dados: ItemMesaUpdate
) -> ItemMesa:
    result = await db.execute(
        select(ItemMesa)
        .options(selectinload(ItemMesa.produto))
        .where(ItemMesa.pk_chave == item_id, ItemMesa.fk_mesas_mesa == nome_mesa)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("Item da mesa", item_id)

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(item, campo, valor)

    await db.flush()
    await db.refresh(item)
    return item


async def remover_item(db: AsyncSession, nome_mesa: str, item_id: int) -> None:
    result = await db.execute(
        select(ItemMesa).where(
            ItemMesa.pk_chave == item_id,
            ItemMesa.fk_mesas_mesa == nome_mesa,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("Item da mesa", item_id)
    await db.delete(item)


async def get_resumo_conta(db: AsyncSession, nome_mesa: str) -> ResumoConta:
    """Retorna o resumo completo da conta de uma mesa (usado para impressão)."""
    itens = await listar_itens_mesa(db, nome_mesa)

    itens_response = [ItemMesaResponse.from_orm_with_total(i) for i in itens]
    total = sum(i.vr_total for i in itens_response)

    return ResumoConta(
        mesa=nome_mesa,
        itens=itens_response,
        total_bruto=total,
        quantidade_itens=len(itens_response),
    )


async def desdobrar_item(
    db: AsyncSession,
    nome_mesa: str,
    item_id: int,
    quantidade_desdobrada: Decimal,
) -> tuple[ItemMesa, ItemMesa]:
    """
    Divide um item em dois. Ex: 1 pizza → 2 meias pizzas.
    Reduz a quantidade do item original e cria um novo com desdobramento=True.
    """
    result = await db.execute(
        select(ItemMesa).where(
            ItemMesa.pk_chave == item_id,
            ItemMesa.fk_mesas_mesa == nome_mesa,
        )
    )
    item_original = result.scalar_one_or_none()
    if not item_original:
        raise NotFoundError("Item da mesa", item_id)

    if quantidade_desdobrada >= item_original.quantidade:
        raise BusinessRuleError(
            "A quantidade desdobrada deve ser menor que a quantidade original."
        )

    nova_qtd_original = item_original.quantidade - quantidade_desdobrada
    item_original.quantidade = nova_qtd_original

    novo_item = ItemMesa(
        fk_mesas_mesa=nome_mesa,
        fk_produtos_produto=item_original.fk_produtos_produto,
        quantidade=quantidade_desdobrada,
        vr_unitario_bruto=item_original.vr_unitario_bruto,
        observacoes_item=item_original.observacoes_item,
        desdobramento=True,
    )
    db.add(novo_item)
    await db.flush()
    await db.refresh(item_original)
    await db.refresh(novo_item)

    return item_original, novo_item
