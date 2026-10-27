"""Daily and per-session quotas (F10-AC10). The atomic booking follows with F10 task 4."""


class QuotaExceeded(Exception):
    """A quota is used up -> HTTP 429 at upload, failed/quota_exceeded during processing."""
