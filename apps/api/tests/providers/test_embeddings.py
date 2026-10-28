"""F05-AC13: embedding providers by configuration (Mistral public, Ollama local, fake for
tests), always 1024 dimensions; adapters tested against stand-ins of the APIs (respx)."""

import json
import math

import httpx
import pytest
import respx

from app.config import Settings
from app.providers.embeddings import create_embedding_provider
from app.providers.embeddings.base import DIMENSION, EmbeddingUnavailable
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.embeddings.mistral import BATCH_SIZE, EMBEDDINGS_URL, MistralEmbeddings
from app.providers.embeddings.ollama import OllamaEmbeddings

pytestmark = pytest.mark.anyio

KEY = "test-key-not-real"


def vector(seed: float) -> list[float]:
    return [seed] * DIMENSION


def mistral_answer(vectors: list[list[float]], order: list[int] | None = None) -> dict:
    order = order if order is not None else list(range(len(vectors)))
    return {
        "object": "list",
        "model": "mistral-embed",
        "data": [{"object": "embedding", "index": i, "embedding": vectors[i]} for i in order],
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
    }


@pytest.mark.parametrize(
    ("provider", "cls", "model"),
    [
        ("mistral", MistralEmbeddings, "mistral-embed"),
        ("ollama", OllamaEmbeddings, "bge-m3"),
        ("fake", FakeEmbeddings, "fake-embed"),
    ],
)
def test_provider_follows_llm_provider_and_has_1024_dimensions(provider, cls, model):
    embeddings = create_embedding_provider(Settings(llm_provider=provider, mistral_api_key=KEY))
    assert isinstance(embeddings, cls)
    assert embeddings.dimension == DIMENSION == 1024
    assert embeddings.model_name.startswith(model)


@respx.mock
async def test_mistral_sends_model_and_texts_and_keeps_the_order():
    route = respx.post(EMBEDDINGS_URL).mock(
        return_value=httpx.Response(200, json=mistral_answer([vector(0.1), vector(0.2)], [1, 0]))
    )
    result = await MistralEmbeddings(KEY).embed(["erster", "zweiter"])
    assert result == [vector(0.1), vector(0.2)]  # by "index", not by position in the answer
    request = route.calls[0].request
    assert json.loads(request.content) == {"model": "mistral-embed", "input": ["erster", "zweiter"]}
    assert request.headers["authorization"] == f"Bearer {KEY}"


@respx.mock
async def test_mistral_sends_large_inputs_in_batches():
    def answer(request):
        texts = json.loads(request.content)["input"]
        return httpx.Response(200, json=mistral_answer([vector(len(t)) for t in texts]))

    route = respx.post(EMBEDDINGS_URL).mock(side_effect=answer)
    texts = ["x" * (i + 1) for i in range(BATCH_SIZE + 5)]
    result = await MistralEmbeddings(KEY).embed(texts)
    assert len(route.calls) == 2
    assert [len(json.loads(c.request.content)["input"]) for c in route.calls] == [BATCH_SIZE, 5]
    assert [v[0] for v in result] == [len(t) for t in texts]


async def test_no_texts_no_request():
    assert await MistralEmbeddings(KEY).embed([]) == []


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"message": "boom"}),
        httpx.Response(429, json={"message": "rate limit"}),
        httpx.Response(200, json={"unexpected": True}),
        httpx.Response(200, json=mistral_answer([[0.1] * 3])),  # wrong dimension
        httpx.Response(200, json=mistral_answer([])),  # wrong count
    ],
    ids=["500", "429", "shape", "dimension", "count"],
)
async def test_mistral_failures_become_unavailable_without_the_key(response):
    respx.post(EMBEDDINGS_URL).mock(return_value=response)
    with pytest.raises(EmbeddingUnavailable) as error:
        await MistralEmbeddings(KEY).embed(["text"])
    assert KEY not in str(error.value)


@respx.mock
async def test_mistral_timeout_and_missing_key_become_unavailable():
    respx.post(EMBEDDINGS_URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(EmbeddingUnavailable):
        await MistralEmbeddings(KEY).embed(["text"])
    with pytest.raises(EmbeddingUnavailable):
        await MistralEmbeddings("").embed(["text"])


@respx.mock
async def test_ollama_uses_the_local_embed_endpoint():
    route = respx.post("http://ollama:11434/api/embed").mock(
        return_value=httpx.Response(200, json={"model": "bge-m3", "embeddings": [vector(0.3)]})
    )
    result = await OllamaEmbeddings("http://ollama:11434", "bge-m3").embed(["lokal"])
    assert result == [vector(0.3)]
    assert json.loads(route.calls[0].request.content) == {"model": "bge-m3", "input": ["lokal"]}


@respx.mock
async def test_ollama_with_a_model_of_another_dimension_is_refused():
    respx.post("http://ollama:11434/api/embed").mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.1] * 768]})
    )
    with pytest.raises(EmbeddingUnavailable):
        await OllamaEmbeddings("http://ollama:11434", "nomic-embed-text").embed(["x"])


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_fake_vectors_are_deterministic_normalised_and_word_based():
    fake = FakeEmbeddings()
    a, again, related, other = await fake.embed(
        [
            "Ramipril 5 mg morgens",
            "Ramipril 5 mg morgens",
            "Wie hoch ist Ramipril dosiert?",
            "Termin Orthopädie vereinbaren",
        ]
    )
    assert a == again and len(a) == DIMENSION
    assert math.isclose(sum(x * x for x in a), 1.0)
    assert cosine(a, related) > cosine(a, other)
