"""Who is calling: the identity the API acts on behalf of, derived from a verified token."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Principal:
    sub: str
    app_role: Literal["nurse", "pdl"]
    ward_ids: tuple[str, ...]
    display_name: str
    actor_type: Literal["human", "agent"] = "human"

    def as_claims(self) -> dict[str, object]:
        """Claims as Postgres sees them in `request.jwt.claims` (read by the app.* functions)."""
        return {
            "sub": self.sub,
            "app_role": self.app_role,
            "ward_ids": list(self.ward_ids),
            "actor_type": self.actor_type,
            "display_name": self.display_name,
        }
