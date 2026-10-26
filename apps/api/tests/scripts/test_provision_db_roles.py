from scripts.provision_db_roles import pooler_dsn, read_env, upsert_env

ADMIN = "postgresql://postgres.abc:adminpw@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"


def test_pooler_dsn_uses_role_dot_ref_and_transaction_port():
    assert pooler_dsn(ADMIN, "api_gateway", "s3cret") == (
        "postgresql://api_gateway.abc:s3cret@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
    )


def test_read_env_ignores_comments_and_inline_comments(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# x\nA=1   # note\nB=\nC=two words\n")
    assert read_env(env) == {"A": "1", "B": "", "C": "two words"}


def test_upsert_env_replaces_existing_and_appends_new(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nDATABASE_URL=\n")
    upsert_env(env, {"DATABASE_URL": "x", "BFF_DATABASE_URL": "y"})
    assert env.read_text() == "A=1\nDATABASE_URL=x\nBFF_DATABASE_URL=y\n"
