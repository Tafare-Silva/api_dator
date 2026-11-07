"""Envio do código de acesso ao cliente. Um provedor por vez, escolhido em
CLIENTE_ENVIO_PROVEDOR. Para WhatsApp/SMS reais, adicionar uma função aqui."""
import logging

from app.core.config import settings

log = logging.getLogger("notificacao")


class EnvioIndisponivel(Exception):
    pass


def provedor_ativo() -> bool:
    return settings.CLIENTE_ENVIO_PROVEDOR in ("log",)


async def enviar_codigo(celular: str, codigo: str) -> None:
    if settings.CLIENTE_ENVIO_PROVEDOR == "log":
        # Apenas para teste: o código vai para o log, ninguém recebe nada.
        log.warning("CODIGO DE ACESSO (teste) para %s: %s", celular, codigo)
        return
    raise EnvioIndisponivel("Provedor de envio não configurado.")
