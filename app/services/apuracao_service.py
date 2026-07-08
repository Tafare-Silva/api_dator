"""
Serviço de apuração de resultados — agregações de despesas/receitas por
plano de contas e centro de custos, DRE simplificado e comparação
"vendido x recebido".

Duas bases de cálculo, conforme o filtro usado:

- Por competência (data_vencimento): usa marilia.titulos diretamente, reaproveitando
  `_build_conditions` de financeiro_service — reflete o que foi lançado/devido no
  período.

- Por caixa (data_baixa): usa marilia.novos_titulos + marilia.baixas + marilia.titulos,
  espelhando a consulta que o próprio ERP usa para relatórios de recebimento/pagamento
  efetivo (confirmado via SQL Monitor do ERP contra dados reais: soma `tit.valor` do
  "novo_titulo" resultante de cada baixa, excluindo os registros com
  `novos_titulos.tipo_titulo = 'DIFERENCA EM ABERTO'`, que representam saldo ainda em
  aberto, não dinheiro efetivamente recebido/pago). Somar direto de `titulos_baixa`
  (como uma primeira versão deste arquivo fazia) SUPERESTIMA o valor recebido, pois
  conta o saldo em aberto de pagamentos parciais como se already tivesse entrado no
  caixa.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.financeiro_service import _build_conditions
from app.services.vendas_service import TIPO_VENDA

CAMPO_TABELAS = {
    "plano_contas": ("cadastros.plano_contas", "fk_plano_contas__plano_contas"),
    "centro_custos": ("cadastros.centro_custos", "fk_centro_custos__centro_custos"),
}


# ── Base de caixa (data_baixa) — espelha a query real do ERP ───────────────────

def _condicoes_caixa(
    tipo_titulo: str,
    data_baixa_inicio: date | None,
    data_baixa_fim: date | None,
    plano_contas_id: int | None,
    centro_custos_id: int | None,
    params: dict,
) -> list[str]:
    conditions = [
        "tit.tipo_titulo = :tipo_titulo",
        "novos.tipo_titulo NOT ILIKE 'DIFERENCA EM ABERTO'",
    ]
    params["tipo_titulo"] = tipo_titulo
    if data_baixa_inicio:
        conditions.append("bai.data >= :data_baixa_inicio")
        params["data_baixa_inicio"] = data_baixa_inicio
    if data_baixa_fim:
        conditions.append("bai.data <= :data_baixa_fim")
        params["data_baixa_fim"] = data_baixa_fim
    if plano_contas_id:
        conditions.append("tit.fk_plano_contas__plano_contas = :plano_contas_id")
        params["plano_contas_id"] = plano_contas_id
    if centro_custos_id:
        conditions.append("tit.fk_centro_custos__centro_custos = :centro_custos_id")
        params["centro_custos_id"] = centro_custos_id
    return conditions


async def _totalizar_caixa(
    db: AsyncSession,
    tipo_titulo: str,
    data_baixa_inicio: date | None,
    data_baixa_fim: date | None,
    plano_contas_id: int | None = None,
    centro_custos_id: int | None = None,
) -> tuple[Decimal, int]:
    params: dict = {}
    where = " AND ".join(_condicoes_caixa(
        tipo_titulo, data_baixa_inicio, data_baixa_fim, plano_contas_id, centro_custos_id, params,
    ))
    sql = text(f"""
        SELECT COALESCE(SUM(tit.valor), 0) AS total, COUNT(*) AS quantidade
        FROM marilia.novos_titulos novos
        JOIN marilia.baixas bai ON bai.pk_chave = novos."fk_baixas$baixa_origem"
        JOIN marilia.titulos tit ON tit.pk_chave = novos."fk_titulos$novo_titulo"
        WHERE {where}
    """)
    r = (await db.execute(sql, params)).one()
    return Decimal(str(r.total or 0)), int(r.quantidade or 0)


async def _agrupar_por_categoria_caixa(
    db: AsyncSession,
    tipo_titulo: str,
    campo: str,
    data_baixa_inicio: date | None,
    data_baixa_fim: date | None,
    plano_contas_id: int | None = None,
    centro_custos_id: int | None = None,
) -> list[dict]:
    tabela, fk_coluna = CAMPO_TABELAS[campo]
    params: dict = {}
    where = " AND ".join(_condicoes_caixa(
        tipo_titulo, data_baixa_inicio, data_baixa_fim, plano_contas_id, centro_custos_id, params,
    ))
    sql = text(f"""
        SELECT
            cat.chave AS categoria_id,
            cat.nome AS categoria_nome,
            cat.codigo AS categoria_codigo,
            COUNT(*) AS quantidade_titulos,
            COALESCE(SUM(tit.valor), 0) AS total
        FROM marilia.novos_titulos novos
        JOIN marilia.baixas bai ON bai.pk_chave = novos."fk_baixas$baixa_origem"
        JOIN marilia.titulos tit ON tit.pk_chave = novos."fk_titulos$novo_titulo"
        JOIN {tabela} cat ON cat.chave = tit.{fk_coluna}
        WHERE {where}
        GROUP BY cat.chave, cat.nome, cat.codigo
        ORDER BY total DESC
    """)
    rows = (await db.execute(sql, params)).all()
    return [
        {
            "id": r.categoria_id,
            "nome": r.categoria_nome,
            "codigo": r.categoria_codigo,
            "quantidade_titulos": int(r.quantidade_titulos or 0),
            "total": Decimal(str(r.total or 0)),
        }
        for r in rows
    ]


# ── Base de competência (data_vencimento) ───────────────────────────────────────

async def _agrupar_por_categoria(
    db: AsyncSession,
    tipo_titulo: str,
    campo: str,
    data_inicio: date | None,
    data_fim: date | None,
    data_baixa_inicio: date | None,
    data_baixa_fim: date | None,
    situacao: str | None,
    plano_contas_id: int | None = None,
    centro_custos_id: int | None = None,
) -> list[dict]:
    if data_baixa_inicio or data_baixa_fim:
        return await _agrupar_por_categoria_caixa(
            db, tipo_titulo, campo, data_baixa_inicio, data_baixa_fim,
            plano_contas_id=plano_contas_id, centro_custos_id=centro_custos_id,
        )

    tabela, fk_coluna = CAMPO_TABELAS[campo]

    params: dict = {}
    conditions = _build_conditions(
        tipo_titulo, data_inicio, data_fim, None, None,
        None, plano_contas_id, centro_custos_id, situacao, params,
    )
    where = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            categoria_id,
            categoria_nome,
            categoria_codigo,
            COUNT(*) AS quantidade_titulos,
            COALESCE(SUM(CASE WHEN pago THEN valor_pago ELSE valor_original END), 0) AS total
        FROM (
            SELECT
                t.pk_chave,
                cat.chave AS categoria_id,
                cat.nome AS categoria_nome,
                cat.codigo AS categoria_codigo,
                t.valor AS valor_original,
                EXISTS (
                    SELECT 1 FROM marilia.titulos_baixa tbxi
                    WHERE tbxi."fk_titulos$chave_titulo" = t.pk_chave
                ) AS pago,
                t.valor + COALESCE((
                    SELECT SUM(tbi.juros + tbi.multa + tbi.adicional - tbi.desconto)
                    FROM marilia.titulos_baixa tbi WHERE tbi."fk_titulos$chave_titulo" = t.pk_chave
                ), 0) AS valor_pago
            FROM marilia.titulos t
            JOIN {tabela} cat ON cat.chave = t.{fk_coluna}
            WHERE {where}
            GROUP BY t.pk_chave, cat.chave, cat.nome, cat.codigo, t.valor
        ) sub
        GROUP BY categoria_id, categoria_nome, categoria_codigo
        ORDER BY total DESC
    """)

    rows = (await db.execute(sql, params)).all()
    return [
        {
            "id": r.categoria_id,
            "nome": r.categoria_nome,
            "codigo": r.categoria_codigo,
            "quantidade_titulos": int(r.quantidade_titulos or 0),
            "total": Decimal(str(r.total or 0)),
        }
        for r in rows
    ]


