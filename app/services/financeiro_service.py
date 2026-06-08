"""
Serviço financeiro — contas a pagar / pagas.
Pago = existe registro em marilia.titulos_baixa.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SITUACAO_PAGAS = "PAGAS"
SITUACAO_PENDENTES = "NORMAL"


def _build_conditions(
    data_inicio: date | None,
    data_fim: date | None,
    data_baixa_inicio: date | None,
    data_baixa_fim: date | None,
    pessoa_id: int | None,
    plano_contas_id: int | None,
    centro_custos_id: int | None,
    situacao: str | None,
    params: dict,
) -> list[str]:
    conditions = [
        "t.tipo_titulo = 'P'",
        "t.e_haver = false",
        "t.e_cartao = false",
        # Sempre oculta títulos renegociados (como no ERP)
        'NOT EXISTS (SELECT 1 FROM marilia.novos_titulos novi'
        ' WHERE novi."fk_titulos$novo_titulo" = t.pk_chave'
        " AND novi.tipo_titulo IN ('NORMAL', 'PARCIAL'))"
    ]
    if data_inicio:
        conditions.append("t.data_vencimento >= :data_inicio")
        params["data_inicio"] = data_inicio
    if data_fim:
        conditions.append("t.data_vencimento <= :data_fim")
        params["data_fim"] = data_fim
    if data_baixa_inicio:
        conditions.append("b.data >= :data_baixa_inicio")
        params["data_baixa_inicio"] = data_baixa_inicio
    if data_baixa_fim:
        conditions.append("b.data <= :data_baixa_fim")
        params["data_baixa_fim"] = data_baixa_fim
    if pessoa_id:
        conditions.append("t.fk_pessoas__pessoa = :pessoa_id")
        params["pessoa_id"] = pessoa_id
    if plano_contas_id:
        conditions.append("t.fk_plano_contas__plano_contas = :plano_contas_id")        
        params["plano_contas_id"] = plano_contas_id
    if centro_custos_id:
        conditions.append("t.fk_centro_custos__centro_custos = :centro_custos_id")     
        params["centro_custos_id"] = centro_custos_id
    
    if situacao == SITUACAO_PAGAS:
        conditions.append(
            'EXISTS (SELECT 1 FROM marilia.titulos_baixa tbxi'
            ' WHERE tbxi."fk_titulos$chave_titulo" = t.pk_chave)'
        )
    elif situacao == SITUACAO_PENDENTES:
        conditions.append(
            'NOT EXISTS (SELECT 1 FROM marilia.titulos_baixa tbxi'
            ' WHERE tbxi."fk_titulos$chave_titulo" = t.pk_chave)'
        )
    return conditions


async def listar_contas_pagar(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    data_baixa_inicio: date | None = None,
    data_baixa_fim: date | None = None,
    pessoa_id: int | None = None,
    plano_contas_id: int | None = None,
    centro_custos_id: int | None = None,
    situacao: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    params: dict = {"limit": limit, "offset": offset}
    conditions = _build_conditions(
        data_inicio, data_fim, data_baixa_inicio, data_baixa_fim,
        pessoa_id, plano_contas_id, centro_custos_id, situacao, params,
    )
    where = " AND ".join(conditions)
    hoje = date.today()

    # Usamos GROUP BY para evitar duplicação se houver múltiplas baixas
    # Usamos COUNT(*) para verificar se há baixas, já que pk_chave pode não existir na tabela marilia.titulos_baixa
    sql = text(f"""
        SELECT
            t.pk_chave,
            t.data_vencimento,
            t.data_operacao,
            t.valor                                 AS valor_original,
            t.documento,
            t.parcela,
            t.observacoes,
            t."fk_tipo_pagamento$nome"              AS tipo_pagamento,
            t.fk_pessoas__pessoa                    AS pessoa_id,
            p.nome                                  AS pessoa_nome,
            t.fk_plano_contas__plano_contas         AS plano_contas_id,
            pc.nome                                 AS plano_contas_nome,
            t.fk_centro_custos__centro_custos       AS centro_custos_id,
            cc.nome                                 AS centro_custos_nome,
            -- pagamento agrupado
            COUNT(tb.*) > 0                         AS pago,
            MAX(b.data)                             AS data_baixa,
            SUM(COALESCE(tb.juros, 0))               AS juros,
            SUM(COALESCE(tb.multa, 0))               AS multa,
            SUM(COALESCE(tb.adicional, 0))           AS adicional,
            SUM(COALESCE(tb.desconto, 0))            AS desconto
        FROM marilia.titulos t
        LEFT JOIN marilia.contas_pagar cp ON cp."fk_titulos$titulo" = t.pk_chave       
        LEFT JOIN cadastros.pessoas p ON p.chave = t.fk_pessoas__pessoa
        LEFT JOIN cadastros.plano_contas pc ON pc.chave = t.fk_plano_contas__plano_contas
        LEFT JOIN cadastros.centro_custos cc ON cc.chave = t.fk_centro_custos__centro_custos
        LEFT JOIN marilia.titulos_baixa tb ON tb."fk_titulos$chave_titulo" = t.pk_chave
        LEFT JOIN marilia.baixas b ON b.pk_chave = tb."fk_baixas$chave_baixa"
        WHERE {where}
        GROUP BY 
            t.pk_chave, t.data_vencimento, t.data_operacao, t.valor, t.documento, 
            t.parcela, t.observacoes, t."fk_tipo_pagamento$nome", t.fk_pessoas__pessoa, 
            p.nome, t.fk_plano_contas__plano_contas, pc.nome, 
            t.fk_centro_custos__centro_custos, cc.nome
        ORDER BY t.data_vencimento ASC, t.pk_chave ASC
        LIMIT :limit OFFSET :offset
    """)

    rows = (await db.execute(sql, params)).all()
    result = []
    for r in rows:
        pago = bool(r.pago)
        juros = Decimal(str(r.juros or 0))
        multa = Decimal(str(r.multa or 0))
        adicional = Decimal(str(r.adicional or 0))
        desconto = Decimal(str(r.desconto or 0))
        valor_original = Decimal(str(r.valor_original or 0))
        valor_pago = valor_original + juros + multa + adicional - desconto

        result.append({
            "pk_chave": r.pk_chave,
            "data_vencimento": r.data_vencimento,
            "data_operacao": r.data_operacao,
            "valor_original": valor_original,
            "valor_pago": valor_pago if pago else valor_original,
            "documento": r.documento,
            "parcela": r.parcela,
            "observacoes": r.observacoes,
            "tipo_pagamento": r.tipo_pagamento,
            "pago": pago,
            "data_baixa": r.data_baixa,
            "juros": juros,
            "multa": multa,
            "adicional": adicional,
            "desconto": desconto,
            "vencido": not pago and r.data_vencimento < hoje,
            "pessoa_id": r.pessoa_id,
            "pessoa_nome": r.pessoa_nome,
            "plano_contas_id": r.plano_contas_id,
            "plano_contas_nome": r.plano_contas_nome,
            "centro_custos_id": r.centro_custos_id,
            "centro_custos_nome": r.centro_custos_nome,
        })
    return result


async def resumo_contas_pagar(
    db: AsyncSession,
    data_inicio: date | None,
    data_fim: date | None,
    data_baixa_inicio: date | None,
    data_baixa_fim: date | None,
    pessoa_id: int | None,
    plano_contas_id: int | None,
    centro_custos_id: int | None,
    situacao: str | None,
) -> dict:
    hoje = date.today()
    params: dict = {"hoje": hoje}
    base_conditions = _build_conditions(
        data_inicio, data_fim, data_baixa_inicio, data_baixa_fim,
        pessoa_id, plano_contas_id, centro_custos_id, situacao, params,
    )
    where = " AND ".join(base_conditions)

    extra_joins = ""
    if data_baixa_inicio or data_baixa_fim:
        extra_joins = (
            'LEFT JOIN marilia.titulos_baixa tb ON tb."fk_titulos$chave_titulo" = t.pk_chave '
            'LEFT JOIN marilia.baixas b ON b.pk_chave = tb."fk_baixas$chave_baixa"'
        )

    sql = text(f"""
        SELECT
            COUNT(*) FILTER (WHERE NOT pago) AS titulos_pendentes,
            COUNT(*) FILTER (WHERE pago) AS titulos_pagos,
            COALESCE(SUM(valor_original) FILTER (WHERE NOT pago AND data_vencimento < :hoje), 0) AS total_vencido,
            COALESCE(SUM(valor_original) FILTER (WHERE NOT pago AND data_vencimento >= :hoje), 0) AS total_a_vencer,
            COALESCE(SUM(valor_pago) FILTER (WHERE pago), 0) AS total_pago,
            COALESCE(SUM(juros_multa) FILTER (WHERE pago), 0) AS total_juros_multa,
            COALESCE(SUM(desconto) FILTER (WHERE pago), 0) AS total_desconto
        FROM (
            SELECT
                t.pk_chave,
                t.data_vencimento,
                t.valor AS valor_original,
                EXISTS (SELECT 1 FROM marilia.titulos_baixa tbxi WHERE tbxi."fk_titulos$chave_titulo" = t.pk_chave) AS pago,
                COALESCE((
                    SELECT SUM(tbi.valor + tbi.juros + tbi.multa + tbi.adicional - tbi.desconto)
                    FROM marilia.titulos_baixa tbi WHERE tbi."fk_titulos$chave_titulo" = t.pk_chave
                ), 0) AS valor_pago,
                COALESCE((
                    SELECT SUM(tbi.juros + tbi.multa)
                    FROM marilia.titulos_baixa tbi WHERE tbi."fk_titulos$chave_titulo" = t.pk_chave
                ), 0) AS juros_multa,
                COALESCE((
                    SELECT SUM(tbi.desconto)
                    FROM marilia.titulos_baixa tbi WHERE tbi."fk_titulos$chave_titulo" = t.pk_chave
                ), 0) AS desconto
            FROM marilia.titulos t
            {extra_joins}
            WHERE {where}
            GROUP BY t.pk_chave, t.data_vencimento, t.valor
        ) AS sub
    """)

    r = (await db.execute(sql, params)).one()
    vencido = Decimal(str(r.total_vencido or 0))
    a_vencer = Decimal(str(r.total_a_vencer or 0))
    return {
        "titulos_pendentes": int(r.titulos_pendentes or 0),
        "titulos_pagos": int(r.titulos_pagos or 0),
        "total_vencido": vencido,
        "total_a_vencer": a_vencer,
        "total": vencido + a_vencer,
        "total_pago": Decimal(str(r.total_pago or 0)),
        "total_juros_multa": Decimal(str(r.total_juros_multa or 0)),
        "total_desconto": Decimal(str(r.total_desconto or 0)),
    }


async def listar_fornecedores(db: AsyncSession) -> list[dict]:
    sql = text("""
        SELECT DISTINCT p.chave, p.nome
        FROM cadastros.pessoas p
        JOIN marilia.titulos t ON t.fk_pessoas__pessoa = p.chave
        WHERE t.tipo_titulo = 'P' AND p.inativo = false
        ORDER BY p.nome
    """)
    rows = (await db.execute(sql)).all()
    return [{"pk_chave": r.chave, "nome": r.nome} for r in rows]


async def listar_planos_contas(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(text("SELECT chave, nome FROM cadastros.plano_contas ORDER BY nome"))).all()
    return [{"pk_chave": r.chave, "nome": r.nome} for r in rows]


async def listar_centros_custos(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(text("SELECT chave, nome FROM cadastros.centro_custos ORDER BY nome"))).all()
    return [{"pk_chave": r.chave, "nome": r.nome} for r in rows]