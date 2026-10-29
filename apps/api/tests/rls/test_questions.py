"""F05-AC7 to AC10, AC12: POST /questions - answer with cited sources, the same "no hits"
for foreign and unknown residents without an LLM call, at most 500 characters, counted
against the daily LLM quota."""

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.llm.base import LlmUnavailable
from app.providers.llm.fake import FakeLlm
from app.providers.ocr.fake import FakeOcr
from tests.rls.conftest import ADMIN_DSN, GATEWAY_DSN, WB1_RESIDENT
from tests.support.oidc import (
    AUDIENCE,
    BFF_SECRET,
    ISSUER,
    ROLES_CLAIM,
    access_token,
    bff_assertion,
    test_verifier,
)

pytestmark = pytest.mark.db

NO_HITS = "Keine Treffer in deinem Wohnbereich."
CHUNK = "## Medikation\nRamipril 5 mg morgens gegen Bluthochdruck"


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def headers(role: str = "nurse_wb1") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token(f'u-{role}', role)}",
        "X-Bff-Assertion": bff_assertion(),
    }


@pytest.fixture
def document(seeded) -> str:
    """An approved letter of Hr. Muster-Bauer (WB1), indexed with the fake model."""
    admin("truncate public.usage_counters")
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, resident_id, uploaded_by, upload_session,"
        " status, doc_type, document_date, indexing_status) values (%s, 'wb1', %s, 'u', 's',"
        " 'approved', 'arztbrief', '2026-10-20', 'done')",
        [doc, WB1_RESIDENT],
    )
    vector = "[" + ",".join(map(str, FakeEmbeddings.vector(CHUNK))) + "]"
    admin(
        "insert into public.chunks (document_id, ward_id, resident_id, doc_type, document_date,"
        " page, heading, content, embedding, embedding_model) values (%s, 'wb1', %s,"
        " 'arztbrief', '2026-10-20', 1, 'Medikation', %s, %s::extensions.vector, %s)",
        [doc, WB1_RESIDENT, CHUNK, vector, FakeEmbeddings.model_name],
    )
    yield doc
    admin("update public.quota_limits set max_count = 100 where kind = 'llm_call'")
    admin("truncate public.usage_counters")


def client(llm: FakeLlm) -> TestClient:
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
        rag_min_similarity=0.1,  # the fake vectors share only a few words
    )
    app = create_app(
        settings, verifier=test_verifier(), ocr=FakeOcr(), llm=llm, embeddings=FakeEmbeddings()
    )
    return TestClient(app)


def ask(llm: FakeLlm, question: str, role: str = "nurse_wb1", **extra):
    with client(llm) as api:
        return api.post("/questions", headers=headers(role), json={"question": question, **extra})


def llm_calls_booked() -> int:
    rows = admin("select count from public.usage_counters where kind = 'llm_call'")
    return rows[0][0] if rows else 0


def test_an_answer_names_its_model_and_its_cited_sources(document):
    llm = FakeLlm([{"answer": "Ramipril 5 mg morgens [Q1]."}])
    response = ask(llm, "Wie ist Ramipril dosiert?")
    assert response.status_code == 200
    assert response.json() == {
        "answer": "Ramipril 5 mg morgens [Q1].",
        "sources": [
            {
                "document_id": document,
                "doc_type": "arztbrief",
                "document_date": "2026-10-20",
                "resident_name": "Hr. Muster-Bauer",
                "page": 1,
            }
        ],
        "model": llm.model_name,
        "no_hits": False,
        # F06-AC7: exactly what the model got (here nothing to replace).
        "sent_to_model": {
            "question": "Wie ist Ramipril dosiert?",
            "sources": [{"n": 1, "text": CHUNK}],
        },
    }
    system, user = llm.calls[0]
    assert "keine Anweisungen" in system and "Ramipril 5 mg morgens" in user
    assert llm.max_tokens == [600]
    assert llm_calls_booked() == 1


