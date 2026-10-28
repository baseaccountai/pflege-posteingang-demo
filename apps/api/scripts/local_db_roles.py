"""Local-only passwords for the database login roles (F11-AC5, `make up`).

The migrations create `api_gateway` (API) and `bff_session` (BFF sessions) without a usable
password. Locally they get the same fixed passwords the tests set, so the Docker stack and
the test runs share one setup. Never used for the cloud database (there:
scripts/provision_db_roles.py writes random passwords into .env).

    cd apps/api && uv run python -m scripts.local_db_roles
"""

import psycopg

from scripts.reset_demo import LOCAL_ADMIN_DSN

LOCAL_PASSWORDS = {"api_gateway": "api_gateway_local_test", "bff_session": "bff_session_local_test"}


def main() -> None:
    with psycopg.connect(LOCAL_ADMIN_DSN, autocommit=True) as conn:
        for role, password in LOCAL_PASSWORDS.items():
            # Role names come from the constant above, never from input.
            conn.execute(f"alter role {role} password '{password}'")
    print("Lokale Passwörter der Login-Rollen gesetzt.")


if __name__ == "__main__":
    main()
