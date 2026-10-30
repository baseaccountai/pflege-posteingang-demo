"""A stand-in for the injection check in pipeline tests (F07): every page is clean,
unless the test gives a result or an error. It records the document status at the call."""

from app.security.screening import Screening


class FakeScreener:
    model_name = "fake-guard"

    def __init__(
        self, error: Exception | None = None, result: Screening | None = None, status=None
    ):
        self.error = error
        self.result = result
        self.status = status  # callable(document_id) -> status at call time, optional
        self.calls: list[tuple[list, bytes | None]] = []
        self.statuses: list[str] = []

    async def __call__(self, principal, pages, pdf):
        self.calls.append((pages, pdf))
        if self.error:
            raise self.error
        return self.result or Screening("clean", pages, [])
