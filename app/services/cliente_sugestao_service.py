"""Sacola sugerida para a cliente logada.

Aprende o perfil só com o que ela JÁ COMPROU (vendas efetivadas, sem itens
devolvidos) e pontua as peças disponíveis (ativas, com foto e saldo) pela
semelhança: tamanho, categoria, gênero, coleção e faixa de preço. Compras
recentes pesam mais. Não reserva estoque: só sugere; o condicional só nasce
quando a cliente confirma, pelo fluxo normal.

As regras são simples de propósito, para explicar cada sugestão ("você costuma
levar tamanho M e Blusas") e dar para trocar por algo mais esperto depois sem
mexer no app: o contrato é {"resumo", "itens"}.
"""
import math
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.cliente_catalogo_service import _ESTOQUE, _FOTO_PRINCIPAL, _norm, _tem_dt_cadastro
from app.services.vendas_service import TIPO_VENDA

PECAS_SUGESTAO = 6          # tamanho da sacola sugerida (respeita o limite do condicional)
MESES_HISTORICO = 24
MEIA_VIDA_DIAS = 180        # uma compra de 6 meses atrás pesa metade de uma de hoje
MAX_CANDIDATOS = 600

# (atributo, peso na pontuação)
_ATRIBUTOS = (("tamanho", 3.0), ("divisao", 2.0), ("genero", 1.5), ("colecao", 1.0))


def _k(v) -> str | None:
    v = (str(v) if v is not None else "").strip().upper()
    return v or None


def _dias(d, hoje: date) -> int:
    if isinstance(d, datetime):
        d = d.date()
    return max((hoje - d).days, 0) if isinstance(d, date) else 0


def montar_perfil(compras: list[dict], hoje: date) -> dict:
    """compras: [{produto_id, tamanho, divisao, genero, colecao, quantidade, preco, data}]"""
    pesos: dict[str, dict[str, float]] = {a: {} for a, _ in _ATRIBUTOS}
    precos: list[float] = []
    comprados: set[int] = set()
    for c in compras:
        w = float(c.get("quantidade") or 1) * 0.5 ** (_dias(c["data"], hoje) / MEIA_VIDA_DIAS)
        for a, _ in _ATRIBUTOS:
            if (v := _k(c.get(a))) is not None:
                pesos[a][v] = pesos[a].get(v, 0.0) + w
        if (p := float(c.get("preco") or 0)) > 0:
            precos.append(p)
        comprados.add(c["produto_id"])
    faixa = None
    if precos:
        precos.sort()
        p25 = precos[int(0.25 * (len(precos) - 1))]
        p75 = precos[int(0.75 * (len(precos) - 1))]
        faixa = (p25 * 0.75, p75 * 1.25)
    return {"pesos": pesos, "faixa": faixa, "comprados": comprados, "total": len(compras)}


def pontuar(perfil: dict, cand: dict) -> tuple[float, dict[str, str]]:
    """Nota da peça para este perfil + os atributos que casaram (para explicar)."""
    nota = 0.0
    casou: dict[str, str] = {}
    for a, peso in _ATRIBUTOS:
        pesos = perfil["pesos"][a]
        v = _k(cand.get(a))
        if pesos and v in pesos:
            afin = pesos[v] / max(pesos.values())
            nota += peso * afin
            if afin >= 0.5:
                casou[a] = v
    preco = float(cand.get("preco") or 0)
    if perfil["faixa"]:
        lo, hi = perfil["faixa"]
        if lo <= preco <= hi:
            nota += 1.0
        elif preco > hi:
            nota -= min(1.5, (preco - hi) / hi)  # bem mais caro que o habitual
    if cand.get("novo"):
        nota += 0.7
    return nota, casou


def _motivo(casou: dict[str, str], cand: dict) -> str:
    partes = []
    if "tamanho" in casou:
        partes.append(f"tamanho {cand.get('tamanho', '').strip()}")
    if "divisao" in casou:
        partes.append(str(cand.get("divisao") or "").strip().capitalize())
    if partes:
        return "Você costuma levar " + " e ".join(partes)
    return "Combina com o seu estilo"


def escolher(perfil: dict, candidatos: list[dict], limite: int) -> list[dict]:
    """Melhores peças ainda não compradas, com variedade (não enche a sacola de uma categoria)."""
    pontuados = []
    for c in candidatos:
        if c["id"] in perfil["comprados"]:
            continue
        nota, casou = pontuar(perfil, c)
        if nota > 0 and casou:  # sem nenhum atributo em comum não é sugestão, é chute
            pontuados.append((nota, c, casou))
    pontuados.sort(key=lambda t: (-t[0], t[1]["id"]))
    teto_categoria = max(2, math.ceil(limite * 0.6))
    por_categoria: dict[str | None, int] = {}
    saida = []
    for nota, c, casou in pontuados:
        cat = _k(c.get("divisao"))
        if por_categoria.get(cat, 0) >= teto_categoria:
            continue
        por_categoria[cat] = por_categoria.get(cat, 0) + 1
        saida.append({**{k: v for k, v in c.items() if k != "novo"}, "motivo": _motivo(casou, c)})
        if len(saida) >= limite:
            break
    return saida


