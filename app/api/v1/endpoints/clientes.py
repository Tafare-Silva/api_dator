from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import get_db

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("/", summary="Busca clientes por nome")
async def buscar_clientes(
    busca: str = Query(..., min_length=2, description="Nome do cliente (mín. 2 caracteres)"),
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db),
):
    sql = text("""
        SELECT
            p.chave,
            p.nome,
            p.cpf_cnpj,
            p.telefone_fixo,
            p.celular_principal
        FROM cadastros.pessoas p
        WHERE p.nome ILIKE :busca
          AND p.inativo = false
        ORDER BY p.nome
        LIMIT :limit
    """)
    rows = (await db.execute(sql, {"busca": f"%{busca}%", "limit": limit})).all()
    return [
        {
            "pk_chave": r.chave,
            "nome": r.nome,
            "cnpj_cpf": r.cpf_cnpj,
            "fone": r.telefone_fixo,
            "celular": r.celular_principal,
        }
        for r in rows
    ]
