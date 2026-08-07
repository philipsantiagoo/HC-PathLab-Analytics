# src/resources/database.py

from typing import AsyncGenerator
from uuid import uuid4
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import NullPool

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


def criar_engine(dsn: str) -> AsyncEngine:
    """Cria um engine assíncrono compatível com PostgreSQL atrás do PgBouncer."""
    dsn_normalizada = normalizar_dsn(dsn)
    engine_options = {"echo": False}

    # O pooler transacional do Supabase/PgBouncer pode entregar a mesma
    # conexão do cliente para sessões PostgreSQL diferentes. O asyncpg e o
    # cache de prepared statements do SQLAlchemy não são compatíveis com
    # esse comportamento quando usam nomes numéricos reutilizáveis.
    if dsn_normalizada.startswith("postgresql+asyncpg://"):
        separador = "&" if "?" in dsn_normalizada else "?"
        dsn_normalizada += f"{separador}prepared_statement_cache_size=0"
        engine_options.update(
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
            },
        )

    return create_async_engine(dsn_normalizada, **engine_options)


class DatabaseManager:
    """
    Manages asynchronous database connections and sessions for a specific DSN.
    """
    def __init__(self, dsn: str):
        self.engine = criar_engine(dsn)
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
