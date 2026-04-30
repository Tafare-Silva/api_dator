"""
Serviço de vendas — toda a lógica de consulta fica aqui,
os endpoints são apenas roteadores finos.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.vendas import (
    Funcionario,
    ItemMovimentacaoEstoque,
    ItemMovimentacaoEstoquePedidoVenda,
    MovimentacaoEstoque,
    PedidoVenda,
    PreVenda,
)

# Tipo de movimentação que identifica vendas no ERP
TIPO_VENDA = "VENDA DE MERCADORIA"
TIPO_PRE_VENDA = "PRE-VENDA"


def _calcular_vr_total_item(item: ItemMovimentacaoEstoque) -> Decimal:
    """Valor líquido do item: (qtd * unitario) - desconto + acrescimo"""
    bruto = abs(item.quantidade) * item.vr_unitario_bruto
    return bruto - item.vr_desconto_total + item.vr_acrescimo_total


# ── Vendedores ────────────────────────────────────────────────────────────────

async def listar_vendedores(db: AsyncSession, apenas_ativos: bool = True) -> list[dict]:
    query = (
        select(Funcionario)
        .options(selectinload(Funcionario.pessoa))
        .where(Funcionario.e_vendedor == True)  # noqa: E712
    )
    if apenas_ativos:
        query = query.where(Funcionario.data_desligamento == None)  # noqa: E711

    result = await db.execute(query)
    funcionarios = result.scalars().all()

    return [
        {
            "pk_chave": f.fk_pessoas_pessoa,
            "nome": f.pessoa.nome if f.pessoa else None,
            "funcao": f.funcao,
            "data_admissao": f.data_admissao,
            "ativo": f.data_desligamento is None,
        }
        for f in funcionarios
    ]


# ── Dashboard ─────────────────────────────────────────────────────────────────

async def get_dashboard(
    db: AsyncSession,
    data_inicio: date,
    data_fim: date,
) -> dict:
    hoje = date.today()

    # Query base para vendas no período
    stmt_periodo = (
        select(
            func.count(PedidoVenda.fk_movimentacao_estoque_movimentacao_estoque).label("qtd"),
            func.coalesce(
                func.sum(
                    select(func.sum(
                        ItemMovimentacaoEstoque.quantidade * ItemMovimentacaoEstoque.vr_unitario_bruto
                        - ItemMovimentacaoEstoque.vr_desconto_total
                        + ItemMovimentacaoEstoque.vr_acrescimo_total
                    ))
                    .where(ItemMovimentacaoEstoque.fk_movimentacao_estoque_movimentacao_estoque
                           == PedidoVenda.fk_movimentacao_estoque_movimentacao_estoque)
                    .correlate(PedidoVenda)
                    .scalar_subquery()
                ), Decimal("0")
            ).label("total"),
        )
        .join(MovimentacaoEstoque,
              MovimentacaoEstoque.pk_chave
              == PedidoVenda.fk_movimentacao_estoque_movimentacao_estoque)
        .where(
            and_(
                MovimentacaoEstoque.fk_tipos_movimentacao_tipo_movimento == TIPO_VENDA,
                MovimentacaoEstoque.data >= data_inicio,
                MovimentacaoEstoque.data <= data_fim,
            )
        )
    )

    # Usa SQL direto para performance — mais simples e rápido
    sql_dashboard = text("""
        SELECT
            COUNT(pv.fk_movimentacao_estoque$movimentacao_estoque) AS qtd_pedidos,
            COALESCE(SUM(
                (SELECT COALESCE(SUM(
                    ABS(ime.quantidade) * ime.vr_unitario_bruto
                    - ime.vr_desconto_total
                    + ime.vr_acrescimo_total
                ), 0)
                FROM marilia.itens_movimentacao_estoque ime
                WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave)
            ), 0) AS total_vendas
        FROM marilia.pedido_venda pv
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        WHERE me."fk_tipos_movimentacao$tipo_movimento" = :tipo_venda
          AND me.data BETWEEN :data_inicio AND :data_fim
    """)

    sql_hoje = text("""
        SELECT
            COUNT(pv.fk_movimentacao_estoque$movimentacao_estoque) AS qtd_pedidos,
            COALESCE(SUM(
                (SELECT COALESCE(SUM(
                    ABS(ime.quantidade) * ime.vr_unitario_bruto
                    - ime.vr_desconto_total
                    + ime.vr_acrescimo_total
                ), 0)
                FROM marilia.itens_movimentacao_estoque ime
                WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave)
            ), 0) AS total_vendas
        FROM marilia.pedido_venda pv
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        WHERE me."fk_tipos_movimentacao$tipo_movimento" = :tipo_venda
          AND me.data = :hoje
    """)

    sql_ranking = text("""
        SELECT
            p.chave AS vendedor_id,
            p.nome AS vendedor_nome,
            COUNT(DISTINCT me.pk_chave) AS qtd_pedidos,
            COALESCE(SUM(
                ABS(ime.quantidade) * ime.vr_unitario_bruto
                - ime.vr_desconto_total
                + ime.vr_acrescimo_total
            ), 0) AS total_vendas
        FROM marilia.itens_movimentacao_estoque ime
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = ime."fk_movimentacao_estoque$movimentacao_estoque"
        JOIN marilia.pedido_venda pv
            ON pv."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
        LEFT JOIN marilia.itens_movimentacao_estoque_pedido_venda impv
            ON impv."fk_itens_movimentacao_estoque$item_movimentacao" = ime.pk_chave
        JOIN cadastros.pessoas p
            ON p.chave = COALESCE(impv."fk_pessoas$vendedor", pv."fk_pessoas$vendedor")
        WHERE me."fk_tipos_movimentacao$tipo_movimento" = :tipo_venda
          AND me.data BETWEEN :data_inicio AND :data_fim
        GROUP BY p.chave, p.nome
        ORDER BY total_vendas DESC
        LIMIT 10
    """)

    params = {"tipo_venda": TIPO_VENDA, "data_inicio": data_inicio, "data_fim": data_fim}
    params_hoje = {"tipo_venda": TIPO_VENDA, "hoje": hoje}

    r_periodo = (await db.execute(sql_dashboard, params)).one()
    r_hoje = (await db.execute(sql_hoje, params_hoje)).one()
    r_ranking = (await db.execute(sql_ranking, params)).all()

    qtd = int(r_periodo.qtd_pedidos or 0)
    total = Decimal(str(r_periodo.total_vendas or 0))
    ticket = (total / qtd) if qtd > 0 else Decimal("0")

    qtd_hoje = int(r_hoje.qtd_pedidos or 0)
    total_hoje = Decimal(str(r_hoje.total_vendas or 0))

    ranking = [
        {
            "vendedor_id": row.vendedor_id,
            "vendedor_nome": row.vendedor_nome or "—",
            "total_vendas": Decimal(str(row.total_vendas or 0)),
            "quantidade_pedidos": int(row.qtd_pedidos or 0),
            "ticket_medio": (
                Decimal(str(row.total_vendas or 0)) / int(row.qtd_pedidos)
                if row.qtd_pedidos else Decimal("0")
            ),
        }
        for row in r_ranking
    ]

    return {
        "total_vendas": total,
        "quantidade_pedidos": qtd,
        "ticket_medio": ticket,
        "total_vendas_hoje": total_hoje,
        "quantidade_pedidos_hoje": qtd_hoje,
        "ranking_vendedores": ranking,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }


# ── Pedidos de Venda ──────────────────────────────────────────────────────────

async def listar_pedidos_venda(
    db: AsyncSession,
    data_inicio: date,
    data_fim: date,
    vendedor_id: int | None = None,
    cliente_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:

    conditions = [
        "me.\"fk_tipos_movimentacao$tipo_movimento\" = :tipo_venda",
        "me.data BETWEEN :data_inicio AND :data_fim",
    ]
    params: dict = {
        "tipo_venda": TIPO_VENDA,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "limit": limit,
        "offset": offset,
    }

    if vendedor_id:
        # MUDANÇA: Filtro OR para buscar vendedor no cabeçalho OU nos itens
        conditions.append("""(
            pv."fk_pessoas$vendedor" = :vendedor_id 
            OR EXISTS (
                SELECT 1 
                FROM marilia.itens_movimentacao_estoque_pedido_venda impv
                WHERE impv."fk_itens_movimentacao_estoque$item_movimentacao" IN (
                    SELECT ime.pk_chave 
                    FROM marilia.itens_movimentacao_estoque ime
                    WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
                )
                AND impv."fk_pessoas$vendedor" = :vendedor_id
            )
        )""")
        params["vendedor_id"] = vendedor_id

    if cliente_id:
        conditions.append("me.\"fk_pessoas$pessoa\" = :cliente_id")
        params["cliente_id"] = cliente_id

    where = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            me.pk_chave,
            me.data,
            me."fk_pessoas$pessoa" AS cliente_id,
            pc.nome AS cliente_nome,
            pv."fk_pessoas$vendedor" AS vendedor_id,
            pven.nome AS vendedor_nome,
            pv.vr_frete,
            COALESCE((
                SELECT SUM(
                    ABS(ime.quantidade) * ime.vr_unitario_bruto
                    - ime.vr_desconto_total
                    + ime.vr_acrescimo_total
                )
                FROM marilia.itens_movimentacao_estoque ime
                WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
            ), 0) AS vr_total,
            (
                SELECT COUNT(*)
                FROM marilia.itens_movimentacao_estoque ime
                WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
            ) AS quantidade_itens
        FROM marilia.pedido_venda pv
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        LEFT JOIN cadastros.pessoas pc ON pc.chave = me."fk_pessoas$pessoa"
        LEFT JOIN cadastros.pessoas pven ON pven.chave = pv."fk_pessoas$vendedor"
        WHERE {where}
        ORDER BY me.data DESC, me.pk_chave DESC
        LIMIT :limit OFFSET :offset
    """)

    rows = (await db.execute(sql, params)).all()

    return [
        {
            "pk_chave": row.pk_chave,
            "data": row.data,
            "cliente_id": row.cliente_id,
            "cliente_nome": row.cliente_nome,
            "vendedor_id": row.vendedor_id,
            "vendedor_nome": row.vendedor_nome,
            "vr_total": Decimal(str(row.vr_total or 0)),
            "vr_frete": Decimal(str(row.vr_frete or 0)),
            "quantidade_itens": int(row.quantidade_itens or 0),
        }
        for row in rows
    ]


