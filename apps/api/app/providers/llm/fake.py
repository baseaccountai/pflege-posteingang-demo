"""LLM stand-in for tests and the e2e run without a Mistral key (LLM_PROVIDER=fake).

With prepared answers it returns them in order (tests). Without, it reads the document in
the prompt with simple rules - enough for the sample documents in samples/ - and quotes
every value verbatim, like a well-behaved model would. A question (schema with "answer",
F05) is answered with the first text line of source Q1 and cites it.
"""

import re

from app.providers.llm.base import ChatTurn, Message, ToolCall

DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
PERSON = re.compile(r"\b(?:Hr|Fr)\. [\w-]+|\bBewohner_[A-Z]\d{2}\b")  # name or its code (F06)
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

    def __init__(
        self,
        answers: list[dict | Exception] | None = None,
        turns: list[ChatTurn | Exception] | None = None,
    ):
        self.answers = list(answers or [])
        self.turns = list(turns or [])  # the agent's script (F08): one entry per model call
        self.calls: list[tuple[str, str]] = []
        self.chats: list[list[Message]] = []  # the conversation as the model saw it each time
        self.max_tokens: list[int] = []  # the output limit of every call (F10-AC11)

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict], max_tokens: int
    ) -> ChatTurn:
        self.chats.append(list(messages))  # a copy: the runner appends to its list
        self.max_tokens.append(max_tokens)
        if self.turns:
            turn = self.turns.pop(0)
            if isinstance(turn, Exception):
                raise turn
            return turn
        return agent_turn(messages)

    async def structured(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        self.calls.append((system, user))
        self.max_tokens.append(max_tokens)
        if self.answers:
            answer = self.answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        if "answer" in schema.get("properties", {}):
            return answer_question(user)
        if "flagged" in schema.get("properties", {}):
            return judge_sections(user)
        document = user.split("<<<DOKUMENT", 1)[-1].rsplit("DOKUMENT>>>", 1)[0]
        return read_document(document)


FIRST_SOURCE = re.compile(r'<quelle id="Q1"[^>]*>\n(.*?)\n</quelle>', re.S)


def answer_question(user: str) -> dict:
    """The first line of source Q1 that is not a heading, cited as [Q1]."""
    match = FIRST_SOURCE.search(user)
    lines = [line.strip() for line in (match.group(1) if match else "").splitlines()]
    text = next((line for line in lines if line and not line.startswith("#")), "")
    return {"answer": f"{text} [Q1]" if text else "Dazu steht nichts in den Quellen."}


SECTION = re.compile(r'<abschnitt nr="(\d+)">\n(.*?)\n</abschnitt>', re.S)
# The fake injection checker (F07): obvious orders to an AI, nothing more.
ORDERS = re.compile(r"ki-system|ignorier|wartungsmodus|vorrang vor allen regeln", re.I)


def judge_sections(user: str) -> dict:
    sections = SECTION.findall(user)
    return {
        "checked": len(sections),
        "flagged": [
            {"section": int(n), "category": "fake", "reason": "Anweisung an die KI"}
            for n, text in sections
            if ORDERS.search(text)
        ],
    }


# --- the agent without a script (F08, e2e): one tool step chosen by simple rules -----------

RESIDENT_LINE = re.compile(r"Bewohner_(\w+) \(bewohner_id ([\w-]+)\)")
CHOSEN = re.compile(r"Ausgewählter Bewohner: Bewohner_\w+ \(bewohner_id ([\w-]+)\)")
CANNOT = re.compile(r"\b(?:änder|lösch|send|schick)", re.I)
TOOL_WORDS = {
    "dokumente_durchsuchen": "die Dokumente durchsucht",
    "bewohnerakte_lesen": "die Bewohnerakte gelesen",
    "medikation_abgleichen": "die Medikation abgeglichen",
    "wiedervorlagen_auflisten": "die Wiedervorlagen aufgelistet",
}
NOTHING = "Dazu gibt es in deinem Wohnbereich nichts – der Agent hat dieselben Rechte wie du."


def agent_turn(messages: list[Message]) -> ChatTurn:
    """First turn: a tool by the words of the task; after a tool result: a short answer."""
    last = messages[-1]
    if last["role"] == "tool":
        return ChatTurn(content=_after_tool(last["name"], last["content"]))
    user = messages[1]["content"] if len(messages) > 1 else ""
    text = user.rsplit("Auftrag:", 1)[-1].strip()
    if CANNOT.search(text):
        return ChatTurn(
            content="Das kann ich nicht: Ich darf nichts in der Akte ändern, löschen oder senden. "
            "Ich kann aber eine Wiedervorlage „Dosis mit Hausarzt klären“ vorschlagen."
        )
    resident = _resident(user, text)
    if resident and "wiedervorlage" in text.casefold():
        title = text.split(":", 1)[1].strip() if ":" in text else "Kontrolle laut Auftrag"
        call = ToolCall(
            "fake_1", "wiedervorlage_vorschlagen", {"bewohner_id": resident, "titel": title}
        )
    elif resident:
        call = ToolCall("fake_1", "bewohnerakte_lesen", {"bewohner_id": resident})
    else:
        call = ToolCall("fake_1", "wiedervorlagen_auflisten", {})
    return ChatTurn(content="", tool_calls=[call])


def _resident(user: str, text: str) -> str | None:
    """The chosen resident, else the first own resident whose placeholder is in the task."""
    chosen = CHOSEN.search(user)
    if chosen:
        return chosen.group(1)
    ids = dict(RESIDENT_LINE.findall(user.split("Auftrag:", 1)[0]))
    return next((ids[code] for code in re.findall(r"Bewohner_(\w+)", text) if code in ids), None)


def _after_tool(tool: str, content: str) -> str:
    if content == "nicht erlaubt":
        return "Das Werkzeug war nicht erlaubt."
    if tool == "wiedervorlage_vorschlagen" and '"gefunden": true' in content:
        return "Ich habe eine Wiedervorlage vorgeschlagen – bitte bestätigen oder verwerfen."
    if '"gefunden": false' in content or re.search(r'": \[\]', content):
        return NOTHING
    return f"Ich habe {TOOL_WORDS.get(tool, 'ein Werkzeug genutzt')} (Testattrappe)."
