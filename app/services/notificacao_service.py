"""Envio do código de acesso ao cliente. Um provedor por vez, escolhido em
CLIENTE_ENVIO_PROVEDOR ('log' para teste, 'evolution' para WhatsApp)."""
import logging

import httpx

from app.core.config import settings

log = logging.getLogger("notificacao")


class EnvioIndisponivel(Exception):
    pass


def _evolution_configurada() -> bool:
    return bool(settings.EVOLUTION_URL and settings.EVOLUTION_INSTANCE and settings.EVOLUTION_API_KEY)


def provedor_ativo() -> bool:
    prov = settings.CLIENTE_ENVIO_PROVEDOR
    return prov == "log" or (prov == "evolution" and _evolution_configurada())


async def _enviar_evolution(celular: str, texto: str) -> None:
    url = f"{settings.EVOLUTION_URL.rstrip('/')}/message/sendText/{settings.EVOLUTION_INSTANCE}"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, headers={"apikey": settings.EVOLUTION_API_KEY},
                             json={"number": celular, "text": texto})
        r.raise_for_status()
    except httpx.HTTPError as e:
        # nunca loga o corpo/URL com chave; só o tipo do erro
        raise EnvioIndisponivel(f"Evolution API falhou: {type(e).__name__}") from e


async def enviar_codigo(celular: str, codigo: str) -> None:
    prov = settings.CLIENTE_ENVIO_PROVEDOR
    if prov == "log":
        # Apenas para teste: o código vai para o log, ninguém recebe nada.
        log.warning("CODIGO DE ACESSO (teste) para %s: %s", celular, codigo)
    elif prov == "evolution" and _evolution_configurada():
        await _enviar_evolution(
            celular,
            f"Seu código de acesso é *{codigo}*. Vale por "
            f"{settings.CLIENTE_CODIGO_VALIDADE_MIN} minutos. Não compartilhe com ninguém.")
    else:
        raise EnvioIndisponivel("Provedor de envio não configurado.")
