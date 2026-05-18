from decimal import Decimal
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _valor_item_sql() -> str:
    """Fórmula do valor líquido de um item — ABS para garantir valores positivos."""
    return "(ABS(ime.quantidade) * ime.vr_unitario_bruto) - ime.vr_desconto_total + ime.vr_acrescimo_total"


def _base_joins() -> str:
    return """
        FROM marilia.itens_movimentacao_estoque ime
        JOIN marilia.itens_movimentacao_estoque_pedido_venda impv
            ON impv."fk_itens_movimentacao_estoque$item_movimentacao" = ime.pk_chave
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = ime."fk_movimentacao_estoque$movimentacao_estoque"
        JOIN marilia.pedido_venda pv
            ON pv."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
        JOIN cadastros.produtos p
            ON p.pk_chave = ime."fk_produtos$produto"
    """


def _filtros_where(
    data_inicio: date | None,
    data_fim: date | None,
    vendedor_id: int | None,
    marca: str | None,
    divisao: str | None,
    colecao: str | None,
    params: dict,
) -> str:
    clausulas = ["impv.item_devolvido = false"]

    if data_inicio:
        clausulas.append("me.data >= :data_inicio")
        params["data_inicio"] = data_inicio

    if data_fim:
        clausulas.append("me.data <= :data_fim")
        params["data_fim"] = data_fim

    if vendedor_id:
        clausulas.append(
            """COALESCE(impv."fk_pessoas$vendedor", pv."fk_pessoas$vendedor") = :vendedor_id"""
        )
        params["vendedor_id"] = vendedor_id

    if marca:
        clausulas.append('p."fk_marcas$marca" = :marca')
        params["marca"] = marca

    if divisao:
        clausulas.append('p."fk_divisoes$divisao" = :divisao')
        params["divisao"] = divisao

    if colecao:
        clausulas.append("p.colecao = :colecao")
        params["colecao"] = colecao

    return "WHERE " + " AND ".join(clausulas)


async def get_curva_abc(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    vendedor_id: int | None = None,
    marca: str | None = None,
    divisao: str | None = None,
    colecao: str | None = None,
    limit: int = 200,
) -> list[dict]:
    params: dict = {"limit": limit}
    where = _filtros_where(data_inicio, data_fim, vendedor_id, marca, divisao, colecao, params)

    sql = f"""
        WITH vendas AS (
            SELECT
                p.pk_chave AS produto_id,
                p.nome AS produto_nome,
                SUM({_valor_item_sql()}) AS total_vendido,
                SUM(ABS(ime.quantidade)) AS quantidade_vendida,
                COUNT(DISTINCT me.pk_chave) AS quantidade_pedidos
            {_base_joins()}
            {where}
            GROUP BY p.pk_chave, p.nome
            ORDER BY total_vendido DESC
            LIMIT :limit
        ),
        total AS (
            SELECT SUM(total_vendido) AS grand_total FROM vendas
        ),
        acumulado AS (
            SELECT
                v.*,
                t.grand_total,
                SUM(v.total_vendido) OVER (ORDER BY v.total_vendido DESC) AS acumulado,
                ROUND(100.0 * v.total_vendido / NULLIF(t.grand_total, 0), 2) AS pct_individual,
                ROUND(100.0 * SUM(v.total_vendido) OVER (ORDER BY v.total_vendido DESC) / NULLIF(t.grand_total, 0), 2) AS pct_acumulado
            FROM vendas v, total t
        )
        SELECT
            produto_id,
            produto_nome,
            total_vendido,
            quantidade_vendida,
            quantidade_pedidos,
            pct_individual,
            pct_acumulado,
            CASE
                WHEN pct_acumulado <= 80 THEN 'A'
                WHEN pct_acumulado <= 95 THEN 'B'
                ELSE 'C'
            END AS curva
        FROM acumulado
        ORDER BY total_vendido DESC
    """

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    return [
        {
            "produto_id": r[0],
            "produto_nome": r[1],
            "total_vendido": Decimal(str(r[2])) if r[2] else Decimal("0"),
            "quantidade_vendida": Decimal(str(r[3])) if r[3] else Decimal("0"),
            "quantidade_pedidos": r[4] or 0,
            "pct_individual": Decimal(str(r[5])) if r[5] else Decimal("0"),
            "pct_acumulado": Decimal(str(r[6])) if r[6] else Decimal("0"),
            "curva": r[7],
        }
        for r in rows
    ]


async def get_vendas_por_marca(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    vendedor_id: int | None = None,
    divisao: str | None = None,
    colecao: str | None = None,
) -> list[dict]:
    # ✅ Usa função oficial do ERP para consistência
    sql = text("""
        SELECT rel.nome, rel.valor_venda, rel.valor_lucro, rel.lucratividade
        FROM marilia.relatorio_vendas_por_marca(:data_inicio, :data_fim) AS rel
        WHERE rel.valor_venda != 0
        ORDER BY rel.valor_venda DESC
    """)

    params = {
        "data_inicio": data_inicio or date(2000, 1, 1),
        "data_fim": data_fim or date.today(),
    }

    result = await db.execute(sql, params)
    rows = result.fetchall()
    total = sum(Decimal(str(r[1])) for r in rows if r[1] and Decimal(str(r[1])) > 0)

    return [
        {
            "marca_codigo": r[0],
            "marca_nome": r[0] or "Sem marca",
            "total_vendido": Decimal(str(r[1])) if r[1] else Decimal("0"),
            "quantidade_vendida": Decimal("0"),
            "quantidade_pedidos": 0,
            "pct": round(float(Decimal(str(r[1])) / total * 100), 2) if total > 0 and r[1] and Decimal(str(r[1])) > 0 else 0.0,
        }
        for r in rows
        if r[1] and Decimal(str(r[1])) > 0  # filtra marcas com venda positiva
    ]


