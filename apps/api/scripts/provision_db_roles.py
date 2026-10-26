"""Give the login roles `api_gateway` and `bff_session` fresh random passwords.

Run by the developer, never in CI:

    cd apps/api && uv run python -m scripts.provision_db_roles ../../.env

Reads SUPABASE_DB_ADMIN_URL from the given .env file (session pooler, port 5432),
sets new passwords in the database and writes DATABASE_URL and BFF_DATABASE_URL
(transaction pooler, port 6543) back into the same file. Nothing secret is printed.
"""

import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

TRANSACTION_POOLER_PORT = 6543
ROLES = {"api_gateway": "DATABASE_URL", "bff_session": "BFF_DATABASE_URL"}


def read_env(path: Path) -> dict[str, str]:
    """Minimal .env parser: KEY=value, '#' starts a comment (also after whitespace)."""
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.split(" #", 1)[0].strip()
    return values


def upsert_env(path: Path, updates: dict[str, str]) -> None:
    """Replace existing KEY= lines, append missing keys; keeps all other lines untouched."""
    lines = path.read_text().splitlines()
    pending = dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    lines += [f"{key}={value}" for key, value in pending.items()]
    path.write_text("\n".join(lines) + "\n")


def pooler_dsn(admin_dsn: str, role: str, password: str) -> str:
    """Same pooler host and project ref as the admin DSN, but for `role` in transaction mode."""
    parts = urlsplit(admin_dsn)
    project_ref = parts.username.split(".", 1)[1]  # admin user is "postgres.<ref>"
    netloc = f"{role}.{project_ref}:{password}@{parts.hostname}:{TRANSACTION_POOLER_PORT}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def main(env_path: Path) -> None:
    admin_dsn = read_env(env_path).get("SUPABASE_DB_ADMIN_URL")
    if not admin_dsn:
        sys.exit("SUPABASE_DB_ADMIN_URL fehlt in der .env-Datei.")

    updates: dict[str, str] = {}
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        for role, env_key in ROLES.items():
            password = secrets.token_urlsafe(32)
            conn.execute(
                sql.SQL("alter role {} password {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            updates[env_key] = pooler_dsn(admin_dsn, role, password)

    upsert_env(env_path, updates)
    print(f"Passwörter gesetzt und {', '.join(updates)} in {env_path} geschrieben.")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "../../.env"))
