"""Ações do cliente logado: gerar condicional e ver títulos em aberto.

Nada aqui confia no que o app manda além do id do produto e da quantidade:
preço, estoque, vendedor e cliente vêm do banco / do token.
"""
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BusinessRuleError
from app.schemas.vendas import ItemPreVendaInput, PreVendaInput
from app.services import financeiro_service, vendas_service

ORIGEM = "APLICATIVO CLIENTE"

_FOTO = """EXISTS (SELECT 1 FROM cadastros.imagem_produto i
          WHERE i."fk_produtos$produto" = p.pk_chave AND octet_length(i.imagem) > 0)"""


async def _vendedor_padrao(db: AsyncSession) -> int:
    nome = settings.CLIENTE_VENDEDOR_PADRAO.strip()
    if not nome:
        raise BusinessRuleError("Vendedor padrão não configurado.")
    rows = (await db.execute(text(r"""
        SELECT p.chave FROM cadastros.pessoas p
        WHERE coalesce(p.funcionario, false) AND NOT coalesce(p.inativo, false)
          AND (upper(trim(p.nome)) = upper(:n) OR upper(p.nome) LIKE upper(:n) || ' %')
        LIMIT 3"""), {"n": nome})).all()
    if len(rows) != 1:
        # nenhuma ou várias: melhor recusar do que gravar com o vendedor errado
        raise BusinessRuleError("Não foi possível gerar o condicional agora. Fale com a loja.")
    return rows[0][0]


async def criar_condicional(db: AsyncSession, pessoa_id: int, itens: list[tuple[int, int]]) -> dict:
    """itens = [(produto_id, quantidade)]. Devolve o resumo da pré-venda criada."""
    if not itens:
        raise BusinessRuleError("O carrinho está vazio.")
    # junta repetidos
    qtd: dict[int, int] = {}
    for pid, q in itens:
        if q < 1:
            raise BusinessRuleError("Quantidade inválida.")
        qtd[pid] = qtd.get(pid, 0) + q
    if len(qtd) > settings.CLIENTE_MAX_ITENS_CONDICIONAL or sum(qtd.values()) > settings.CLIENTE_MAX_ITENS_CONDICIONAL:
        raise BusinessRuleError(
            f"Máximo de {settings.CLIENTE_MAX_ITENS_CONDICIONAL} peças por condicional.")

    # Serializa por cliente e por produto: dois pedidos simultâneos não passam do
    # limite nem vendem a mesma última peça (locks soltam no commit).
    await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": 7_000_000_000 + pessoa_id})
    for pid in sorted(qtd):
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": pid})

    abertos = (await db.execute(text("""
        SELECT count(*) FROM marilia.pre_venda pv
        JOIN marilia.movimentacao_estoque m
          ON m.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        WHERE m."fk_pessoas$pessoa" = :p AND NOT coalesce(pv.efetivada, false)
          AND m.data >= current_date - 30"""), {"p": pessoa_id})).scalar()
    if abertos >= settings.CLIENTE_MAX_CONDICIONAIS_ABERTOS:
        raise BusinessRuleError(
            "Você já tem condicional em aberto. Devolva ou finalize na loja para pedir outro.")

    linhas = (await db.execute(text(f"""
        SELECT p.pk_chave, marilia.obter_preco_venda(p.pk_chave) AS preco,
               coalesce((SELECT SUM(saldo) FROM cadastros.v_estoque_atual
                         WHERE "fk_produtos$produto" = p.pk_chave), 0) AS saldo
        FROM cadastros.produtos p
        WHERE p.pk_chave = ANY(:ids) AND NOT coalesce(p.inativo, false) AND {_FOTO}"""),
        {"ids": list(qtd)})).all()
    dados = {r[0]: (Decimal(str(r[1] or 0)), Decimal(str(r[2]))) for r in linhas}

    for pid, q in qtd.items():
        if pid not in dados:
            raise BusinessRuleError("Um dos produtos não está mais disponível. Atualize o carrinho.")
        preco, saldo = dados[pid]
        if preco <= 0:
            raise BusinessRuleError("Um dos produtos não está disponível para pedido.")
        if saldo < q:
            raise BusinessRuleError("Um dos produtos acabou de esgotar. Atualize o carrinho.")

    vendedor = await _vendedor_padrao(db)
    pre = PreVendaInput(
        cliente_id=pessoa_id, vendedor_id=vendedor, obs=ORIGEM,
        itens=[ItemPreVendaInput(produto_id=pid, quantidade=Decimal(q), vr_unitario_bruto=dados[pid][0])
               for pid, q in qtd.items()],
    )
    r = await vendas_service.criar_pre_venda(db, pre, ORIGEM)
    return {"numero": r["pk_chave"], "total": float(r["vr_total"]), "itens": sum(qtd.values())}


async def titulos_em_aberto(db: AsyncSession, pessoa_id: int) -> dict:
    rows = await financeiro_service.listar_financeiro(
        db, "R", pessoa_id=pessoa_id, situacao=financeiro_service.SITUACAO_PENDENTES, limit=200)
    titulos = [
        {"vencimento": t["data_vencimento"], "valor": float(t["valor_original"]),
         "documento": t["documento"], "parcela": t["parcela"], "vencido": t["vencido"]}
        for t in rows
    ]
    return {"total": sum(t["valor"] for t in titulos),
            "total_vencido": sum(t["valor"] for t in titulos if t["vencido"]),
            "titulos": titulos}