async def get_vendas_por_divisao(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    vendedor_id: int | None = None,
    marca: str | None = None,
    colecao: str | None = None,
) -> list[dict]:
    # ✅ Usa função oficial do ERP — passa '' para trazer todas as divisões
    sql = text("""
        SELECT rel.nome, rel.valor_venda, rel.valor_lucro, rel.lucratividade, rel.quantidade
        FROM marilia.relatorio_vendas_por_divisao(:data_inicio, :data_fim, :divisao) AS rel
        WHERE rel.valor_venda != 0
        ORDER BY rel.valor_venda DESC
    """)

    params = {
        "data_inicio": data_inicio or date(2000, 1, 1),
        "data_fim": data_fim or date.today(),
        "divisao": "",  # '' = todas as divisões
    }

    result = await db.execute(sql, params)
    rows = result.fetchall()
    total = sum(Decimal(str(r[1])) for r in rows if r[1] and Decimal(str(r[1])) > 0)

    return [
        {
            "divisao_codigo": r[0],
            "divisao_nome": r[0] or "Sem divisão",
            "total_vendido": Decimal(str(r[1])) if r[1] else Decimal("0"),
            "quantidade_vendida": Decimal(str(r[4])) if len(r) > 4 and r[4] else Decimal("0"),
            "quantidade_pedidos": 0,
            "pct": round(float(Decimal(str(r[1])) / total * 100), 2) if total > 0 and r[1] and Decimal(str(r[1])) > 0 else 0.0,
        }
        for r in rows
        if r[1] and Decimal(str(r[1])) > 0
    ]


async def get_vendas_por_colecao(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    vendedor_id: int | None = None,
    marca: str | None = None,
    divisao: str | None = None,
) -> list[dict]:
    params: dict = {}
    where = _filtros_where(data_inicio, data_fim, vendedor_id, marca, divisao, None, params)

    sql = f"""
        SELECT
            -- ✅ trata string vazia como NULL
            COALESCE(NULLIF(TRIM(p.colecao), ''), 'Sem coleção') AS colecao,
            SUM({_valor_item_sql()}) AS total_vendido,
            SUM(ABS(ime.quantidade)) AS quantidade_vendida,
            COUNT(DISTINCT me.pk_chave) AS quantidade_pedidos
        {_base_joins()}
        {where}
        GROUP BY COALESCE(NULLIF(TRIM(p.colecao), ''), 'Sem coleção')
        ORDER BY total_vendido DESC
    """

    result = await db.execute(text(sql), params)
    rows = result.fetchall()
    total = sum(Decimal(str(r[1])) for r in rows if r[1] and Decimal(str(r[1])) > 0)

    return [
        {
            "colecao": r[0],
            "total_vendido": Decimal(str(r[1])) if r[1] else Decimal("0"),
            "quantidade_vendida": Decimal(str(r[2])) if r[2] else Decimal("0"),
            "quantidade_pedidos": r[3] or 0,
            "pct": round(float(Decimal(str(r[1])) / total * 100), 2) if total > 0 and r[1] else 0.0,
        }
        for r in rows
    ]


async def get_vendas_por_genero(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    vendedor_id: int | None = None,
    marca: str | None = None,
    divisao: str | None = None,
    colecao: str | None = None,
) -> list[dict]:
    params: dict = {}
    where = _filtros_where(data_inicio, data_fim, vendedor_id, marca, divisao, colecao, params)

    sql = f"""
        SELECT
            -- ✅ trata string vazia como NULL
            COALESCE(NULLIF(TRIM(p.genero), ''), 'Sem gênero') AS genero,
            SUM({_valor_item_sql()}) AS total_vendido,
            SUM(ABS(ime.quantidade)) AS quantidade_vendida,
            COUNT(DISTINCT me.pk_chave) AS quantidade_pedidos
        {_base_joins()}
        {where}
        GROUP BY COALESCE(NULLIF(TRIM(p.genero), ''), 'Sem gênero')
        ORDER BY total_vendido DESC
    """

    result = await db.execute(text(sql), params)
    rows = result.fetchall()
    total = sum(Decimal(str(r[1])) for r in rows if r[1] and Decimal(str(r[1])) > 0)

    return [
        {
            "genero": r[0],
            "total_vendido": Decimal(str(r[1])) if r[1] else Decimal("0"),
            "quantidade_vendida": Decimal(str(r[2])) if r[2] else Decimal("0"),
            "quantidade_pedidos": r[3] or 0,
            "pct": round(float(Decimal(str(r[1])) / total * 100), 2) if total > 0 and r[1] else 0.0,
        }
        for r in rows
    ]


async def get_filtros_disponiveis(db: AsyncSession) -> dict:
    marcas = await db.execute(text("SELECT nome FROM cadastros.marcas WHERE nome IS NOT NULL AND TRIM(nome) != '' ORDER BY nome"))
    divisoes = await db.execute(text("SELECT codigo, nome FROM cadastros.divisoes WHERE nome IS NOT NULL ORDER BY nome"))
    colecoes = await db.execute(text(
        "SELECT DISTINCT TRIM(colecao) FROM cadastros.produtos WHERE colecao IS NOT NULL AND TRIM(colecao) != '' ORDER BY 1"
    ))

    return {
        "marcas": [r[0] for r in marcas.fetchall()],
        "divisoes": [{"codigo": r[0], "nome": r[1]} for r in divisoes.fetchall()],
        "colecoes": [r[0] for r in colecoes.fetchall()],
    }