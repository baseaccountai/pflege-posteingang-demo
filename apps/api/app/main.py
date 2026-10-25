"""FastAPI application: the security layer between the web app and LLM/OCR/database."""

from fastapi import FastAPI

from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory; reads settings from the environment unless given explicitly."""
    settings = settings or Settings()
    app = FastAPI(title="Pflege-Posteingang API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        # Exposes which providers are active so the demo can show "cloud vs. local".
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider,
            "ocr_provider": settings.ocr_provider,
        }

    return app


# Module-level instance for uvicorn: `uvicorn app.main:app`
app = create_app()
