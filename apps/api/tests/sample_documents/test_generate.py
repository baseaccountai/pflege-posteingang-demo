"""F10-AC2, F10-AC3: sample documents are generated reproducibly, carry the MUSTER
watermark and contain only invented names from the script's fixed list."""

import hashlib
import io
import re

import pytest
from PIL import Image
from pypdf import PdfReader

from samples import generate

NAME_PATTERN = re.compile(r"\b(?:Hr|Fr|Dr)\. (?:med\. )?([A-ZÄÖÜ][\w-]+)")


@pytest.fixture(scope="module")
def output(tmp_path_factory):
    target = tmp_path_factory.mktemp("samples")
    generate.generate(target)
    return target


def pdf_text(path) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(path).pages)


def test_required_documents_exist(output):
    names = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    for required in [
        "arztbrief_muster-bauer.pdf",
        "medikationsplan_muster-bauer.pdf",
        "ueberleitungsbogen_testfeld.pdf",
        "arztbrief_muster-bauer_foto.jpg",
        "bad/leere_seite.jpg",
        "bad/unscharf.jpg",
        "bad/schief.jpg",
        "bad/kochrezept.pdf",
    ]:
        assert required in names


def test_every_pdf_page_carries_the_watermark(output):
    for path in output.rglob("*.pdf"):
        for page in PdfReader(path).pages:
            assert "MUSTER" in page.extract_text(), path.name


def test_only_names_from_the_fixed_list_appear(output):
    allowed = set(generate.ALLOWED_NAMES)
    for path in output.rglob("*.pdf"):
        for name in NAME_PATTERN.findall(pdf_text(path)):
            assert name in allowed, f"{path.name}: {name}"
    for place in generate.PLACES:
        assert place in generate.ALLOWED_PLACES


def test_the_photo_is_larger_than_the_upload_limit_edge(output):
    # Needed by the e2e test of the browser downscaling (F02-AC3).
    with Image.open(output / "arztbrief_muster-bauer_foto.jpg") as photo:
        assert max(photo.size) > 2000


def test_expected_ocr_text_exists_for_every_document(output):
    for path in output.rglob("*"):
        if path.suffix in {".pdf", ".jpg"}:
            expected = (
                output / "ocr" / f"{path.relative_to(output).as_posix().replace('/', '__')}.md"
            )
            assert expected.exists(), path.name
    assert (output / "ocr" / "bad__leere_seite.jpg.md").read_text() == ""


def test_the_medication_plan_differs_from_the_record(output):
    # One new, one stopped, one changed medication (F03-AC7 demo).
    record = {m["name"]: m for m in generate.RECORD_MEDICATIONS}
    plan = {m["name"]: m for m in generate.PLAN_MEDICATIONS}
    assert len(plan.keys() - record.keys()) == 1
    assert len(record.keys() - plan.keys()) == 1
    changed = [n for n in plan.keys() & record.keys() if plan[n] != record[n]]
    assert len(changed) == 1


def test_generation_is_reproducible(tmp_path):
    def digests(folder):
        return {
            p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*")
            if p.is_file()
        }

    generate.generate(tmp_path / "a")
    generate.generate(tmp_path / "b")
    assert digests(tmp_path / "a") == digests(tmp_path / "b")


@pytest.mark.parametrize("char", list("äöüÄÖÜß"))
def test_the_image_font_has_german_umlauts(char):
    # A missing glyph is drawn as the same placeholder box as any other missing one.
    font = generate.image_font(44)
    missing = font.getmask("一").getbbox()
    assert font.getmask(char).getbbox() != missing


# --- Seed documents (F10-AC1): older approved documents behind the seeded record ----------
def test_seed_documents_cover_every_resident_and_only_allowed_names():
    residents = {doc["resident"] for doc in generate.SEED_DOCUMENTS}
    assert residents == {name for names in generate.RESIDENTS.values() for name in names}
    allowed = set(generate.ALLOWED_NAMES)
    for doc in generate.SEED_DOCUMENTS:
        for name in NAME_PATTERN.findall("\n".join(doc["lines"])):
            assert name in allowed, f"{doc['id']}: {name}"


def test_seed_sql_is_reproducible_and_carries_watermarked_pdfs():
    sql = generate.seed_sql()
    assert sql == generate.seed_sql()
    for doc in generate.SEED_DOCUMENTS:
        assert doc["id"] in sql
    pdf = generate.pdf_bytes(generate.SEED_DOCUMENTS[0]["lines"])
    assert pdf.startswith(b"%PDF")
    assert "MUSTER" in PdfReader(io.BytesIO(pdf)).pages[0].extract_text()


def test_the_seed_record_of_muster_bauer_is_older_than_the_plan():
    doc = next(d for d in generate.SEED_DOCUMENTS if d["resident"] == "Hr. Muster-Bauer")
    text = "\n".join(doc["lines"])
    for med in generate.RECORD_MEDICATIONS:
        assert f"| {med['name']} | {med['strength']} | {med['dosage']} |" in text


def test_committed_seed_sql_is_up_to_date():
    committed = generate.SEED_SQL_PATH.read_text(encoding="utf-8")
    assert committed == generate.seed_sql(), "run `make samples`"
