"""Catálogo público da Área do Cliente.

Só entra produto ativo, com saldo em estoque e com foto cadastrada.
Preço sempre vem do banco (marilia.obter_preco_venda).
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_TEM_DT_CADASTRO: dict[str, bool] = {}

# Produto só aparece com foto de verdade (bytea não vazio).
_FOTO = """EXISTS (SELECT 1 FROM cadastros.imagem_produto i
          WHERE i."fk_produtos$produto" = p.pk_chave AND octet_length(i.imagem) > 0)"""

_ESTOQUE = """JOIN (SELECT "fk_produtos$produto" AS pid, SUM(saldo) AS saldo
                FROM cadastros.v_estoque_atual GROUP BY 1 HAVING SUM(saldo) > 0) e
              ON e.pid = p.pk_chave"""


async def _tem_dt_cadastro(db: AsyncSession) -> bool:
    banco = db.get_bind().url.database
    if banco not in _TEM_DT_CADASTRO:
        r = await db.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_schema='cadastros' "
            "AND table_name='produtos' AND column_name='data_cadastramento'"))
        _TEM_DT_CADASTRO[banco] = r.first() is not None
    return _TEM_DT_CADASTRO[banco]


def _norm(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


async def listar(
    db: AsyncSession, busca=None, divisao=None, genero=None, colecao=None,
    novidades: bool = False, limit: int = 30, offset: int = 0,
) -> list[dict]:
    where = ["NOT coalesce(p.inativo, false)", _FOTO]
    params: dict = {"limit": min(max(limit, 1), 60), "offset": max(offset, 0)}
    if b := _norm(busca):
        where.append("(p.nome ILIKE :busca OR p.referencia_fabrica ILIKE :busca)")
        params["busca"] = f"%{b}%"
    for campo, col, val in (
        ("divisao", 'trim(p."fk_divisoes$divisao")', divisao),
        ("genero", "trim(p.genero)", genero),
        ("colecao", "trim(p.colecao)", colecao),
    ):
        if v := _norm(val):
            where.append(f"upper({col}) = upper(:{campo})")
            params[campo] = v
    if novidades and await _tem_dt_cadastro(db):
        where.append("p.data_cadastramento >= current_date - 30")

    rows = (await db.execute(text(f"""
        SELECT p.pk_chave, p.nome, p.referencia_fabrica, p.cor, p.tamanho, p.colecao,
               p.genero, trim(p."fk_divisoes$divisao") AS divisao,
               marilia.obter_preco_venda(p.pk_chave) AS preco, e.saldo
        FROM cadastros.produtos p {_ESTOQUE}
        WHERE {' AND '.join(where)}
        ORDER BY p.nome, p.pk_chave
        LIMIT :limit OFFSET :offset
    """), params)).mappings().all()
    return [
        {
            "id": r["pk_chave"], "nome": r["nome"], "referencia": r["referencia_fabrica"],
            "cor": r["cor"], "tamanho": r["tamanho"], "colecao": _norm(r["colecao"]),
            "genero": _norm(r["genero"]), "divisao": _norm(r["divisao"]),
            "preco": float(r["preco"] or 0),
        }
        for r in rows
    ]


async def filtros(db: AsyncSession) -> dict:
    """Valores existentes entre os produtos listáveis; vazio = filtro some do app."""
    base = f"FROM cadastros.produtos p {_ESTOQUE} WHERE NOT coalesce(p.inativo,false) AND {_FOTO}"
    out = {}
    for chave, col in (("divisoes", 'trim(p."fk_divisoes$divisao")'),
                       ("generos", "trim(p.genero)"), ("colecoes", "trim(p.colecao)")):
        rs = await db.execute(text(
            f"SELECT {col} AS v, count(*) FROM (SELECT p.* {base}) p "
            f"WHERE coalesce({col},'') <> '' GROUP BY 1 ORDER BY 1"))
        out[chave] = [{"nome": v, "total": n} for v, n in rs.all()]
    out["tem_novidades"] = False
    if await _tem_dt_cadastro(db):
        n = (await db.execute(text(
            f"SELECT count(*) {base} AND p.data_cadastramento >= current_date - 30"))).scalar()
        out["tem_novidades"] = bool(n)
    return out


async def foto(db: AsyncSession, produto_id: int) -> bytes | None:
    r = (await db.execute(text("""
        SELECT i.imagem FROM cadastros.produtos p
        JOIN cadastros.imagem_produto i ON i."fk_produtos$produto" = p.pk_chave
        WHERE p.pk_chave = :id AND NOT coalesce(p.inativo,false) AND octet_length(i.imagem) > 0
        ORDER BY (i.pk_chave = p."fk_imagem_produto$imagem_principal") DESC, i.pk_chave
        LIMIT 1"""), {"id": produto_id})).first()
    return bytes(r[0]) if r else None
