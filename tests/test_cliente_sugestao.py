from datetime import date, timedelta

from app.services.cliente_sugestao_service import escolher, montar_perfil, pontuar

HOJE = date(2026, 11, 18)


def compra(pid, tam="M", div="BLUSAS", preco=80.0, dias=10, qtd=1, genero="FEMININO"):
    return {"produto_id": pid, "tamanho": tam, "divisao": div, "genero": genero, "colecao": "VERAO",
            "quantidade": qtd, "preco": preco, "data": HOJE - timedelta(days=dias)}


def peca(pid, tam="M", div="BLUSAS", preco=85.0, novo=False, genero="FEMININO"):
    return {"id": pid, "nome": f"P{pid}", "tamanho": tam, "divisao": div, "genero": genero,
            "colecao": "VERAO", "preco": preco, "novo": novo}


def test_perfil_pesa_compra_recente_mais_que_antiga():
    p = montar_perfil([compra(1, tam="M", dias=5), compra(2, tam="G", dias=700)], HOJE)
    assert p["pesos"]["tamanho"]["M"] > 10 * p["pesos"]["tamanho"]["G"]


def test_peca_do_tamanho_e_categoria_da_cliente_pontua_mais():
    p = montar_perfil([compra(1), compra(2)], HOJE)
    boa, _ = pontuar(p, peca(10))
    outra, _ = pontuar(p, peca(11, tam="GG", div="CALCAS"))
    assert boa > outra


def test_nao_sugere_o_que_ela_ja_comprou():
    p = montar_perfil([compra(1)], HOJE)
    ids = [i["id"] for i in escolher(p, [peca(1), peca(2)], 6)]
    assert ids == [2]


def test_peca_sem_nada_em_comum_nao_e_sugerida():
    p = montar_perfil([compra(1, tam="M", div="BLUSAS", genero="FEMININO")], HOJE)
    estranha = {**peca(5, tam="48", div="TERNOS", genero="MASCULINO"), "colecao": "INVERNO"}
    assert escolher(p, [estranha], 6) == []


def test_muito_mais_cara_perde_pontos():
    p = montar_perfil([compra(1, preco=80), compra(2, preco=90)], HOJE)
    barata, _ = pontuar(p, peca(10, preco=90))
    cara, _ = pontuar(p, peca(11, preco=400))
    assert barata > cara


def test_variedade_limita_uma_categoria():
    p = montar_perfil([compra(1, div="BLUSAS"), compra(2, div="SAIAS", tam="M")], HOJE)
    cands = [peca(10 + i, div="BLUSAS") for i in range(10)] + [peca(30, div="SAIAS")]
    saida = escolher(p, cands, 5)
    assert sum(1 for i in saida if i["divisao"] == "BLUSAS") <= 3
    assert any(i["divisao"] == "SAIAS" for i in saida)


def test_motivo_explica_e_nao_vaza_campo_interno():
    p = montar_perfil([compra(1)], HOJE)
    item = escolher(p, [peca(2)], 6)[0]
    assert "tamanho M" in item["motivo"] and "Blusas" in item["motivo"]
    assert "novo" not in item


def test_sem_compras_perfil_vazio_nao_quebra():
    p = montar_perfil([], HOJE)
    assert escolher(p, [peca(1)], 6) == []
