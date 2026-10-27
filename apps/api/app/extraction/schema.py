"""Fixed answer schema of the field suggestion (F03-AC1).

Every value comes with `evidence`: the verbatim passage of the OCR text it was taken from.
All fields are required (null where nothing was found), so the schema can be enforced
strictly by the model provider and is checked here again with Pydantic.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

DocType = Literal["arztbrief", "medikationsplan", "ueberleitungsbogen", "sonstiges"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextField(Strict):
    value: str | None
    evidence: str | None


class DocTypeField(Strict):
    value: DocType | None
    evidence: str | None


class Dosage(Strict):
    morgens: str | None
    mittags: str | None
    abends: str | None
    nachts: str | None


class Medication(Strict):
    name: str
    strength: str | None
    dosage: Dosage
    hint: str | None
    evidence: str | None


class FollowUp(Strict):
    title: str
    due_date: str | None  # YYYY-MM-DD
    evidence: str | None


class DocumentSuggestion(Strict):
    doc_type: DocTypeField
    document_date: TextField  # YYYY-MM-DD
    issuer: TextField
    resident_name: TextField
    diagnoses: list[TextField]
    medications: list[Medication]
    follow_ups: list[FollowUp]


SCHEMA = DocumentSuggestion.model_json_schema()
