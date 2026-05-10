from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.produto import Produto, CodigoBarras


async def _obter_precos_em_lote(db: AsyncSession, produto_ids: list[int]) -> dict[int, Decimal]:
    """Busca preços de venda para múltiplos produtos de uma vez."""
    if not produto_ids:
        return {}
    result = await db.execute(
        text("""
            SELECT pk_chave, marilia.obter_preco_venda(pk_chave)
            FROM cadastros.produtos
            WHERE pk_chave = ANY(:ids)
        """),
        {"ids": produto_ids},
    )
    return {row[0]: Decimal(str(row[1])) if row[1] else Decimal("0") for row in result.fetchall()}


async def _obter_estoques_em_lote(db: AsyncSession, produto_ids: list[int]) -> dict[int, Decimal]:
    """Busca estoques para múltiplos produtos de uma vez."""
    if not produto_ids:
        return {}
    result = await db.execute(
        text("""
            SELECT "fk_produtos$produto", COALESCE(SUM(saldo), 0)
            FROM cadastros.v_estoque_atual
            WHERE "fk_produtos$produto" = ANY(:ids)
            GROUP BY "fk_produtos$produto"
        """),
        {"ids": produto_ids},
    )
    return {row[0]: Decimal(str(row[1])) for row in result.fetchall()}


async def _obter_preco_venda(db: AsyncSession, produto_id: int) -> Decimal:
    """Chama a função marilia.obter_preco_venda do PostgreSQL."""
    result = await db.execute(
        text("SELECT marilia.obter_preco_venda(:produto_id)"),
        {"produto_id": produto_id},
    )
    preco = result.scalar_one_or_none()
    return Decimal(str(preco)) if preco else Decimal("0")


async def _obter_estoque(db: AsyncSession, produto_id: int) -> Decimal:
    """Busca estoque de um produto."""
    result = await db.execute(
        text("""
            SELECT COALESCE(SUM(saldo), 0)
            FROM cadastros.v_estoque_atual
            WHERE "fk_produtos$produto" = :produto_id
        """),
        {"produto_id": produto_id},
    )
    estoque = result.scalar_one_or_none()
    return Decimal(str(estoque)) if estoque else Decimal("0")


async def listar_produtos(
    db: AsyncSession,
    apenas_ativos: bool = True,
    busca: str | None = None,
    categoria: str | None = None,
    codigo_barras: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    from sqlalchemy import or_

    # Busca por código de barras
    if codigo_barras:
        result = await db.execute(
            select(CodigoBarras).where(CodigoBarras.codigo_barras == codigo_barras)
        )
        cb = result.scalar_one_or_none()
        if not cb:
            return []
        query = select(Produto).where(Produto.pk_chave == cb.fk_produtos_produto)
    else:
        query = select(Produto)
        if apenas_ativos:
            query = query.where(Produto.inativo == False)  # noqa: E712
        if busca:
            termo = f"%{busca}%"
            query = query.where(
                or_(
                    Produto.nome.ilike(termo),
                    Produto.categoria.ilike(termo),
                    Produto.referencia_fabrica.ilike(termo),
                )
            )
        if categoria:
            query = query.where(Produto.categoria.ilike(f"%{categoria}%"))

    query = query.order_by(Produto.nome).limit(limit).offset(offset)
    result = await db.execute(query)
    produtos = list(result.scalars().all())

    if not produtos:
        return []

    # ✅ Busca preços e estoques em LOTE — muito mais rápido
    ids = [p.pk_chave for p in produtos]
    precos = await _obter_precos_em_lote(db, ids)
    estoques = await _obter_estoques_em_lote(db, ids)

    return [
        {
            "pk_chave": p.pk_chave,
            "nome": p.nome,
            "referencia_fabrica": p.referencia_fabrica,
            "preco_venda": precos.get(p.pk_chave, Decimal("0")),
            "estoque": estoques.get(p.pk_chave, Decimal("0")),
            "inativo": p.inativo,
            "categoria": p.categoria,
            "cor": p.cor,
            "tamanho": p.tamanho,
            "colecao": p.colecao,
            "marca": p.fk_marcas_marca,
            "divisao": p.fk_divisoes_divisao,
            "genero": p.genero,
        }
        for p in produtos
    ]


async def buscar_produto(db: AsyncSession, produto_id: int) -> dict:
    result = await db.execute(select(Produto).where(Produto.pk_chave == produto_id))
    produto = result.scalar_one_or_none()
    if not produto:
        raise NotFoundError("Produto", produto_id)

    preco = await _obter_preco_venda(db, produto_id)
    estoque = await _obter_estoque(db, produto_id)

    result_cb = await db.execute(
        select(CodigoBarras).where(CodigoBarras.fk_produtos_produto == produto_id)
    )
    codigos_barras = [cb.codigo_barras for cb in result_cb.scalars().all()]

    return {
        "pk_chave": produto.pk_chave,
        "nome": produto.nome,
        "referencia_fabrica": produto.referencia_fabrica,
        "preco_venda": preco,
        "estoque": estoque,
        "inativo": produto.inativo,
        "categoria": produto.categoria,
        "cor": produto.cor,
        "tamanho": produto.tamanho,
        "colecao": produto.colecao,
        "marca": produto.fk_marcas_marca,
        "divisao": produto.fk_divisoes_divisao,
        "genero": produto.genero,
        "tipo_produto": produto.tipo_produto,
        "unidade_venda": produto.fk_unidades_unidade_venda,
        "aplicacao": produto.aplicacao,
        "codigos_barras": codigos_barras,
    }