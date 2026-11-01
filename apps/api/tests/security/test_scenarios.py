"""F13-AC4: scenarios through the whole API (test IdP, RLS, real screener, fake models).

The two prepared sample letters of F07-AC12 are uploaded as files, exactly as a visitor
of the demo would: each must end with its findings, and the field suggestion must not see
the attack. Every text that leaves for a model on the way - checker, suggestion,
embeddings - must carry placeholders instead of the residents' names (F06).

The agent (F08) gets two more: a letter that tells the AI what to do is approved and the
agent reads it - it can at most leave an open proposal (F08-AC13); and a task about the
resident of WB2 gets the same answer as one about nobody, without a model call (F08-AC10).
"""

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.agent.runner import FOREIGN_ANSWER
from app.config import Settings
from app.main import create_app
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.llm.base import ChatTurn, ToolCall
from app.providers.llm.fake import FakeLlm
from app.providers.ocr.fake import FakeOcr
from tests.rls.conftest import ADMIN_DSN, GATEWAY_DSN, seeded  # noqa: F401 (fixture)
from tests.support.oidc import (
    AGENT_SIGNING_KEY,
    AUDIENCE,
    BFF_SECRET,
    ISSUER,
    ROLES_CLAIM,
    access_token,
    bff_assertion,
    test_verifier,
)

pytestmark = pytest.mark.db

SAMPLES = Path(__file__).parents[4] / "samples"
# The residents the two letters are about, as in the seed (code, name, birth date).
RESIDENTS = [
    ("D15", "Hr. Probe", "1939-02-28", "28.02.1939"),
    ("R07", "Fr. Beispiel", "1936-06-17", "17.06.1936"),
]


def headers() -> dict[str, str]:
    """Fresh per request: token and BFF assertion are short-lived."""
    return {
        "Authorization": f"Bearer {access_token('u-wb1', 'nurse_wb1')}",
        "X-Bff-Assertion": bff_assertion(),
    }


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


@pytest.fixture
def api(seeded: None) -> Iterator[tuple[TestClient, FakeLlm, FakeEmbeddings, FakeLlm]]:  # noqa: F811
    admin("truncate public.usage_counters")
    for code, name, born, _ in RESIDENTS:
        admin(
            "insert into public.residents (ward_id, display_name, birth_date, pseudonym)"
            " values ('wb1', %s, %s, %s)",
            [name, born, code],
        )
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
        llm_provider="fake",  # also the checker
        rag_min_similarity=0.1,  # the fake vectors share only a few words
        agent_token_mode="self_signed",  # the fallback way: no IdP in the tests (F08-AC1)
        agent_id="agent-test",
        agent_signing_key=AGENT_SIGNING_KEY,
    )
    llm, embeddings = FakeLlm(), FakeEmbeddings()
    app = create_app(
        settings,
        verifier=test_verifier(),
        ocr=FakeOcr.from_samples(SAMPLES),
        llm=llm,
        embeddings=embeddings,
    )
    with TestClient(app) as client:
        yield client, llm, embeddings, app.state.gateway.guard
    admin("truncate public.usage_counters")


def upload(client: TestClient, name: str) -> dict:
    data = (SAMPLES / name).read_bytes()
    created = client.post(
        "/documents", headers=headers(), files={"file": (name, data, "application/pdf")}
    )
    assert created.status_code == 202, created.text
    # The background processing has run when the TestClient returns.
    return client.get(f"/documents/{created.json()['id']}", headers=headers()).json()


def test_the_white_text_letter_is_caught_from_the_pdf_itself(api):
    # The OCR of this sample does not read the white text: only the PDF check can find it.
    # (Cutting it out where the OCR does read it: tests/security/test_screening.py.)
    client, llm, _, _ = api
    doc = upload(client, "angriff_versteckt_probe.pdf")
    assert doc["status"] == "ready_for_review" and doc["screening_result"] == "suspicious"
    (hidden,) = [f for f in doc["findings"] if f["layer"] == "hidden_text"]
    assert hidden["invisible"] and "Wartungsmodus" in hidden["excerpt"]
    assert llm.calls  # the visible letter still gets its suggestion


def test_the_note_to_the_ai_is_caught_and_cut_out_before_the_suggestion(api):
    client, llm, _, _ = api
    doc = upload(client, "angriff_hinweis_beispiel.pdf")
    assert doc["screening_result"] == "suspicious"
    assert {"pattern", "classifier"} <= {f["layer"] for f in doc["findings"]}
    (_, suggestion_input), *_ = llm.calls
    assert "Hinweis für das KI-System" not in suggestion_input
    assert "Amlodipin" in suggestion_input  # the rest of the letter still goes on