def _resumo(perfil: dict) -> str | None:
    def topo(a: str, n: int) -> list[str]:
        return [k.capitalize() if a == "divisao" else k
                for k, _ in sorted(perfil["pesos"][a].items(), key=lambda kv: -kv[1])[:n]]
    partes = []
    if t := topo("tamanho", 1):
        partes.append(f"tamanho {t[0]}")
    partes += topo("divisao", 2)
    return ("Pensado no seu estilo: " + ", ".join(partes)) if partes else None


async def _compras(db: AsyncSession, pessoa_id: int) -> list[dict]:
    rows = (await db.execute(text(f"""
        SELECT ime."fk_produtos$produto" AS produto_id, p.tamanho, p.genero, p.colecao,
               trim(p."fk_divisoes$divisao") AS divisao, abs(ime.quantidade) AS quantidade,
               ime.vr_unitario_bruto AS preco, me.data
        FROM marilia.movimentacao_estoque me
        JOIN marilia.pedido_venda pv ON pv."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
        JOIN marilia.itens_movimentacao_estoque ime
          ON ime."fk_movimentacao_estoque$movimentacao_estoque" = me.pk_chave
        JOIN cadastros.produtos p ON p.pk_chave = ime."fk_produtos$produto"
        LEFT JOIN marilia.itens_movimentacao_estoque_pedido_venda impv
          ON impv."fk_itens_movimentacao_estoque$item_movimentacao" = ime.pk_chave
        WHERE me."fk_pessoas$pessoa" = :p AND me."fk_tipos_movimentacao$tipo_movimento" = :tipo
          AND me.data >= current_date - {MESES_HISTORICO * 30}
          AND NOT coalesce(impv.item_devolvido, false)
        ORDER BY me.data DESC
        LIMIT 400"""), {"p": pessoa_id, "tipo": TIPO_VENDA})).mappings().all()
    return [dict(r) for r in rows]


async def _candidatos(db: AsyncSession, perfil: dict) -> list[dict]:
    novo = "coalesce(p.data_cadastramento >= current_date - 30, false)" if await _tem_dt_cadastro(db) else "false"
    tams = list(perfil["pesos"]["tamanho"])
    divs = list(perfil["pesos"]["divisao"])
    # só peças que têm ao menos tamanho ou categoria em comum (corta o trabalho)
    filtro = ""
    params: dict = {"lim": MAX_CANDIDATOS}
    if tams or divs:
        filtro = ('AND (upper(trim(p.tamanho)) = ANY(:tams) '
                  'OR upper(trim(p."fk_divisoes$divisao")) = ANY(:divs))')
        params |= {"tams": tams, "divs": divs}
    rows = (await db.execute(text(f"""
        SELECT p.pk_chave, p.nome, p.referencia_fabrica, p.cor, p.tamanho, p.colecao, p.genero,
               trim(p."fk_divisoes$divisao") AS divisao,
               marilia.obter_preco_venda(p.pk_chave) AS preco, f.img, f.bytes, {novo} AS novo
        FROM cadastros.produtos p {_ESTOQUE}
        JOIN LATERAL ({_FOTO_PRINCIPAL}) f ON true
        WHERE NOT coalesce(p.inativo, false) {filtro}
        ORDER BY p.pk_chave DESC
        LIMIT :lim"""), params)).mappings().all()
    return [
        {
            "id": r["pk_chave"], "nome": r["nome"], "referencia": r["referencia_fabrica"],
            "cor": r["cor"], "tamanho": r["tamanho"], "colecao": _norm(r["colecao"]),
            "genero": _norm(r["genero"]), "divisao": _norm(r["divisao"]),
            "preco": float(r["preco"] or 0), "foto_v": f"{r['img']}-{r['bytes']}",
            "novo": bool(r["novo"]),
        }
        for r in rows if float(r["preco"] or 0) > 0
    ]


async def sugerir(db: AsyncSession, pessoa_id: int) -> dict:
    """{"resumo": str|None, "itens": [...]}. Sem histórico de compras, não sugere nada."""
    compras = await _compras(db, pessoa_id)
    if not compras:
        return {"resumo": None, "itens": []}
    perfil = montar_perfil(compras, date.today())
    limite = min(PECAS_SUGESTAO, settings.CLIENTE_MAX_ITENS_CONDICIONAL)
    itens = escolher(perfil, await _candidatos(db, perfil), limite)
    return {"resumo": _resumo(perfil) if itens else None, "itens": itens}
