# src/resources/database.py

from typing import AsyncGenerator
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Base para os modelos do banco de dados da aplicação
Base = declarative_base()


# O painel do Supabase entrega a connection string como ``postgresql://``, que o
# SQLAlchemy resolve para psycopg2 — síncrono — e o engine assíncrono quebra no
# startup com "The loaded 'psycopg2' is not async". Como toda colagem da URI do
# painel reintroduz o problema, normalizamos aqui em vez de depender de alguém
# lembrar de digitar o driver no .env.
DRIVERS_ASSINCRONOS = {
    "postgresql": "postgresql+asyncpg",
    "postgres": "postgresql+asyncpg",
    "sqlite": "sqlite+aiosqlite",
}


def normalizar_dsn(dsn: str) -> str:
    """Garante um driver assíncrono na DSN, preservando-a se já houver um."""
    if not dsn:
        return dsn
    esquema, separador, resto = dsn.partition("://")
    if not separador or "+" in esquema:
        return dsn  # driver já explícito (ex.: postgresql+asyncpg)
    destino = DRIVERS_ASSINCRONOS.get(esquema.lower())
    return f"{destino}://{resto}" if destino else dsn


class DatabaseManager:
    """
    Manages asynchronous database connections and sessions for a specific DSN.
    """
    def __init__(self, dsn: str):
        self.engine: AsyncEngine = create_async_engine(normalizar_dsn(dsn), echo=False) # Set echo=False to reduce log verbosity
        self.async_session_maker = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provides an asynchronous session for database operations.
        """
        async with self.async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()

    async def close_connection(self):
        """
        Closes all connections in the engine's connection pool.
        """
        await self.engine.dispose()

async def get_aghu_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get an AGHU database session from the app state.
    """
    aghu_db_manager: DatabaseManager = request.app.state.aghu_db
    async for session in aghu_db_manager.get_session():
        yield session

async def get_app_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get an application database session (SQLite) from the app state.
    """
    app_db_manager: DatabaseManager = request.app.state.app_db
    async for session in app_db_manager.get_session():
        yield session
