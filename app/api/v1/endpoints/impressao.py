import socket
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.item_mesa_service import get_resumo_conta

router = APIRouter(prefix="/impressao", tags=["Impressão"])


class ConfigImpressora(BaseModel):
    ip: str
    porta: int = 9100


class ImprimirPedidoRequest(BaseModel):
    nome_mesa: str
    impressora_ip: str
    impressora_porta: int = 9100


def _gerar_esc_pos(nome_mesa: str, resumo) -> bytes:
    """
    Gera os bytes ESC/POS para impressora térmica Bematech / genérica.
    Protocolo padrão — funciona na maioria das impressoras térmicas.
    """
    ESC = b'\x1b'
    GS = b'\x1d'
    LF = b'\n'

    cmds = bytearray()

    # Inicializa impressora
    cmds += ESC + b'@'

    # Centraliza
    cmds += ESC + b'a' + b'\x01'
    # Negrito + tamanho maior
    cmds += ESC + b'E' + b'\x01'
    cmds += GS + b'!' + b'\x11'
    cmds += f'MESA: {nome_mesa}\n'.encode('cp850', errors='replace')
    # Reset tamanho
    cmds += GS + b'!' + b'\x00'
    cmds += ESC + b'E' + b'\x00'

    # Alinha esquerda
    cmds += ESC + b'a' + b'\x00'
    cmds += b'-' * 32 + LF

    # Data/hora
    from datetime import datetime
    cmds += f'{datetime.now().strftime("%d/%m/%Y %H:%M")}\n'.encode('cp850', errors='replace')
    cmds += b'-' * 32 + LF

    # Itens
    for item in resumo.itens:
        nome = (item.produto.nome if item.produto else f'Produto #{item.fk_produtos_produto}') or ''
        qtd = item.quantidade
        total = item.vr_total

        # Nome do produto (máx 32 chars)
        nome_truncado = nome[:32]
        cmds += f'{nome_truncado}\n'.encode('cp850', errors='replace')

        # Quantidade x Valor unitário = Total
        qtd_str = f'{qtd:.0f}' if qtd == int(qtd) else f'{qtd:.2f}'
        linha_valor = f'  {qtd_str} x R${item.vr_unitario_bruto:.2f} = R${total:.2f}'
        cmds += linha_valor.encode('cp850', errors='replace') + LF

        # Observação se houver
        if item.observacoes_item:
            obs = f'  OBS: {item.observacoes_item[:28]}'
            cmds += obs.encode('cp850', errors='replace') + LF

    cmds += b'-' * 32 + LF

    # Total
    cmds += ESC + b'E' + b'\x01'
    total_str = f'TOTAL: R${resumo.total_bruto:.2f}\n'
    cmds += total_str.encode('cp850', errors='replace')
    cmds += ESC + b'E' + b'\x00'

    # Espaço e corte
    cmds += LF * 3
    # Corte total (GS V 0)
    cmds += GS + b'V' + b'\x00'

    return bytes(cmds)


@router.post("/pedido", summary="Imprime pedido da mesa na impressora térmica via TCP/IP")
async def imprimir_pedido(
    dados: ImprimirPedidoRequest,
    db: AsyncSession = Depends(get_db),
):
    resumo = await get_resumo_conta(db, dados.nome_mesa)

    conteudo = _gerar_esc_pos(dados.nome_mesa, resumo)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((dados.impressora_ip, dados.impressora_porta))
        sock.sendall(conteudo)
        sock.close()
    except socket.timeout:
        raise HTTPException(status_code=504, detail=f"Impressora {dados.impressora_ip}:{dados.impressora_porta} não respondeu (timeout).")
    except ConnectionRefusedError:
        raise HTTPException(status_code=502, detail=f"Não foi possível conectar na impressora {dados.impressora_ip}:{dados.impressora_porta}.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao imprimir: {str(e)}")

    return {"status": "impresso", "mesa": dados.nome_mesa}


@router.post("/testar-conexao", summary="Testa conexão com a impressora")
async def testar_conexao(config: ConfigImpressora):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((config.ip, config.porta))
        sock.close()
        return {"status": "ok", "mensagem": f"Impressora {config.ip}:{config.porta} acessível."}
    except Exception:
        raise HTTPException(status_code=502, detail=f"Impressora {config.ip}:{config.porta} não acessível.")