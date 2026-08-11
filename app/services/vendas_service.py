"""
Serviço de vendas — toda a lógica de consulta fica aqui,
os endpoints são apenas roteadores finos.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.vendas import (
    Funcionario,
    ItemMovimentacaoEstoque,
    ItemMovimentacaoEstoquePedidoVenda,
    MovimentacaoEstoque,
    PedidoVenda,
    PreVenda,
)
from app.schemas.vendas import PreVendaInput

TIPO_VENDA = "VENDA DE MERCADORIA"
TIPO_PRE_VENDA = "PRE-VENDA"


def _calcular_vr_total_item(item: ItemMovimentacaoEstoque) -> Decimal:
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

    # ✅ Totais do período usando query direta
    sql_dashboard = text("""
        SELECT
            COUNT(pv."fk_movimentacao_estoque$movimentacao_estoque") AS qtd_pedidos,
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
            COUNT(pv."fk_movimentacao_estoque$movimentacao_estoque") AS qtd_pedidos,
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

    # ✅ RANKING usa a função oficial do ERP para garantir consistência com o ERP
    # LEFT JOIN LATERAL resolve o vendedor (chave + secao) uma única vez por
    # linha, reaproveitado também na subquery de contagem de pedidos — evita
    # repetir o mesmo lookup por nome 3x como antes.
    sql_ranking = text("""
        SELECT
            rel.nome_vendedor,
            rel.vr_total_vendas,
            rel.vr_total_devolucoes,
            pess.chave AS vendedor_id,
            pess.secao,
            (
                SELECT COUNT(DISTINCT pv2."fk_movimentacao_estoque$movimentacao_estoque")
                FROM marilia.pedido_venda pv2
                JOIN marilia.movimentacao_estoque me2
                    ON me2.pk_chave = pv2."fk_movimentacao_estoque$movimentacao_estoque"
                WHERE me2."fk_tipos_movimentacao$tipo_movimento" = :tipo_venda
                AND me2.data BETWEEN :data_inicio AND :data_fim
                AND pv2."fk_pessoas$vendedor" = pess.chave
            ) AS qtd_pedidos
        FROM marilia.relatorio_vendas_por_vendedor(:data_inicio, :data_fim) AS rel
        LEFT JOIN LATERAL (
            SELECT p.chave, p.secao
            FROM cadastros.pessoas p
            WHERE p.nome = rel.nome_vendedor AND p.chave > 0
            ORDER BY p.chave DESC
            LIMIT 1
        ) pess ON true
        ORDER BY rel.vr_total_vendas DESC
        LIMIT 100
    """)

    params = {
        "tipo_venda": TIPO_VENDA,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    r_periodo = (await db.execute(sql_dashboard, params)).one()
    r_hoje = (await db.execute(sql_hoje, {"tipo_venda": TIPO_VENDA, "hoje": hoje})).one()
    r_ranking = (await db.execute(sql_ranking, params)).all()

    qtd = int(r_periodo.qtd_pedidos or 0)
    total = Decimal(str(r_periodo.total_vendas or 0))
    ticket = (total / qtd) if qtd > 0 else Decimal("0")

    qtd_hoje = int(r_hoje.qtd_pedidos or 0)
    total_hoje = Decimal(str(r_hoje.total_vendas or 0))

    ranking = []
    for row in r_ranking:
        total_vendas = Decimal(str(row.vr_total_vendas or 0))
        total_dev = Decimal(str(row.vr_total_devolucoes or 0))
        # ✅ total líquido = vendas - devoluções (igual ao ERP)
        total_liquido = total_vendas - total_dev
        qtd_ped = int(row.qtd_pedidos or 0)
        ranking.append({
            "vendedor_id": row.vendedor_id or 0,
            "vendedor_nome": row.nome_vendedor or "—",
            "secao": row.secao,
            "total_vendas": total_liquido,
            "quantidade_pedidos": qtd_ped,
            "ticket_medio": (total_liquido / qtd_ped) if qtd_ped > 0 else Decimal("0"),
        })

    # Agrupa o ranking por seção (cadastros.pessoas.secao) — vendedores sem
    # seção definida caem em "Sem Seção" em vez de serem descartados.
    secoes_map: dict[str, list[dict]] = {}
    for item in ranking:
        chave_secao = item["secao"] or "Sem Seção"
        secoes_map.setdefault(chave_secao, []).append(item)

    secoes = []
    # Loja sem nenhum vendedor com seção cadastrada (ex: "Linda de Bonito") --
    # todo mundo cai em "Sem Seção", o que só duplicaria o total geral numa
    # aba redundante. Nesse caso não devolve seções nenhuma; o app já trata
    # lista vazia mostrando só os totais gerais, sem abas.
    if not (len(secoes_map) == 1 and "Sem Seção" in secoes_map):
        for nome_secao, itens in secoes_map.items():
            total_secao = sum((i["total_vendas"] for i in itens), Decimal("0"))
            qtd_secao = sum(i["quantidade_pedidos"] for i in itens)
            secoes.append({
                "secao": nome_secao,
                "total_vendas": total_secao,
                "quantidade_pedidos": qtd_secao,
                "ticket_medio": (total_secao / qtd_secao) if qtd_secao > 0 else Decimal("0"),
                "ranking_vendedores": sorted(itens, key=lambda i: i["total_vendas"], reverse=True),
            })
        secoes.sort(key=lambda s: s["total_vendas"], reverse=True)

    return {
        "total_vendas": total,
        "quantidade_pedidos": qtd,
        "ticket_medio": ticket,
        "total_vendas_hoje": total_hoje,
        "quantidade_pedidos_hoje": qtd_hoje,
        "ranking_vendedores": ranking,
        "secoes": secoes,
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
    limit: int = 500,
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
    itens_rows = (await db.execute(sql_itens, {
        "pedido_id": pedido_id,
        "vendedor_cabecalho_id": vendedor_cabecalho_id,
    })).all()

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
    limit: int = 500,
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
    itens_rows = (await db.execute(sql_itens, {
        "id": pre_venda_id,
        "vendedor_cabecalho_id": vendedor_cabecalho_id,
    })).all()

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


# ── Devolução de item do condicional (pré-venda) ────────────────────────────────
#
# O ERP, ao efetivar o condicional em venda, simplesmente pega todos os itens
# ainda existentes em marilia.itens_movimentacao_estoque daquela pré-venda —
# não olha nenhum campo de "devolvido". Por isso a devolução aqui precisa
# DELETAR o item de verdade (não só marcar), senão o ERP levaria o item
# devolvido junto pra venda. A FK de itens_movimentacao_estoque_pre_venda pra
# itens_movimentacao_estoque é ON DELETE CASCADE (confirmado em produção),
# então basta apagar a linha do item principal.
#
# (O campo item_devolvido/quantidade_devolvida em itens_movimentacao_estoque_pre_venda
# segue existindo no schema, mas não é usado por esse fluxo — ver histórico do
# módulo pra entender a primeira versão, que usava esse campo, e por que foi
# trocada por esta.)

async def devolver_item_pre_venda(db: AsyncSession, pre_venda_id: int, item_id: int) -> None:
    item = (await db.execute(
        text("""
            SELECT ime.pk_chave, pv.efetivada
            FROM marilia.itens_movimentacao_estoque ime
            JOIN marilia.pre_venda pv
                ON pv."fk_movimentacao_estoque$movimentacao_estoque" = ime."fk_movimentacao_estoque$movimentacao_estoque"
            WHERE ime.pk_chave = :item_id
              AND ime."fk_movimentacao_estoque$movimentacao_estoque" = :pre_venda_id
        """),
        {"item_id": item_id, "pre_venda_id": pre_venda_id},
    )).one_or_none()

    if not item:
        raise NotFoundError("Item da pré-venda", item_id)
    if item.efetivada:
        raise BusinessRuleError("Pré-venda já efetivada — não é possível devolver itens.")

    await db.execute(
        text("DELETE FROM marilia.itens_movimentacao_estoque WHERE pk_chave = :item_id"),
        {"item_id": item_id},
    )
    await db.commit()


async def restaurar_item_pre_venda(
    db: AsyncSession,
    pre_venda_id: int,
    produto_id: int,
    quantidade: Decimal,
    vr_unitario_bruto: Decimal,
    vr_desconto_total: Decimal,
    vr_acrescimo_total: Decimal,
    vendedor_id: int | None,
) -> dict:
    """Desfaz uma devolução recriando o item na pré-venda (o item antigo foi
    deletado de verdade, então isso gera um pk_chave novo — mesma lógica de
    inserção usada em `criar_pre_venda`)."""
    pv = (await db.execute(
        text('SELECT efetivada FROM marilia.pre_venda WHERE "fk_movimentacao_estoque$movimentacao_estoque" = :id'),
        {"id": pre_venda_id},
    )).one_or_none()
    if not pv:
        raise NotFoundError("Pré-venda", pre_venda_id)
    if pv.efetivada:
        raise BusinessRuleError("Pré-venda já efetivada — não é possível restaurar itens.")

    local_estoque = await _obter_local_estoque_padrao(db)

    r_item = await db.execute(
        text("""
            INSERT INTO marilia.itens_movimentacao_estoque
                ("fk_movimentacao_estoque$movimentacao_estoque", "fk_produtos$produto",
                 quantidade, "fk_local_estoque$local",
                 vr_desconto_total, vr_unitario_bruto, vr_acrescimo_total, vr_comissao)
            VALUES
                (:pre_venda_id, :produto_id, :quantidade, :local_estoque,
                 :desconto, :unitario, :acrescimo, 0)
            RETURNING pk_chave
        """),
        {
            "pre_venda_id": pre_venda_id,
            "produto_id": produto_id,
            "quantidade": -abs(quantidade),
            "local_estoque": local_estoque,
            "desconto": vr_desconto_total,
            "unitario": vr_unitario_bruto,
            "acrescimo": vr_acrescimo_total,
        },
    )
    novo_item_id = r_item.scalar_one()

    await db.execute(
        text("""
            INSERT INTO marilia.itens_movimentacao_estoque_pre_venda
                ("fk_itens_movimentacao_estoque$item_movimentacao", "fk_pessoas$vendedor",
                 quantidade_devolvida, item_devolvido)
            VALUES (:item_id, :vendedor_id, 0, false)
        """),
        {"item_id": novo_item_id, "vendedor_id": vendedor_id},
    )
    await db.commit()

    return {
        "pk_chave": novo_item_id,
        "produto_id": produto_id,
        "quantidade": abs(quantidade),
        "vr_unitario_bruto": vr_unitario_bruto,
        "vr_desconto_total": vr_desconto_total,
        "vr_acrescimo_total": vr_acrescimo_total,
        "vendedor_id": vendedor_id,
    }


# ── Criação de Pré-Venda ──────────────────────────────────────────────────────

async def _obter_local_estoque_padrao(db: AsyncSession) -> str:
    """Obtém o local de estoque mais usado em pré-vendas existentes.

    Se não houver nenhuma pré-venda anterior para basear a busca, cai para um
    valor real cadastrado em `cadastros.local_estoque` (preferindo "LOJA",
    que é o local padrão mais comum) — nunca para uma string fixa que pode
    não existir na tabela, o que violaria a FK de
    `itens_movimentacao_estoque."fk_local_estoque$local"` e derrubaria a
    criação da pré-venda com um erro 500.
    """
    result = await db.execute(text("""
        SELECT ime."fk_local_estoque$local"
        FROM marilia.itens_movimentacao_estoque ime
        JOIN marilia.pre_venda pv
            ON pv."fk_movimentacao_estoque$movimentacao_estoque" = ime."fk_movimentacao_estoque$movimentacao_estoque"
        GROUP BY ime."fk_local_estoque$local"
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """))
    row = result.one_or_none()
    if row:
        return row[0]

    fallback = await db.execute(text("""
        SELECT nome FROM cadastros.local_estoque
        ORDER BY (nome = 'LOJA') DESC, nome
        LIMIT 1
    """))
    fallback_row = fallback.one_or_none()
    if not fallback_row:
        raise BusinessRuleError("Nenhum local de estoque cadastrado — não é possível criar a pré-venda.")
    return fallback_row[0]


async def criar_pre_venda(
    db: AsyncSession,
    dados: PreVendaInput,
    usuario_login: str,
) -> dict:
    from datetime import date as date_cls

    data_pv = dados.data or date_cls.today()
    local_estoque = await _obter_local_estoque_padrao(db)

    # 1. Busca nome do cliente
    cliente_nome: str | None = None
    if dados.cliente_id:
        r = await db.execute(
            text("SELECT nome FROM cadastros.pessoas WHERE chave = :chave"),
            {"chave": dados.cliente_id},
        )
        row = r.one_or_none()
        cliente_nome = row[0] if row else None

    # 2. Insere movimentacao_estoque
    # Nota: as colunas "usuario" e "cliente" não existem em todos os bancos de
    # clientes (schema do ERP Delphi varia por instalação) — por isso o usuário
    # que criou a pré-venda e o nome do cliente vão só na observação, nunca em
    # colunas dedicadas. O cliente_id em si continua salvo via
    # "fk_pessoas$pessoa", que é uma coluna universal.
    obs_partes = [f"APLICATIVO ({usuario_login})"]
    if cliente_nome:
        obs_partes.append(f"Cliente: {cliente_nome}")
    if dados.obs:
        obs_partes.append(dados.obs)

    r_mov = await db.execute(
        text("""
            INSERT INTO marilia.movimentacao_estoque
                (data, "fk_pessoas$pessoa", "fk_tipos_movimentacao$tipo_movimento", obs)
            VALUES
                (:data, :cliente_id, :tipo, :obs)
            RETURNING pk_chave
        """),
        {
            "data": data_pv,
            "cliente_id": dados.cliente_id,
            "tipo": TIPO_PRE_VENDA,
            "obs": " - ".join(obs_partes),
        },
    )
    mov_pk = r_mov.scalar_one()

    # 3. Insere pre_venda
    await db.execute(
        text("""
            INSERT INTO marilia.pre_venda
                ("fk_movimentacao_estoque$movimentacao_estoque", "fk_pessoas$vendedor",
                 efetivada, condicao_pagamento, data_entrega)
            VALUES (:mov_pk, :vendedor_id, false, :condicao, :data_entrega)
        """),
        {
            "mov_pk": mov_pk,
            "vendedor_id": dados.vendedor_id,
            "condicao": dados.condicao_pagamento,
            "data_entrega": dados.data_entrega,
        },
    )

    # 4. Insere os itens
    vr_total = Decimal("0")
    for item in dados.itens:
        r_item = await db.execute(
            text("""
                INSERT INTO marilia.itens_movimentacao_estoque
                    ("fk_movimentacao_estoque$movimentacao_estoque", "fk_produtos$produto",
                     quantidade, "fk_local_estoque$local",
                     vr_desconto_total, vr_unitario_bruto, vr_acrescimo_total, vr_comissao)
                VALUES
                    (:mov_pk, :produto_id, :quantidade, :local_estoque,
                     :desconto, :unitario, :acrescimo, 0)
                RETURNING pk_chave
            """),
            {
                "mov_pk": mov_pk,
                "produto_id": item.produto_id,
                "quantidade": -abs(item.quantidade),  # saída: negativo
                "local_estoque": local_estoque,
                "desconto": item.vr_desconto_total,
                "unitario": item.vr_unitario_bruto,
                "acrescimo": item.vr_acrescimo_total,
            },
        )
        item_pk = r_item.scalar_one()

        # Vendedor do item: usa o do item se informado, senão usa o do cabeçalho
        vendedor_item = item.vendedor_id if item.vendedor_id is not None else dados.vendedor_id

        await db.execute(
            text("""
                INSERT INTO marilia.itens_movimentacao_estoque_pre_venda
                    ("fk_itens_movimentacao_estoque$item_movimentacao",
                     "fk_pessoas$vendedor", quantidade_devolvida, item_devolvido)
                VALUES (:item_pk, :vendedor_id, 0, false)
            """),
            {"item_pk": item_pk, "vendedor_id": vendedor_item},
        )

        vr_total += item.quantidade * item.vr_unitario_bruto - item.vr_desconto_total + item.vr_acrescimo_total

    await db.commit()

    # 5. Retorna resumo da pré-venda criada
    return {
        "pk_chave": mov_pk,
        "data": data_pv,
        "cliente_id": dados.cliente_id,
        "cliente_nome": cliente_nome,
        "vendedor_id": dados.vendedor_id,
        "vendedor_nome": None,
        "vr_total": vr_total,
        "quantidade_itens": len(dados.itens),
    }