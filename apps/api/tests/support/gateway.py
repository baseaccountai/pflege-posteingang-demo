"""A model gateway for tests: given providers, the residents of the test database."""

from app.privacy.gateway import ModelGateway, database_directory, database_visible
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.llm.fake import FakeLlm


def db_gateway(db, llm=None, embeddings=None) -> ModelGateway:
    return ModelGateway(
        llm or FakeLlm(),
        embeddings or FakeEmbeddings(),
        database_directory(db),
        database_visible(db),
    )
