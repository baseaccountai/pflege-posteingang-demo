"""LLM stand-in for tests and the e2e run without a Mistral key (LLM_PROVIDER=fake).

With prepared answers it returns them in order (tests). Without, it reads the document in
the prompt with simple rules - enough for the sample documents in samples/ - and quotes
every value verbatim, like a well-behaved model would.
"""

import re

DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
PERSON = re.compile(r"\b(?:Hr|Fr)\. [\w-]+")
SLOTS = ("morgens", "mittags", "abends", "nachts")


def _iso(match: re.Match) -> str:
    day, month, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _field(value, evidence):
    return {"value": value, "evidence": evidence if value is not None else None}


def read_document(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    heading = next((ln.lstrip("# ") for ln in lines if ln.startswith("# ")), "")
    lower = heading.casefold()
    doc_type = (
        "medikationsplan" if "medikationsplan" in lower
        else "ueberleitungsbogen" if "überleitung" in lower
        else "arztbrief" if "brief" in lower
        else "sonstiges"
    )  # fmt: skip
    date_line = next((ln for ln in lines if DATE.search(ln)), None)
    issuer_line = next(
        (ln for ln in lines if re.search(r"Klinikum|Praxis|Pflegeheim", ln) and DATE.search(ln)),
        None,
    )
    person_line = next(
        (ln for ln in lines if re.search(r"Patient|Für|Bewohner", ln) and PERSON.search(ln)), None
    )

    diagnoses, section = [], ""
    medications, follow_ups = [], []
    for line in lines:
        if line.startswith("#"):
            section = line.lstrip("# ").casefold()
            continue
        if section.startswith("diagnose") and line.startswith("- "):
            diagnoses.append(_field(line[2:], line))
        cells = [c.strip() for c in line.strip("|").split("|")] if line.startswith("|") else []
        if len(cells) == 3 and cells[0] != "Medikament" and not cells[0].startswith("---"):
            amounts = cells[2].split("-")
            dosage = dict(zip(SLOTS, amounts + ["0"] * (4 - len(amounts)), strict=False))
            medications.append(
                {
                    "name": cells[0],
                    "strength": cells[1],
                    "dosage": dosage,
                    "hint": None,
                    "evidence": line,
                }
            )
        if re.match(r"(Kontrolle|Wiedervorlage)", line):
            title = re.split(r" am | in |\.$", line.removeprefix("Wiedervorlage: "))[0]
            due = DATE.search(line)
            follow_ups.append(
                {"title": title, "due_date": _iso(due) if due else None, "evidence": line}
            )

    return {
        "doc_type": _field(doc_type if heading else None, heading or None),
        "document_date": _field(_iso(DATE.search(date_line)) if date_line else None, date_line),
        "issuer": _field(issuer_line.split(",")[0] if issuer_line else None, issuer_line),
        "resident_name": _field(
            PERSON.search(person_line).group(0) if person_line else None, person_line
        ),
        "diagnoses": diagnoses,
        "medications": medications,
        "follow_ups": follow_ups,
    }


class FakeLlm:
    model_name = "fake-llm (Testattrappe)"

    def __init__(self, answers: list[dict | Exception] | None = None):
        self.answers = list(answers or [])
        self.calls: list[tuple[str, str]] = []

    async def structured(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        self.calls.append((system, user))
        if self.answers:
            answer = self.answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        document = user.split("<<<DOKUMENT", 1)[-1].rsplit("DOKUMENT>>>", 1)[0]
        return read_document(document)
