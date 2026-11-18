"""Fotos do catálogo em tamanho reduzido.

As fotos do ERP costumam vir do celular (vários MB). O app do cliente recebe
uma versão reduzida: "mini" para as listas e "grande" para a página do produto.
O resultado fica em cache (memória + disco) e a chave inclui o id e o tamanho
da imagem original, então trocar a foto no ERP gera uma miniatura nova.
"""
import asyncio
import io
import logging
import os
from collections import OrderedDict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("cliente_fotos")

TAMANHOS = {"mini": (480, 78), "grande": (1280, 82)}  # lado maior (px), qualidade JPEG
_DIR = Path(__file__).resolve().parents[2] / "cache_fotos"
_MEM_MAX_BYTES = 96 * 1024 * 1024

_mem: "OrderedDict[str, bytes]" = OrderedDict()
_mem_bytes = 0
_sem = asyncio.Semaphore(3)  # no máximo 3 reduções ao mesmo tempo (CPU)
_avisou_sem_pillow = False


def reduzir(original: bytes, tamanho: str) -> bytes:
    """Devolve JPEG reduzido. Se não der (sem Pillow, formato estranho), devolve o original."""
    global _avisou_sem_pillow
    try:
        from PIL import Image, ImageOps
    except ImportError:
        if not _avisou_sem_pillow:
            log.warning("Pillow não instalado: fotos serão entregues em tamanho original.")
            _avisou_sem_pillow = True
        return original
    lado, qualidade = TAMANHOS[tamanho]
    try:
        with Image.open(io.BytesIO(original)) as im:
            im = ImageOps.exif_transpose(im)  # respeita a rotação da câmera
            if im.mode not in ("RGB", "L"):
                fundo = Image.new("RGB", im.size, (255, 255, 255))
                rgba = im.convert("RGBA")
                fundo.paste(rgba, mask=rgba.split()[-1])
                im = fundo
            elif im.mode == "L":
                im = im.convert("RGB")
            im.thumbnail((lado, lado))  # só reduz, nunca amplia
            saida = io.BytesIO()
            im.save(saida, "JPEG", quality=qualidade, optimize=True, progressive=True)
            return saida.getvalue()
    except Exception:
        log.exception("não foi possível reduzir a foto; entregando original")
        return original


def _guardar_mem(chave: str, dados: bytes) -> None:
    global _mem_bytes
    if chave in _mem:
        _mem_bytes -= len(_mem.pop(chave))
    _mem[chave] = dados
    _mem_bytes += len(dados)
    while _mem_bytes > _MEM_MAX_BYTES and _mem:
        _, velho = _mem.popitem(last=False)
        _mem_bytes -= len(velho)


def _ler_disco(chave: str) -> bytes | None:
    try:
        return (_DIR / chave).read_bytes()
    except OSError:
        return None


def _gravar_disco(chave: str, dados: bytes) -> None:
    try:  # best effort: se a pasta não for gravável, só perde o cache em disco
        _DIR.mkdir(exist_ok=True)
        tmp = _DIR / f"{chave}.{os.getpid()}.tmp"
        tmp.write_bytes(dados)
        os.replace(tmp, _DIR / chave)
    except OSError:
        pass


async def foto(db: AsyncSession, loja: str, produto_id: int, tamanho: str,
               img: int | None = None) -> bytes | None:
    """[img] = código de uma foto específica do produto; sem ele, a principal."""
    if tamanho not in TAMANHOS:
        tamanho = "mini"
    # Primeiro só os metadados (barato); o conteúdo só é lido se faltar no cache.
    # A foto escolhida precisa ser deste produto (e o produto, ativo).
    filtro_img = "AND i.pk_chave = :img" if img is not None else ""
    params = {"id": produto_id, **({"img": img} if img is not None else {})}
    meta = (await db.execute(text(f"""
        SELECT i.pk_chave, octet_length(i.imagem) AS bytes
        FROM cadastros.produtos p
        JOIN cadastros.imagem_produto i ON i."fk_produtos$produto" = p.pk_chave
        WHERE p.pk_chave = :id AND NOT coalesce(p.inativo,false) AND octet_length(i.imagem) > 0
          {filtro_img}
        ORDER BY (i.pk_chave = p."fk_imagem_produto$imagem_principal") DESC, i.pk_chave
        LIMIT 1"""), params)).first()
    if not meta:
        return None
    chave = f"{loja}_{meta[0]}_{meta[1]}_{tamanho}.jpg"

    if (d := _mem.get(chave)) is not None:
        _mem.move_to_end(chave)
        return d
    if (d := _ler_disco(chave)) is not None:
        _guardar_mem(chave, d)
        return d

    async with _sem:
        if (d := _mem.get(chave)) is not None:  # outro pedido já gerou enquanto esperava
            return d
        original = (await db.execute(
            text("SELECT imagem FROM cadastros.imagem_produto WHERE pk_chave = :k"),
            {"k": meta[0]})).scalar()
        orig = bytes(original)
        d = await asyncio.to_thread(reduzir, orig, tamanho)
    if d is orig:  # não deu para reduzir: entrega a original, mas não ocupa o cache
        return d
    _guardar_mem(chave, d)
    await asyncio.to_thread(_gravar_disco, chave, d)
    return d
