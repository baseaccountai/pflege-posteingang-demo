"""FastAPI application: the security layer between the web app and LLM/OCR/database."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.auth.dependencies import current_principal, principal_db
from app.auth.principal import Principal
from app.auth.tokens import TokenVerifier
from app.config import Settings, get_settings
from app.db import Database

NOT_FOUND = HTTPException(status_code=404, detail="Nicht gefunden")
RESIDENT_COLUMNS = "id::text, ward_id, display_name, room"


def create_app(settings: Settings | None = None, verifier: TokenVerifier | None = None) -> FastAPI:
    """Application factory; reads settings from the environment unless given explicitly.

    `verifier` replaces the JWKS-based token check in tests (test IdP).
    """
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.verifier = verifier
        if app.state.verifier is None and settings.oidc_issuer:
            app.state.verifier = TokenVerifier.from_issuer(
                settings.oidc_issuer, settings.oidc_audience
            )
        app.state.database = Database(settings.database_url) if settings.database_url else None
        if app.state.database:
            await app.state.database.open()
        try:
            yield
        finally:
            if app.state.database:
                await app.state.database.close()

    app = FastAPI(title="Pflege-Posteingang API", version="0.1.0", lifespan=lifespan)
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

    @app.get("/me")
    def me(principal: Annotated[Principal, Depends(current_principal)]) -> dict:
        return {
            "sub": principal.sub,
            "app_role": principal.app_role,
            "ward_ids": list(principal.ward_ids),
            "display_name": principal.display_name,
        }

    @app.get("/residents")
    async def residents(conn: Annotated[AsyncConnection, Depends(principal_db)]) -> list[dict]:
        # No ward filter here on purpose: RLS decides which rows exist for this caller.
        cursor = conn.cursor(row_factory=dict_row)
        await cursor.execute(
            f"select {RESIDENT_COLUMNS} from public.residents order by display_name"
        )
        return await cursor.fetchall()

    @app.get("/residents/{resident_id}")
    async def resident(
        resident_id: str, conn: Annotated[AsyncConnection, Depends(principal_db)]
    ) -> dict:
        # Malformed, unknown and foreign IDs all get the same 404 (F01-AC12).
        try:
            uuid.UUID(resident_id)
        except ValueError as error:
            raise NOT_FOUND from error
        cursor = conn.cursor(row_factory=dict_row)
        await cursor.execute(
            f"select {RESIDENT_COLUMNS} from public.residents where id = %s", [resident_id]
        )
        row = await cursor.fetchone()
        if row is None:
            raise NOT_FOUND
        return row

    return app


# Module-level instance for uvicorn: `uvicorn app.main:app`
app = create_app()
