-- F01-AC5: server-side one-time login attempts. The login route stores sha256(state); the
-- callback deletes the row before it redeems the code. A replayed callback (even with a
-- stolen login cookie) or a parallel second callback finds no row and is rejected.
create table bff.login_attempts (
  state_hash bytea primary key,        -- sha256 of the OIDC state, never the state itself
  expires_at timestamptz not null      -- 10 minutes, like the login cookie
);

-- select: needed for the WHERE clause of the delete.
grant select, insert, delete on bff.login_attempts to bff_session;
