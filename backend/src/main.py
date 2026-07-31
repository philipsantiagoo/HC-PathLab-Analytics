from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

from .resources.database import DatabaseManager, Base
from .services.catalogos import garantir_catalogos_iniciais

# Importa o pacote de modelos para registrar todas as tabelas em Base.metadata
# (necessário para o create_all do startup e para o autogenerate do Alembic).
from . import models  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")

    # Initialize AGHU DB Manager and store in app.state
    aghu_dsn = os.getenv("POSTGRES_DSN")
    if aghu_dsn:
        app.state.aghu_db = DatabaseManager(aghu_dsn)
        print("AGHU PostgreSQL connection pool initialized.")
    else:
        print("AGHU source database not configured (POSTGRES_DSN); continuing without direct AGHU access.")

    # APP_DATABASE_DSN recebe o PostgreSQL do Supabase em produção. O fallback
    # mantém SQLite funcional para desenvolvimento local legado.
    app_dsn = os.getenv("APP_DATABASE_DSN") or os.getenv("SQLITE_DSN")
    if not app_dsn:
        raise ValueError("APP_DATABASE_DSN or SQLITE_DSN not found in environment variables.")
    app.state.app_db = DatabaseManager(app_dsn)
    banco_app = "Supabase/PostgreSQL" if app_dsn.startswith("postgresql") else "SQLite"
    print(f"Application database connection pool initialized: {banco_app}.")

    # Create tables for App DB (if they don't exist) - for development only, Alembic handles this in production
    async with app.state.app_db.engine.begin() as conn:
        # O schema ``pathlab`` existe somente no PostgreSQL e é criado por
        # migrations. Limitar o create_all às tabelas sem schema mantém o
        # fallback SQLite de desenvolvimento funcional.
        tabelas_locais = [t for t in Base.metadata.sorted_tables if t.schema is None]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tabelas_locais))
    async with app.state.app_db.async_session_maker() as session:
        await garantir_catalogos_iniciais(session)
    print(f"Application database tables checked: {banco_app}.")

    yield

    # Shutdown
    print("Shutting down...")
    if hasattr(app.state, 'aghu_db') and app.state.aghu_db:
        await app.state.aghu_db.close_connection()
        print("AGHU PostgreSQL connection pool closed.")
    if hasattr(app.state, 'app_db') and app.state.app_db:
        await app.state.app_db.close_connection()
        print("App SQLite connection pool closed.")

app = FastAPI(
    title="Esqueleto de Aplicação Web Full-Stack",
    description="Aplicação Backend monolítica (API REST) em Python/FastAPI, com foco em acesso e agregação de dados heterogêneos.",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve o frontend Vue 3 empacotado (só monta se o build existir — em dev usa Vite diretamente)
if os.path.isdir("src/static/dist/assets"):
    app.mount("/static/dist/assets", StaticFiles(directory="src/static/dist/assets"), name="assets")
if os.path.isdir("src/static/dist"):
    app.mount("/static/dist", StaticFiles(directory="src/static/dist"), name="static")

# Placeholder para incluir os roteadores da API
from .routers import paciente, auth, admin, aih, bpa, material
from .routers import exame, frasco, macroscopia, historico, processamento, microscopia, congelamento, usuarios
app.include_router(paciente.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(aih.router)
app.include_router(bpa.router)
app.include_router(material.router)

# Fluxo de rastreabilidade de amostras (Fase 1: Triagem + Macroscopia)
app.include_router(exame.router)
app.include_router(frasco.router)
app.include_router(macroscopia.router)
app.include_router(historico.router)
app.include_router(processamento.router)
app.include_router(microscopia.router)
app.include_router(congelamento.router)
app.include_router(usuarios.router)

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """
    Serve o arquivo index.html para todas as rotas que não são da API ou arquivos estáticos.
    Isso é necessário para que o roteamento do Vue (SPA) funcione.
    """
    # Se a rota começa com 'api', deixa o roteador do FastAPI lidar
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="API route not found")
    
    index_path = os.path.join("src", "static", "dist", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend build not found"}

# Exemplo:
# from .routers import aih, bpa, material
# app.include_router(aih.router)
# app.include_router(bpa.router)
# app.include_router(material.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
