"""F06-AC1, AC10: the gateway is the door to the models and refuses plain names."""

from datetime import date

import pytest

from app.privacy.gateway import ModelGateway, PseudonymizationFailed
from app.privacy.pseudonymizer import KnownResident

pytestmark = pytest.mark.anyio

RESIDENTS = [KnownResident("r1", "K42", "Hr. Muster-Bauer", date(1941, 4, 3))]


class RecordingLlm:
    model_name = "fake-llm"

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def structured(self, system, user, schema, max_tokens):
        self.calls.append((system, user))
        return {"answer": "ok"}


class RecordingEmbeddings:
    model_name = "fake-embed"
    dimension = 1024

    def __init__(self):
        self.calls: list[list[str]] = []

    async def embed(self, texts):
        self.calls.append(texts)
        return [[0.0] * 1024 for _ in texts]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def loads():
    return []


@pytest.fixture
def gateway(loads):
    async def directory():
        loads.append(1)
        return RESIDENTS

    async def visible(principal):
        return {"r1"}

    return ModelGateway(RecordingLlm(), RecordingEmbeddings(), directory, visible)


async def test_pseudonymized_text_reaches_the_model(gateway):
    assert await gateway.structured("System", "Frage zu Bewohner_K42", {}, 100) == {"answer": "ok"}
    assert gateway.llm.calls == [("System", "Frage zu Bewohner_K42")]
    assert await gateway.embed(["Bewohner_K42 bekommt Ramipril"])
    assert gateway.embeddings.calls == [["Bewohner_K42 bekommt Ramipril"]]


@pytest.mark.parametrize("user", ["Frage zu Hr. Muster-Bauer", "geb. 03.04.1941"])
async def test_a_plain_name_or_birth_date_stops_the_llm_call(gateway, user):
    with pytest.raises(PseudonymizationFailed):
        await gateway.structured("System", user, {}, 100)
    assert gateway.llm.calls == []


async def test_a_plain_name_in_the_system_prompt_stops_the_call_too(gateway):
    with pytest.raises(PseudonymizationFailed):
        await gateway.structured("Antworte über Muster-Bauer", "Frage", {}, 100)
    assert gateway.llm.calls == []


async def test_a_plain_name_stops_the_embedding_call(gateway):
    with pytest.raises(PseudonymizationFailed):
        await gateway.embed(["Bewohner_K42", "Muster-Bauer klagt über Schwindel"])
    assert gateway.embeddings.calls == []


async def test_the_directory_is_loaded_once_and_reused(gateway, loads):
    first = await gateway.pseudonymizer()
    second = await gateway.pseudonymizer()
    assert first is second and loads == [1]


async def test_the_model_names_come_from_the_providers(gateway):
    assert (gateway.llm_model, gateway.embedding_model) == ("fake-llm", "fake-embed")
