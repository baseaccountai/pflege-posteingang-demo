"""F11-AC19: `make reindex` only ever reaches the local database - also when the shell has
the cloud admin URL or a DATABASE_URL set (the cloud keeps its mistral-embed chunks)."""

from scripts.reindex import LOCAL_GATEWAY_DSN, connection_strings
from scripts.reset_demo import LOCAL_ADMIN_DSN


def test_the_cloud_urls_of_the_shell_are_ignored(monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_ADMIN_URL", "postgresql://cloud-admin@example.invalid/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://cloud-gateway@example.invalid/db")
    assert connection_strings() == (LOCAL_ADMIN_DSN, LOCAL_GATEWAY_DSN)
    assert "127.0.0.1" in LOCAL_GATEWAY_DSN
