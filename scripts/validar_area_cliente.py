"""Fase 0 da Area do Cliente -- SOMENTE LEITURA, resultados agregados.

Roda contra as lojas configuradas em EMPRESAS (mesmo .env da API).
Uso (no servidor, com o venv ativo):  python scripts/validar_area_cliente.py
Nao imprime CPF, nome nem telefone de ninguem: so contagens.
"""
import asyncio
import os
import sys
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import EMPRESAS, settings

CONSULTAS = {
    "imagens de produto": 'SELECT count(*) AS imagens, count(DISTINCT "fk_produtos$produto") AS produtos '
                          "FROM cadastros.imagem_produto",
    "produtos vendaveis (ativos com saldo)": """
        SELECT count(DISTINCT p.pk_chave) AS total,
               count(DISTINCT p.pk_chave) FILTER (WHERE trim(coalesce(p.genero,''))<>'') AS com_genero,
               count(DISTINCT p.pk_chave) FILTER (WHERE trim(coalesce(p.colecao,''))<>'') AS com_colecao,
               count(DISTINCT p.pk_chave) FILTER (WHERE trim(coalesce(p.tamanho,''))<>'') AS com_tamanho,
               count(DISTINCT p.pk_chave) FILTER (WHERE trim(coalesce(p.cor,''))<>'') AS com_cor,
               count(DISTINCT p.pk_chave) FILTER (WHERE trim(coalesce(p.referencia_fabrica,''))<>'') AS com_referencia,
               count(DISTINCT p.pk_chave) FILTER (WHERE p."fk_divisoes$divisao" <> 'DIVISAO') AS divisao_especifica
        FROM cadastros.produtos p
        JOIN cadastros.v_estoque_atual e ON e."fk_produtos$produto" = p.pk_chave AND e.saldo > 0
        WHERE NOT p.inativo""",
    "divisoes (produtos vendaveis por divisao)": """
        SELECT p."fk_divisoes$divisao" AS divisao, count(DISTINCT p.pk_chave) AS n
        FROM cadastros.produtos p
        JOIN cadastros.v_estoque_atual e ON e."fk_produtos$produto" = p.pk_chave AND e.saldo > 0
        WHERE NOT p.inativo GROUP BY 1 ORDER BY 2 DESC""",
    "clientes: dados para login": r"""
        SELECT count(*) AS clientes_ativos,
               count(*) FILTER (WHERE coalesce(trim(cpf_cnpj),'')='') AS sem_documento,
               count(*) FILTER (WHERE length(regexp_replace(coalesce(cpf_cnpj,''),'\D','','g'))=11) AS com_cpf,
               count(*) FILTER (WHERE dt_nascimento IS NULL) AS sem_nascimento,
               count(*) FILTER (WHERE coalesce(trim(celular_principal),'')='') AS sem_celular,
               count(*) FILTER (WHERE length(regexp_replace(coalesce(celular_principal,''),'\D','','g')) IN (10,11)) AS celular_formato_ok
        FROM cadastros.pessoas WHERE cliente AND NOT coalesce(inativo, false)""",
    "CPFs repetidos entre clientes": r"""
        SELECT count(*) AS cpfs_repetidos, coalesce(max(n),0) AS maior_repeticao FROM (
          SELECT count(*) n FROM cadastros.pessoas
          WHERE cliente AND NOT coalesce(inativo,false)
            AND length(regexp_replace(coalesce(cpf_cnpj,''),'\D','','g'))=11
          GROUP BY regexp_replace(cpf_cnpj,'\D','','g') HAVING count(*)>1) x""",
    "vendedores em pre-vendas": 'SELECT count(*) AS pre_vendas, count("fk_pessoas$vendedor") AS com_vendedor '
                                "FROM marilia.pre_venda",
    "historico de compra": """
        SELECT count(DISTINCT me."fk_pessoas$pessoa") AS clientes_com_venda, count(*) AS vendas,
               min(me.data) AS primeira, max(me.data) AS ultima
        FROM marilia.pedido_venda pv
        JOIN marilia.movimentacao_estoque me ON me.pk_chave = pv."fk_movimentacao_estoque$movimentacao_estoque"
        WHERE me."fk_tipos_movimentacao$tipo_movimento" = 'VENDA DE MERCADORIA'""",
}


async def main() -> None:
    for banco, nome in EMPRESAS.items():
        print(f"\n{'=' * 70}\nLOJA: {nome} ({banco})\n{'=' * 70}")
        url = (f"postgresql+asyncpg://{settings.DB_USER}:{quote_plus(settings.DB_PASSWORD)}"
               f"@{settings.DB_HOST}:{settings.DB_PORT}/{banco}")
        engine = create_async_engine(url, poolclass=NullPool, connect_args={"statement_cache_size": 0})
        for titulo, sql in CONSULTAS.items():
            print(f"\n-- {titulo}")
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SET TRANSACTION READ ONLY"))
                    for linha in (await conn.execute(text(sql))).mappings().all():
                        print("  ", dict(linha))
            except Exception as e:  # uma consulta falhar nao pode esconder as outras
                print("   ERRO:", str(e).splitlines()[0][:200])
        await engine.dispose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
