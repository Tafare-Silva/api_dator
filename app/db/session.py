from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import quote_plus
from typing import AsyncGenerator

from app.core.config import settings

# Monta a URL codificando a senha corretamente
DATABASE_URL = (
    f"postgresql+asyncpg://{settings.DB_USER}:"
    f"{quote_plus(settings.DB_PASSWORD)}@"
    f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

print(f"🔗 Conectando em: postgresql+asyncpg://{settings.DB_USER}:***@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
print(f"🔑 Senha codificada: {quote_plus(settings.DB_PASSWORD)}")

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise