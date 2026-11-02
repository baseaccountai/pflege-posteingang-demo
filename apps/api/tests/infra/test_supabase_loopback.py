"""F11-AC13: the local Supabase stack listens on this machine only (Codex review phase 8).

`supabase start` publishes the database (postgres:postgres, no RLS for that login), Studio
and the API gateway on every interface by default - reachable from the whole network.
`make db-start` therefore starts it in a Docker network that binds published ports to
127.0.0.1 (option com.docker.network.bridge.host_binding_ipv4). Checked by hand on
02.11.2026: `ss -ltn` shows 127.0.0.1 only, the LAN address gets no answer.
"""

import re
from pathlib import Path

MAKEFILE = Path(__file__).parents[4] / "Makefile"


def target(name: str) -> str:
    text = MAKEFILE.read_text()
    match = re.search(rf"^{name}:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, f"target {name} missing"
    return match.group(1)


def test_db_start_uses_a_network_that_binds_to_localhost_only():
    recipe = target("db-start")
    assert "--network-id $(SUPABASE_NETWORK)" in recipe
    assert "com.docker.network.bridge.host_binding_ipv4=127.0.0.1" in recipe


def test_an_existing_network_without_the_binding_stops_the_start():
    # A network of the same name created by hand without the option would publish on all
    # interfaces again - db-start checks the option instead of trusting the name.
    recipe = target("db-start")
    assert "host_binding_ipv4" in recipe.split("--network-id")[0]
    assert "exit 1" in recipe
