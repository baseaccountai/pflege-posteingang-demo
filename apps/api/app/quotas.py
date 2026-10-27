"""Daily and per-session quotas (F10-AC10), booked in the database before any paid call.

Several bookings for one action (upload: session upload, OCR pages, LLM call) happen in the
caller's transaction: if one fails, QuotaExceeded rolls the transaction back and the
earlier bookings of the same action disappear too.
"""

from psycopg import AsyncConnection


class QuotaExceeded(Exception):
    """A quota is used up -> HTTP 429 at upload, failed/quota_exceeded during processing."""

    def __init__(self, kind: str):
        super().__init__(f"quota exhausted: {kind}")
        self.kind = kind


async def consume(conn: AsyncConnection, kind: str, amount: int, subject: str = "global") -> None:
    """Books `amount` of `kind` or raises QuotaExceeded (nothing is booked then)."""
    cur = await conn.execute("select app.consume_quota(%s, %s, %s)", [kind, subject, amount])
    if not (await cur.fetchone())[0]:
        raise QuotaExceeded(kind)
