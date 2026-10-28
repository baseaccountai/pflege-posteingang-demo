"""F11-AC5: `make up` uses the same local-only passwords as the tests, so running the tests
while the local stack is up does not lock the stack out of its database."""

from scripts.local_db_roles import LOCAL_PASSWORDS
from tests.rls.conftest import GATEWAY_PASSWORD


def test_the_local_passwords_are_the_ones_the_tests_use():
    assert LOCAL_PASSWORDS == {
        "api_gateway": GATEWAY_PASSWORD,
        "bff_session": "bff_session_local_test",  # apps/web/e2e/support/env.ts BFF_PASSWORD
    }