async def despesas_por_plano_contas(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    data_baixa_inicio: date | None = None,
    data_baixa_fim: date | None = None,
    situacao: str | None = None,
    centro_custos_id: int | None = None,
) -> list[dict]:
    return await _agrupar_por_categoria(
        db, "P", "plano_contas", data_inicio, data_fim, data_baixa_inicio, data_baixa_fim,
        situacao, centro_custos_id=centro_custos_id,
    )


async def despesas_por_centro_custo(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    data_baixa_inicio: date | None = None,
    data_baixa_fim: date | None = None,
    situacao: str | None = None,
    plano_contas_id: int | None = None,
) -> list[dict]:
    return await _agrupar_por_categoria(
        db, "P", "centro_custos", data_inicio, data_fim, data_baixa_inicio, data_baixa_fim,
        situacao, plano_contas_id=plano_contas_id,
    )


async def receitas_por_plano_contas(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    data_baixa_inicio: date | None = None,
    data_baixa_fim: date | None = None,
    situacao: str | None = None,
    centro_custos_id: int | None = None,
) -> list[dict]:
    return await _agrupar_por_categoria(
        db, "R", "plano_contas", data_inicio, data_fim, data_baixa_inicio, data_baixa_fim,
        situacao, centro_custos_id=centro_custos_id,
    )