async def get_pedido_venda_detalhe(db: AsyncSession, pedido_id: int) -> dict:
    sql_cabecalho = text("""
        SELECT
            me.pk_chave,
            me.data,
            me."fk_pessoas$pessoa" AS cliente_id,
            pc.nome AS cliente_nome,
            pv."fk_pessoas$vendedor" AS vendedor_id,
            pven.nome AS vendedor_nome,
            pv.vr_frete
        FROM marilia.pedido_venda pv
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        LEFT JOIN cadastros.pessoas pc ON pc.chave = me."fk_pessoas$pessoa"
        LEFT JOIN cadastros.pessoas pven ON pven.chave = pv."fk_pessoas$vendedor"
        WHERE me.pk_chave = :pedido_id
    """)

    sql_itens = text("""
        SELECT
            ime.pk_chave,
            ime."fk_produtos$produto" AS produto_id,
            pr.nome AS produto_nome,
            ABS(ime.quantidade) AS quantidade,
            ime.vr_unitario_bruto,
            ime.vr_desconto_total,
            ime.vr_acrescimo_total,
            ABS(ime.quantidade) * ime.vr_unitario_bruto
                - ime.vr_desconto_total + ime.vr_acrescimo_total AS vr_total_liquido,
            COALESCE(impv.item_devolvido, false) AS item_devolvido,
            COALESCE(impv.quantidade_devolvida, 0) AS quantidade_devolvida,
            COALESCE(impv."fk_pessoas$vendedor", :vendedor_cabecalho_id) AS vendedor_id,
            pven_item.nome AS vendedor_nome
        FROM marilia.itens_movimentacao_estoque ime
        LEFT JOIN cadastros.produtos pr ON pr.pk_chave = ime."fk_produtos$produto"
        LEFT JOIN marilia.itens_movimentacao_estoque_pedido_venda impv
            ON impv."fk_itens_movimentacao_estoque$item_movimentacao" = ime.pk_chave
        LEFT JOIN cadastros.pessoas pven_item
            ON pven_item.chave = COALESCE(impv."fk_pessoas$vendedor", :vendedor_cabecalho_id)
        WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = :pedido_id
        ORDER BY ime.pk_chave
    """)

    cab = (await db.execute(sql_cabecalho, {"pedido_id": pedido_id})).one_or_none()
    if not cab:
        return None

    vendedor_cabecalho_id = cab.vendedor_id

    itens_rows = (await db.execute(sql_itens, {"pedido_id": pedido_id, "vendedor_cabecalho_id": vendedor_cabecalho_id})).all()

    itens = [
        {
            "pk_chave": i.pk_chave,
            "produto_id": i.produto_id,
            "produto_nome": i.produto_nome,
            "quantidade": Decimal(str(i.quantidade or 0)),
            "vr_unitario_bruto": Decimal(str(i.vr_unitario_bruto or 0)),
            "vr_desconto_total": Decimal(str(i.vr_desconto_total or 0)),
            "vr_acrescimo_total": Decimal(str(i.vr_acrescimo_total or 0)),
            "vr_total_liquido": Decimal(str(i.vr_total_liquido or 0)),
            "item_devolvido": i.item_devolvido,
            "quantidade_devolvida": Decimal(str(i.quantidade_devolvida or 0)),
            "vendedor_id": i.vendedor_id,
            "vendedor_nome": i.vendedor_nome,
        }
        for i in itens_rows
    ]

    vr_total = sum(i["vr_total_liquido"] for i in itens)

    return {
        "pk_chave": cab.pk_chave,
        "data": cab.data,
        "cliente_id": cab.cliente_id,
        "cliente_nome": cab.cliente_nome,
        "vendedor_id": cab.vendedor_id,
        "vendedor_nome": cab.vendedor_nome,
        "vr_total": vr_total,
        "vr_frete": Decimal(str(cab.vr_frete or 0)),
        "quantidade_itens": len(itens),
        "itens": itens,
    }


