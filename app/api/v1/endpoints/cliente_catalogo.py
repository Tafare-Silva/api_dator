from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401

from app.core.config import EMPRESAS
from app.db.session import SESSION_FACTORIES
from app.services import cliente_catalogo_service as svc
from app.services import cliente_fotos_service as fotos

# Público: o cliente navega sem login. Nada aqui devolve dado de cliente.
router = APIRouter(prefix="/cliente/catalogo", tags=["Área do Cliente - Catálogo"])


def _loja(loja: str) -> str:
    if loja not in EMPRESAS:
        raise HTTPException(422, "Loja inválida.")
    return loja


def _tipo_imagem(b: bytes) -> str:
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


@router.get("/", summary="Produtos com foto e saldo")
async def listar(
    loja: str, busca: str | None = None, divisao: str | None = None,
    genero: str | None = None, colecao: str | None = None, novidades: bool = False,
    limit: int = Query(30, ge=1, le=60), offset: int = Query(0, ge=0),
):
    async with SESSION_FACTORIES[_loja(loja)]() as db:
        return await svc.listar(db, busca, divisao, genero, colecao, novidades, limit, offset)


@router.get("/filtros", summary="Divisões, gêneros e coleções disponíveis")
async def filtros(loja: str):
    async with SESSION_FACTORIES[_loja(loja)]() as db:
        return await svc.filtros(db)


@router.get("/{produto_id}/fotos", summary="Todas as fotos do produto (principal primeiro)")
async def fotos_do_produto(produto_id: int, loja: str):
    async with SESSION_FACTORIES[_loja(loja)]() as db:
        return await svc.fotos_do_produto(db, produto_id)


@router.get("/{produto_id}/foto", summary="Foto do produto (reduzida)")
async def foto(
    produto_id: int, loja: str, tamanho: str = Query("mini", pattern="^(mini|grande)$"),
    img: int | None = None, v: str | None = Query(None, max_length=40),
):
    async with SESSION_FACTORIES[_loja(loja)]() as db:
        b = await fotos.foto(db, loja, produto_id, tamanho, img)
    if not b:
        raise HTTPException(404, "Sem foto.")
    # Com "v" (versão da foto na URL) o navegador pode guardar por muito tempo: se a
    # foto mudar no ERP, a URL muda. Sem "v", cache curto para a troca aparecer logo.
    cache = "public, max-age=31536000, immutable" if v else "public, max-age=300"
    return Response(b, media_type=_tipo_imagem(b), headers={"Cache-Control": cache})
