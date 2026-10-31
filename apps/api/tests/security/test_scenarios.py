"""F13-AC4: scenarios through the whole API (test IdP, RLS, real screener, fake models).

The two prepared sample letters of F07-AC12 are uploaded as files, exactly as a visitor
of the demo would: each must end with its findings, and the field suggestion must not see
the attack. Every text that leaves for a model on the way - checker, suggestion,
embeddings - must carry placeholders instead of the residents' names (F06).

The agent scenarios of F13-AC4 (document instruction, question about WB2) follow with F08.
"""

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.llm.fake import FakeLlm
from app.providers.ocr.fake import FakeOcr
from tests.rls.conftest import ADMIN_DSN, GATEWAY_DSN, seeded  # noqa: F401 (fixture)
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


def admin(sql: str, params: list | None = None) -> None:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(sql, params)


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