# ── Pré-Vendas ────────────────────────────────────────────────────────────────

async def listar_pre_vendas(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    vendedor_id: int | None = None,
    cliente_id: int | None = None,
    efetivada: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:

    conditions = ["me.\"fk_tipos_movimentacao$tipo_movimento\" = :tipo_venda"]
    params: dict = {"tipo_venda": TIPO_PRE_VENDA, "limit": limit, "offset": offset}

    if data_inicio:
        conditions.append("me.data >= :data_inicio")
        params["data_inicio"] = data_inicio
    if data_fim:
        conditions.append("me.data <= :data_fim")
        params["data_fim"] = data_fim
    if vendedor_id:
        # MUDANÇA: Filtro OR para buscar vendedor no cabeçalho OU nos itens
        conditions.append("""(
            pv."fk_pessoas$vendedor" = :vendedor_id 
            OR EXISTS (
                SELECT 1 
                FROM marilia.itens_movimentacao_estoque_pre_venda impv
                WHERE impv."fk_itens_movimentacao_estoque$item_movimentacao" IN (
                    SELECT ime.pk_chave 
                    FROM marilia.itens_movimentacao_estoque ime
                    WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
                )
                AND impv."fk_pessoas$vendedor" = :vendedor_id
            )
        )""")
        params["vendedor_id"] = vendedor_id
    if cliente_id:
        conditions.append("me.\"fk_pessoas$pessoa\" = :cliente_id")
        params["cliente_id"] = cliente_id
    if efetivada is not None:
        conditions.append("pv.efetivada = :efetivada")
        params["efetivada"] = efetivada

    where = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            me.pk_chave,
            me.data,
            me."fk_pessoas$pessoa" AS cliente_id,
            pc.nome AS cliente_nome,
            pv."fk_pessoas$vendedor" AS vendedor_id,
            pven.nome AS vendedor_nome,
            pv.efetivada,
            pv.condicao_pagamento,
            pv.data_entrega,
            COALESCE((
                SELECT SUM(
                    ABS(ime.quantidade) * ime.vr_unitario_bruto
                    - ime.vr_desconto_total
                    + ime.vr_acrescimo_total
                )
                FROM marilia.itens_movimentacao_estoque ime
                WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
            ), 0) AS vr_total,
            (
                SELECT COUNT(*)
                FROM marilia.itens_movimentacao_estoque ime
                WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
            ) AS quantidade_itens
        FROM marilia.pre_venda pv
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        LEFT JOIN cadastros.pessoas pc ON pc.chave = me."fk_pessoas$pessoa"
        LEFT JOIN cadastros.pessoas pven ON pven.chave = pv."fk_pessoas$vendedor"
        WHERE {where}
        ORDER BY me.data DESC, me.pk_chave DESC
        LIMIT :limit OFFSET :offset
    """)

    rows = (await db.execute(sql, params)).all()

    return [
        {
            "pk_chave": row.pk_chave,
            "data": row.data,
            "cliente_id": row.cliente_id,
            "cliente_nome": row.cliente_nome,
            "vendedor_id": row.vendedor_id,
            "vendedor_nome": row.vendedor_nome,
            "efetivada": row.efetivada,
            "condicao_pagamento": row.condicao_pagamento,
            "data_entrega": row.data_entrega,
            "vr_total": Decimal(str(row.vr_total or 0)),
            "quantidade_itens": int(row.quantidade_itens or 0),
        }
        for row in rows
    ]


async def get_pre_venda_detalhe(db: AsyncSession, pre_venda_id: int) -> dict | None:
    sql_cabecalho = text("""
        SELECT
            me.pk_chave,
            me.data,
            me."fk_pessoas$pessoa" AS cliente_id,
            pc.nome AS cliente_nome,
            pv."fk_pessoas$vendedor" AS vendedor_id,
            pven.nome AS vendedor_nome,
            pv.efetivada,
            pv.condicao_pagamento,
            pv.data_entrega
        FROM marilia.pre_venda pv
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        LEFT JOIN cadastros.pessoas pc ON pc.chave = me."fk_pessoas$pessoa"
        LEFT JOIN cadastros.pessoas pven ON pven.chave = pv."fk_pessoas$vendedor"
        WHERE me.pk_chave = :id
    """)

    sql_itens = text("""
        SELECT
            ime.pk_chave,
            ime."fk_produtos$produto" AS produto_id,
            pr.nome AS produto_nome,
            ABS(ime.quantidade) AS quantidade,
            ime.vr_unitario_bruto,
            ime.vr_desconto_total,
            ime.vr_acrescimo_total,
            ABS(ime.quantidade) * ime.vr_unitario_bruto
                - ime.vr_desconto_total + ime.vr_acrescimo_total AS vr_total_liquido,
            COALESCE(impv.item_devolvido, false) AS item_devolvido,
            COALESCE(impv.quantidade_devolvida, 0) AS quantidade_devolvida,
            COALESCE(impv."fk_pessoas$vendedor", :vendedor_cabecalho_id) AS vendedor_id,
            pven_item.nome AS vendedor_nome
        FROM marilia.itens_movimentacao_estoque ime
        LEFT JOIN cadastros.produtos pr ON pr.pk_chave = ime."fk_produtos$produto"
        LEFT JOIN marilia.itens_movimentacao_estoque_pre_venda impv
            ON impv."fk_itens_movimentacao_estoque$item_movimentacao" = ime.pk_chave
        LEFT JOIN cadastros.pessoas pven_item
            ON pven_item.chave = COALESCE(impv."fk_pessoas$vendedor", :vendedor_cabecalho_id)
        WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = :id
        ORDER BY ime.pk_chave
    """)

    cab = (await db.execute(sql_cabecalho, {"id": pre_venda_id})).one_or_none()
    if not cab:
        return None

    vendedor_cabecalho_id = cab.vendedor_id

    itens_rows = (await db.execute(sql_itens, {"id": pre_venda_id, "vendedor_cabecalho_id": vendedor_cabecalho_id})).all()

    itens = [
        {
            "pk_chave": i.pk_chave,
            "produto_id": i.produto_id,
            "produto_nome": i.produto_nome,
            "quantidade": Decimal(str(i.quantidade or 0)),
            "vr_unitario_bruto": Decimal(str(i.vr_unitario_bruto or 0)),
            "vr_desconto_total": Decimal(str(i.vr_desconto_total or 0)),
            "vr_acrescimo_total": Decimal(str(i.vr_acrescimo_total or 0)),
            "vr_total_liquido": Decimal(str(i.vr_total_liquido or 0)),
            "item_devolvido": i.item_devolvido,
            "quantidade_devolvida": Decimal(str(i.quantidade_devolvida or 0)),
            "vendedor_id": i.vendedor_id,
            "vendedor_nome": i.vendedor_nome,
        }
        for i in itens_rows
    ]

    vr_total = sum(i["vr_total_liquido"] for i in itens)

    return {
        "pk_chave": cab.pk_chave,
        "data": cab.data,
        "cliente_id": cab.cliente_id,
        "cliente_nome": cab.cliente_nome,
        "vendedor_id": cab.vendedor_id,
        "vendedor_nome": cab.vendedor_nome,
        "efetivada": cab.efetivada,
        "condicao_pagamento": cab.condicao_pagamento,
        "data_entrega": cab.data_entrega,
        "vr_total": vr_total,
        "quantidade_itens": len(itens),
        "itens": itens,
    }