"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from node_api.config import settings
from node_api.db.models import Base
from node_api.db.session import engine
from node_api.routes import agent, conjunctions, maneuvers, satellites, spacecraft


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(spacecraft.router, prefix="/spacecraft", tags=["spacecraft"])
    app.include_router(satellites.router, prefix="/satellites", tags=["satellites"])
    app.include_router(conjunctions.router, prefix="/conjunctions", tags=["conjunctions"])
    app.include_router(maneuvers.router, prefix="/maneuvers", tags=["maneuvers"])
    app.include_router(agent.router, prefix="/agent", tags=["agent"])

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
