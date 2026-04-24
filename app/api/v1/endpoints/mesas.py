from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.mesa import MesaCreate, MesaResponse, MesaUpdate
from app.services import mesa_service

router = APIRouter(prefix="/mesas", tags=["Mesas"])


@router.get("/", response_model=list[MesaResponse], summary="Lista todas as mesas")
async def listar_mesas(db: AsyncSession = Depends(get_db)):
    return await mesa_service.listar_mesas(db)


@router.get("/{nome}", response_model=MesaResponse, summary="Detalhe de uma mesa")
async def detalhar_mesa(nome: str, db: AsyncSession = Depends(get_db)):
    return await mesa_service.buscar_mesa(db, nome)


@router.post("/", response_model=MesaResponse, status_code=201, summary="Cria uma nova mesa")
async def criar_mesa(dados: MesaCreate, db: AsyncSession = Depends(get_db)):
    return await mesa_service.criar_mesa(db, dados)


@router.patch("/{nome}", response_model=MesaResponse, summary="Atualiza dados de uma mesa")
async def atualizar_mesa(nome: str, dados: MesaUpdate, db: AsyncSession = Depends(get_db)):
    return await mesa_service.atualizar_mesa(db, nome, dados)


@router.delete("/{nome}", status_code=204, summary="Remove uma mesa")
async def excluir_mesa(nome: str, db: AsyncSession = Depends(get_db)):
    await mesa_service.excluir_mesa(db, nome)
