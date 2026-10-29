"""FastAPI application: the security layer between the web app and LLM/OCR/database."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.dependencies import current_principal
from app.auth.principal import Principal
from app.auth.tokens import TokenVerifier
from app.config import Settings, get_settings
from app.db import Database
from app.documents.pipeline import Pipeline
from app.documents.routes import router as documents_router
from app.extraction.service import Extractor
from app.privacy.gateway import create_gateway
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LlmProvider
from app.providers.ocr import OcrProvider, create_ocr_provider
from app.quotas import consume
from app.rag.indexer import Indexer
from app.rag.routes import router as questions_router
from app.residents.routes import router as residents_router
from app.security.screening import Screener

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAINTENANCE_MESSAGE = "Demo wird gerade zurückgesetzt – bitte in einer Minute erneut versuchen"


def create_app(
    settings: Settings | None = None,
    verifier: TokenVerifier | None = None,
    ocr: OcrProvider | None = None,
    llm: LlmProvider | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> FastAPI:
    """Application factory; reads settings from the environment unless given explicitly.

    `verifier` replaces the JWKS-based token check in tests (test IdP), `ocr`, `llm` and
    `embeddings` the providers chosen by OCR_PROVIDER and LLM_PROVIDER.
    """
    settings = settings or Settings()
    ocr = ocr or create_ocr_provider(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.verifier = verifier
        if app.state.verifier is None and settings.oidc_issuer:
            app.state.verifier = TokenVerifier.from_issuer(
                settings.oidc_issuer, settings.oidc_audience
            )
        app.state.database = Database(settings.database_url) if settings.database_url else None
        app.state.pipeline = None
        app.state.indexer = None
        if app.state.database:
            await app.state.database.open()
            database = app.state.database

            async def book_retry(principal: Principal) -> None:
                # The extraction's second attempt costs one more LLM call (F10-AC10).
                async with database.as_principal(principal) as conn:
                    await consume(conn, "llm_call", 1)

            # F06-AC1: every model call goes through the gateway (pseudonymised text only).
            app.state.gateway = create_gateway(settings, database, llm, embeddings)

            async def book_guard(principal: Principal) -> None:
                # One injection check of a document, at most 20 000 characters (F07-AC4).
                async with database.as_principal(principal) as conn:
                    await consume(conn, "guard_document", 1)

            app.state.pipeline = Pipeline(
                database,
                ocr,
                Extractor(app.state.gateway, book_retry),
                screener=Screener(app.state.gateway, book_guard),
            )
            app.state.indexer = Indexer(database, app.state.gateway)
        try:
            yield
        finally:
            if app.state.database:
                await app.state.database.close()

    app = FastAPI(title="Pflege-Posteingang API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def refuse_writes_during_reset(request: Request, call_next):
        # F10-AC7: while the nightly reset runs, writes get a clear 503 instead of waiting
        # for the reset's locks; reading keeps working (it waits at most a few seconds).
        database = getattr(request.app.state, "database", None)  # None without lifespan
        if request.method in WRITE_METHODS and database and await database.in_maintenance():
            return JSONResponse(
                status_code=503,
                content={"error_code": "maintenance", "message": MAINTENANCE_MESSAGE},
            )
        return await call_next(request)

    # F11-AC12: no browser origin may call the API; only the BFF does, server to server.
    # Spelled out on purpose, so nobody "fixes" a CORS error by allowing an origin here.
    app.add_middleware(CORSMiddleware, allow_origins=[], allow_credentials=False)

    app.include_router(documents_router)
    app.include_router(residents_router)
    app.include_router(questions_router)
    # The BFF assertion check reads its secret through this dependency.
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/health")
    def health() -> dict[str, str]:
        # Exposes which providers are active so the demo can show "cloud vs. local".
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider,
            "ocr_provider": settings.ocr_provider,
        }

    @app.get("/health/ready")
    async def ready(request: Request) -> JSONResponse:
        # Keep-alive (F10-AC9): asks the database, so Supabase sees activity and does not
        # pause the free project; 503 tells the workflow that the database is not reachable.
        database = getattr(request.app.state, "database", None)
        try:

            async def ping() -> None:
                async with database.connection() as conn:
                    await conn.execute("select 1")

            await asyncio.wait_for(ping(), timeout=5)
        except Exception:
            return JSONResponse(status_code=503, content={"db": "unavailable"})
        return JSONResponse(content={"db": "ok"})

    @app.get("/me")
    def me(principal: Annotated[Principal, Depends(current_principal)]) -> dict:
        return {
            "sub": principal.sub,
            "app_role": principal.app_role,
            "ward_ids": list(principal.ward_ids),
            "display_name": principal.display_name,
        }

    return app


# Module-level instance for uvicorn: `uvicorn app.main:app`
app = create_app()
