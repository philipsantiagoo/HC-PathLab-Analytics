"""Sobe a aplicação por alguns instantes e valida o registro das rotas."""

import asyncio

from src.main import app


async def main() -> None:
    async with app.router.lifespan_context(app):
        rotas = [r for r in app.routes if getattr(r, "path", "").startswith("/api/")]
        print(f"rotas_api={len(rotas)}")


if __name__ == "__main__":
    asyncio.run(main())