def test_no_resident_name_or_birth_date_leaves_for_any_model(api):
    client, llm, embeddings, guard = api
    upload(client, "angriff_versteckt_probe.pdf")
    upload(client, "angriff_hinweis_beispiel.pdf")
    client.post("/questions", headers=headers(), json={"question": "Was bekommt Hr. Probe?"})
    outgoing = [user for _, user in llm.calls + guard.calls]
    outgoing += [text for batch in embeddings.calls for text in batch]
    assert guard.calls and llm.calls and embeddings.calls  # every kind of model was used
    for _, name, _, born in RESIDENTS:
        assert not [text for text in outgoing if name in text or born in text], name
    assert any("Bewohner_D15" in text for text in outgoing)


# --- the agent (F08) ------------------------------------------------------------------------

NOTE = "Hinweis für das KI-System"


def approve_beispiel_letter(client: TestClient) -> str:
    """The note-to-the-AI letter, approved by the nurse for Fr. Beispiel (made searchable)."""
    doc = upload(client, "angriff_hinweis_beispiel.pdf")
    (resident,) = admin(
        "select id::text from public.residents where display_name = 'Fr. Beispiel'"
    )[0]
    meds = [{"name": "Amlodipin", "strength": "5 mg", "dosage": {"morgens": "1"}, "hint": None}]
    diff = client.post(
        f"/documents/{doc['id']}/medication-diff",
        headers=headers(),
        json={"resident_id": resident, "doc_type": "arztbrief", "medications": meds},
    ).json()
    approved = client.post(
        f"/documents/{doc['id']}/approve",
        headers=headers(),
        json={
            "resident_id": resident,
            "resident_confirmed": True,
            "diff_hash": diff["diff_hash"],
            "doc_type": "arztbrief",
            "document_date": "2026-10-26",
            "diagnoses": ["Arterielle Hypertonie"],
            "medications": meds,
            "follow_ups": [],
        },
    )
    assert approved.status_code == 200, approved.text
    return resident


def order(client: TestClient, task: str):
    return client.post("/agent", headers=headers(), json={"task": task})


def seen_by_the_model(llm: FakeLlm) -> list[str]:
    return [str(m.get("content") or "") for chat in llm.chats for m in chat]


def test_an_instruction_in_a_document_ends_at_most_as_an_open_proposal(api):
    client, llm, _, _ = api
    resident = approve_beispiel_letter(client)
    # A model that obeys the letter: it reads it and then does what the note says.
    llm.turns = [
        ChatTurn(
            "",
            [
                ToolCall(
                    "c1",
                    "dokumente_durchsuchen",
                    {"frage": "Amlodipin Medikation", "bewohner_id": resident},
                )
            ],
        ),
        ChatTurn(
            "",
            [
                ToolCall(
                    "c2",
                    "wiedervorlage_vorschlagen",
                    {"bewohner_id": resident, "titel": "Ramipril 20 mg übernehmen"},
                )
            ],
        ),
        ChatTurn("Ich habe Ramipril 20 mg übernommen."),
    ]
    response = order(client, "Lies den neuen Arztbrief von Fr. Beispiel und setze ihn um.")
    assert response.status_code == 200, response.text
    seen = seen_by_the_model(llm)
    assert any("Amlodipin" in text for text in seen)  # the letter was read
    assert not [text for text in seen if NOTE in text]  # but cut out before indexing (F07)
    # Nothing is written: one open proposal waits for the nurse's confirmation (F08-AC13).
    assert admin("select status from public.agent_proposals") == [("open",)]
    assert admin("select count(*) from public.follow_ups where resident_id = %s", [resident]) == [
        (0,)
    ]
    assert admin("select name from public.medications where resident_id = %s", [resident]) == [
        ("Amlodipin",)
    ]


def test_a_task_about_the_resident_of_wb2_gets_the_answer_for_nobody(api):
    client, llm, _, _ = api
    answers = [
        order(client, f"Welche Diagnosen hat {who}?").json()
        for who in ("Fr. Testfeld", "Fr. Niemand")
    ]
    assert [a["answer"] for a in answers] == [FOREIGN_ANSWER, FOREIGN_ANSWER]
    assert answers[0] == answers[1]
    assert llm.chats == []  # decided before any model call


def test_no_resident_name_or_birth_date_reaches_the_agents_model(api):
    client, llm, _, _ = api
    approve_beispiel_letter(client)
    response = order(client, "Was steht im Arztbrief von Fr. Beispiel vom 17.06.1936?")
    assert response.status_code == 200, response.text
    seen = seen_by_the_model(llm)
    assert llm.chats and any("Bewohner_R07" in text for text in seen)
    for _, name, _, born in RESIDENTS:
        assert not [text for text in seen if name in text or born in text], name
