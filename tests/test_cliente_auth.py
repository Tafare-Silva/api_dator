"""Isolamento entre token de cliente e token da equipe, e trava do login do cliente.

Não precisa de banco: todos os casos são recusados antes de qualquer consulta.
Rode com as variáveis DB_* definidas (qualquer valor serve).
"""
import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import EMPRESAS, settings
from app.core.security import criar_token
from app.main import app
from app.services import cliente_auth_service as svc

client = TestClient(app, raise_server_exceptions=False)
LOJA = next(iter(EMPRESAS))


def _token_cliente(**extra):
    return criar_token({"sub": "123", "tipo": "cliente", "loja": LOJA, **extra})


def _token_equipe():
    return criar_token({"sub": "FULANO", "empresa": LOJA})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_token_de_cliente_nao_acessa_rotas_internas():
    for rota in ("/api/v1/produtos/", "/api/v1/vendas/dashboard", "/api/v1/financeiro/contas-receber"):
        r = client.get(rota, headers=_auth(_token_cliente()))
        assert r.status_code == 401, rota


def test_token_da_equipe_nao_acessa_rotas_do_cliente():
    assert client.get("/api/v1/cliente/auth/me", headers=_auth(_token_equipe())).status_code == 401


def test_cliente_sem_token_ou_com_lixo_e_recusado():
    assert client.get("/api/v1/cliente/auth/me").status_code == 401
    assert client.get("/api/v1/cliente/auth/me", headers=_auth("lixo")).status_code == 401


def test_token_de_cliente_valido_funciona_no_me():
    r = client.get("/api/v1/cliente/auth/me", headers=_auth(_token_cliente()))
    assert r.status_code == 200 and r.json()["pessoa_id"] == 123


def test_token_de_cliente_com_loja_inexistente_e_recusado():
    t = criar_token({"sub": "1", "tipo": "cliente", "loja": "banco_que_nao_existe"})
    assert client.get("/api/v1/cliente/auth/me", headers=_auth(t)).status_code == 401


def test_solicitar_codigo_desligado_sem_provedor(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "uma-chave-forte-qualquer")
    monkeypatch.setattr(settings, "CLIENTE_ENVIO_PROVEDOR", "")
    body = {"cpf": "12345678909", "loja": LOJA}
    assert client.post("/api/v1/cliente/auth/solicitar-codigo", json=body).status_code == 503


def test_recusado_com_secret_key_padrao(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "troque-esta-chave-em-producao")
    monkeypatch.setattr(settings, "CLIENTE_ENVIO_PROVEDOR", "log")
    body = {"cpf": "12345678909", "loja": LOJA}
    assert client.post("/api/v1/cliente/auth/solicitar-codigo", json=body).status_code == 503


def test_loja_invalida(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "uma-chave-forte-qualquer")
    monkeypatch.setattr(settings, "CLIENTE_ENVIO_PROVEDOR", "log")
    body = {"cpf": "12345678909", "loja": "nao_existe"}
    assert client.post("/api/v1/cliente/auth/solicitar-codigo", json=body).status_code == 422


def test_codigo_vale_uma_vez_e_erra_demais_invalida(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "uma-chave-forte-qualquer")
    cod = svc.gerar_codigo(LOJA, "111")
    assert not svc.conferir_codigo(LOJA, "111", "000000" if cod != "000000" else "999999")
    assert svc.conferir_codigo(LOJA, "111", cod)
    assert not svc.conferir_codigo(LOJA, "111", cod)  # já usado
    cod = svc.gerar_codigo(LOJA, "222")
    for _ in range(svc.MAX_ERROS_CODIGO):
        svc.conferir_codigo(LOJA, "222", "abcdef")
    assert not svc.conferir_codigo(LOJA, "222", cod)  # invalidado


def test_codigo_expirado(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "uma-chave-forte-qualquer")
    cod = svc.gerar_codigo(LOJA, "333")
    svc._codigos[(LOJA, "333")]["exp"] = time.time() - 1
    assert not svc.conferir_codigo(LOJA, "333", cod)


def test_normalizar_celular():
    assert svc.normalizar_celular("(67) 99999-1234") == "5567999991234"
    assert svc.normalizar_celular("5567999991234") == "5567999991234"
    assert svc.normalizar_celular("1234") is None and svc.normalizar_celular(None) is None


def test_catalogo_publico_valida_loja():
    assert client.get("/api/v1/cliente/catalogo/?loja=xx").status_code == 422
    assert client.get("/api/v1/cliente/catalogo/filtros?loja=xx").status_code == 422
    assert client.get("/api/v1/cliente/catalogo/1/foto?loja=xx").status_code == 422


def test_bloqueio_apos_varias_falhas(monkeypatch):
    monkeypatch.setattr(settings, "CLIENTE_MAX_TENTATIVAS", 3)
    chave = "cpf:00000000000"
    svc.limpar_falhas(chave)
    for _ in range(2):
        svc.registrar_falha(chave)
    assert not svc.bloqueado(chave)
    svc.registrar_falha(chave)
    assert svc.bloqueado(chave)
    svc.limpar_falhas(chave)
    assert not svc.bloqueado(chave)


def test_falhas_antigas_saem_da_janela(monkeypatch):
    monkeypatch.setattr(settings, "CLIENTE_MAX_TENTATIVAS", 1)
    monkeypatch.setattr(settings, "CLIENTE_JANELA_BLOQUEIO_MIN", 1)
    chave = "cpf:11111111111"
    svc._falhas[chave] = [time.time() - 120]
    assert not svc.bloqueado(chave)


def test_apenas_digitos():
    assert svc.apenas_digitos("123.456.789-09") == "12345678909"
    assert svc.apenas_digitos(None) == ""