async def _totalizar(
    db: AsyncSession,
    tipo_titulo: str,
    data_inicio: date | None,
    data_fim: date | None,
    data_baixa_inicio: date | None,
    data_baixa_fim: date | None,
    situacao: str | None,
) -> tuple[Decimal, int]:
    if data_baixa_inicio or data_baixa_fim:
        return await _totalizar_caixa(db, tipo_titulo, data_baixa_inicio, data_baixa_fim)

    params: dict = {}
    conditions = _build_conditions(
        tipo_titulo, data_inicio, data_fim, None, None,
        None, None, None, situacao, params,
    )
    where = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            COUNT(*) AS quantidade,
            COALESCE(SUM(CASE WHEN pago THEN valor_pago ELSE valor_original END), 0) AS total
        FROM (
            SELECT
                t.pk_chave,
                t.valor AS valor_original,
                EXISTS (
                    SELECT 1 FROM marilia.titulos_baixa tbxi
                    WHERE tbxi."fk_titulos$chave_titulo" = t.pk_chave
                ) AS pago,
                t.valor + COALESCE((
                    SELECT SUM(tbi.juros + tbi.multa + tbi.adicional - tbi.desconto)
                    FROM marilia.titulos_baixa tbi WHERE tbi."fk_titulos$chave_titulo" = t.pk_chave
                ), 0) AS valor_pago
            FROM marilia.titulos t
            WHERE {where}
            GROUP BY t.pk_chave, t.valor
        ) sub
    """)

    r = (await db.execute(sql, params)).one()
    return Decimal(str(r.total or 0)), int(r.quantidade or 0)


async def apuracao_resultado(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    data_baixa_inicio: date | None = None,
    data_baixa_fim: date | None = None,
    situacao: str | None = None,
) -> dict:
    total_despesas, qtd_despesas = await _totalizar(
        db, "P", data_inicio, data_fim, data_baixa_inicio, data_baixa_fim, situacao,
    )
    total_receitas, qtd_receitas = await _totalizar(
        db, "R", data_inicio, data_fim, data_baixa_inicio, data_baixa_fim, situacao,
    )
    return {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "total_despesas": total_despesas,
        "quantidade_despesas": qtd_despesas,
        "total_receitas": total_receitas,
        "quantidade_receitas": qtd_receitas,
        "saldo": total_receitas - total_despesas,
    }


async def vendido_vs_recebido(
    db: AsyncSession,
    data_inicio: date,
    data_fim: date,
) -> dict:
    sql_vendido = text("""
        SELECT COALESCE(SUM(
            (SELECT COALESCE(SUM(
                ABS(ime.quantidade) * ime.vr_unitario_bruto
                - ime.vr_desconto_total
                + ime.vr_acrescimo_total
            ), 0)
            FROM marilia.itens_movimentacao_estoque ime
            WHERE ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave)
        ), 0) AS total_vendido,
        COUNT(*) AS quantidade_vendas
        FROM marilia.pedido_venda pv
        JOIN marilia.movimentacao_estoque me
            ON me.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        WHERE me."fk_tipos_movimentacao$tipo_movimento" = :tipo_venda
          AND me.data BETWEEN :data_inicio AND :data_fim
    """)

    r_vendido = (await db.execute(
        sql_vendido, {"tipo_venda": TIPO_VENDA, "data_inicio": data_inicio, "data_fim": data_fim},
    )).one()
    total_vendido = Decimal(str(r_vendido.total_vendido or 0))

    total_recebido, quantidade_recebimentos = await _totalizar_caixa(db, "R", data_inicio, data_fim)

    return {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "total_vendido": total_vendido,
        "total_recebido": total_recebido,
        "diferenca": total_vendido - total_recebido,
        "quantidade_vendas": int(r_vendido.quantidade_vendas or 0),
        "quantidade_recebimentos": quantidade_recebimentos,
    }
