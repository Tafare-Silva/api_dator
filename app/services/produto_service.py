from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.produto import Produto


async def _obter_preco_venda(db: AsyncSession, produto_id: int) -> Decimal:
    """Chama a função marilia.obter_preco_venda do PostgreSQL."""
    result = await db.execute(
        text("SELECT marilia.obter_preco_venda(:produto_id)"),
        {"produto_id": produto_id},
    )
    preco = result.scalar_one_or_none()
    return Decimal(str(preco)) if preco else Decimal("0")


async def listar_produtos(
    db: AsyncSession,
    apenas_ativos: bool = True,
    busca: str | None = None,
    categoria: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    from sqlalchemy import or_
    query = select(Produto)

    if apenas_ativos:
        query = query.where(Produto.inativo == False)  # noqa: E712

    if busca:
        termo = f"%{busca}%"
        query = query.where(
            or_(Produto.nome.ilike(termo), Produto.categoria.ilike(termo))
        )

    if categoria:
        query = query.where(Produto.categoria.ilike(f"%{categoria}%"))

    query = query.order_by(Produto.nome).limit(limit).offset(offset)
    result = await db.execute(query)
    produtos = list(result.scalars().all())

    # Busca o preço calculado para cada produto via função do banco
    resultado = []
    for p in produtos:
        preco = await _obter_preco_venda(db, p.pk_chave)
        resultado.append({
            "pk_chave": p.pk_chave,
            "nome": p.nome,
            "preco_venda": preco,
            "inativo": p.inativo,
            "categoria": p.categoria,
            "cor": p.cor,
            "tamanho": p.tamanho,
        })
    return resultado


async def buscar_produto(db: AsyncSession, produto_id: int) -> dict:
    result = await db.execute(
        select(Produto).where(Produto.pk_chave == produto_id)
    )
    produto = result.scalar_one_or_none()
    if not produto:
        raise NotFoundError("Produto", produto_id)

    preco = await _obter_preco_venda(db, produto_id)
    return {
        "pk_chave": produto.pk_chave,
        "nome": produto.nome,
        "preco_venda": preco,
        "inativo": produto.inativo,
        "categoria": produto.categoria,
        "cor": produto.cor,
        "tamanho": produto.tamanho,
        "tipo_produto": produto.tipo_produto,
        "fk_unidades_unidade_venda": produto.fk_unidades_unidade_venda,
        "aplicacao": produto.aplicacao,
    }