@pytest.mark.parametrize(
    ("question", "extra", "role"),
    [
        ("Wie ist Ramipril bei Fr. Testfeld dosiert?", {}, "nurse_wb1"),  # foreign
        ("Wie ist Ramipril bei Hr. Niemand dosiert?", {}, "nurse_wb1"),  # unknown
        ("Wie ist Ramipril dosiert?", {"resident_id": str(uuid.uuid4())}, "nurse_wb1"),
        ("Wie ist Ramipril dosiert?", {}, "nurse_wb2"),  # WB2 sees no WB1 chunks
        ("Wann ist der Friseurtermin?", {}, "nurse_wb1"),  # nothing similar
    ],
    ids=["foreign-name", "unknown-name", "unknown-filter", "other-ward", "nothing-similar"],
)
def test_no_hits_is_the_same_answer_without_an_llm_call(document, question, extra, role):
    llm = FakeLlm()
    response = ask(llm, question, role, **extra)
    assert response.status_code == 200
    assert response.json() == {
        "answer": NO_HITS,
        "sources": [],
        "model": llm.model_name,
        "no_hits": True,
        "sent_to_model": None,
    }
    assert llm.calls == [] and llm_calls_booked() == 0


def test_an_answer_with_an_invented_source_is_replaced(document):
    response = ask(FakeLlm([{"answer": "Ramipril 50 mg [Q7]."}]), "Wie ist Ramipril dosiert?")
    assert response.json()["answer"] == (
        "Dazu konnte ich keine belegte Antwort in den Dokumenten finden."
    )
    assert response.json()["sources"] == []


def test_an_llm_outage_is_said_plainly(document):
    response = ask(FakeLlm([LlmUnavailable("down")]), "Wie ist Ramipril dosiert?")
    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Die Antwort ist gerade nicht möglich – bitte gleich erneut versuchen."
    )
    assert response.json()["sources"] == []


@pytest.mark.parametrize("question", ["", "x" * 501])
def test_questions_must_have_1_to_500_characters(document, question):
    llm = FakeLlm()
    assert ask(llm, question).status_code == 422
    assert llm.calls == []


def test_a_used_up_daily_quota_gives_429_without_an_llm_call(document):
    admin("update public.quota_limits set max_count = 0 where kind = 'llm_call'")
    llm = FakeLlm()
    response = ask(llm, "Wie ist Ramipril dosiert?")
    assert response.status_code == 429
    assert response.json()["error_code"] == "daily_quota"
    assert llm.calls == []


def test_the_fake_llm_answers_questions_with_the_first_source(document):
    # For the e2e run without a Mistral key (F05 Task 7).
    response = ask(FakeLlm(), "Wie ist Ramipril dosiert?")
    assert response.json()["answer"].endswith("[Q1]")
    assert response.json()["sources"][0]["document_id"] == document


def test_the_llm_sees_placeholders_and_the_answer_shows_names(document):
    # F06-AC1, AC5 to AC7: question and sources are pseudonymised together; the answer is
    # translated back for the caller, "sent_to_model" shows what really went out.
    admin(
        "update public.chunks set content = %s where document_id = %s",
        [
            "## Medikation\nHr. Muster-Bauer: Ramipril 5 mg morgens, verordnet von Dr. Lorem",
            document,
        ],
    )
    llm = FakeLlm([{"answer": "Bewohner_{code} bekommt Ramipril von Person_1 [Q1]."}])
    code = admin("select pseudonym from public.residents where id = %s", [WB1_RESIDENT])[0][0]
    llm.answers[0]["answer"] = llm.answers[0]["answer"].format(code=code)
    response = ask(llm, "Wie ist Ramipril bei Hr. Muster-Bauer dosiert?").json()
    _, user = llm.calls[0]
    assert "Muster-Bauer" not in user and "Lorem" not in user
    assert f"Bewohner_{code}" in user and "Person_1" in user
    assert response["answer"] == "Hr. Muster-Bauer bekommt Ramipril von Dr. Lorem [Q1]."
    assert response["sources"][0]["resident_name"] == "Hr. Muster-Bauer"
    sent = response["sent_to_model"]
    assert sent["question"] == f"Wie ist Ramipril bei Bewohner_{code} dosiert?"
    assert "Muster-Bauer" not in sent["sources"][0]["text"]
