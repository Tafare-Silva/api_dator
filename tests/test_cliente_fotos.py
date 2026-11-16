"""Redução das fotos do catálogo (sem banco)."""
import io

import pytest
from PIL import Image

from app.services import cliente_fotos_service as fotos


def _foto(w=3000, h=4000, modo="RGB"):
    import os
    im = Image.frombytes("RGB", (w, h), os.urandom(w * h * 3)).convert(modo)
    b = io.BytesIO()
    im.save(b, "PNG" if modo == "RGBA" else "JPEG", quality=95)
    return b.getvalue()


def test_mini_fica_pequena_e_dentro_do_limite():
    orig = _foto()
    out = fotos.reduzir(orig, "mini")
    im = Image.open(io.BytesIO(out))
    assert max(im.size) == 480 and im.format == "JPEG"
    assert len(out) < len(orig) / 10


def test_grande_nao_amplia_foto_pequena():
    out = fotos.reduzir(_foto(300, 200), "grande")
    assert Image.open(io.BytesIO(out)).size == (300, 200)


def test_png_com_transparencia_vira_jpeg():
    out = fotos.reduzir(_foto(600, 600, "RGBA"), "mini")
    assert Image.open(io.BytesIO(out)).format == "JPEG"


def test_lixo_devolve_original():
    lixo = b"isto nao e uma imagem"
    assert fotos.reduzir(lixo, "mini") is lixo
