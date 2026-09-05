"""Accounts (password auth) + per-account private sessions — integration against a local Postgres.

Skipped unless NOESIS_TEST_PG_DSN is set (same convention as the kernel's pg tests). Uses the real
tables (noesis_user / noesis_user_token / noesis_research_session) under a throwaway vertical name so
nothing collides with dev data; rows are removed at the end.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from api.accounts import AccountStore, hash_password, verify_password
from api.sessions import SessionStore

DSN = os.environ.get("NOESIS_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="set NOESIS_TEST_PG_DSN for pg integration")
VERT = "test_" + uuid.uuid4().hex[:8]


def test_password_hash_roundtrip_and_constant_time_shape() -> None:
    h, salt = hash_password("hunter2")
    assert verify_password("hunter2", h, salt)
    assert not verify_password("hunter3", h, salt)
    assert not verify_password("hunter2", "", "")          # unknown user path still returns False


async def _cleanup(acc: AccountStore, sess: SessionStore) -> None:
    async with (await acc._get_pool()).acquire() as conn:
        await conn.execute("DELETE FROM noesis_user_token WHERE user_id IN (SELECT id FROM noesis_user WHERE vertical=$1)", VERT)
        await conn.execute("DELETE FROM noesis_user WHERE vertical=$1", VERT)
        await conn.execute("DELETE FROM noesis_research_session WHERE vertical=$1", VERT)


def test_register_login_logout_and_private_sessions() -> None:
    async def body():
        acc = AccountStore(DSN, vertical=VERT)
        sess = SessionStore(DSN, vertical=VERT)
        try:
            h, salt = hash_password("pw-a")
            alice, tok_a = await acc.register(email="a@x.io", name="Alice", pw_hash=h, pw_salt=salt)
            h2, salt2 = hash_password("pw-b")
            bob, tok_b = await acc.register(email="b@x.io", name="Bob", pw_hash=h2, pw_salt=salt2)
            assert await acc.email_exists("A@x.io") and not await acc.email_exists("c@x.io")
            # a pre-passwords (token-only) account has no password → may claim itself by setting one
            legacy, _ = await acc.register(email="l@x.io", name="Legacy")
            assert await acc.email_exists("l@x.io") and not await acc.has_password("l@x.io")
            assert await acc.login(email="l@x.io", password="anything") is None
            h3, salt3 = hash_password("pw-l")
            claimed, _ = await acc.register(email="l@x.io", name="Legacy", pw_hash=h3, pw_salt=salt3)
            assert claimed["id"] == legacy["id"] and await acc.has_password("l@x.io")
            assert (await acc.login(email="l@x.io", password="pw-l"))[0]["id"] == legacy["id"]
            assert await acc.has_password("a@x.io")                    # normal accounts stay 409 at the route
            # login: right password → fresh token; wrong → None
            assert await acc.login(email="a@x.io", password="nope") is None
            u, tok_a2 = await acc.login(email="a@x.io", password="pw-a")
            assert u["id"] == alice["id"] and tok_a2 != tok_a
            assert (await acc.user_by_token(tok_a2))["id"] == alice["id"]
            await acc.logout(tok_a2)
            assert await acc.user_by_token(tok_a2) is None
            assert (await acc.user_by_token(tok_a))["id"] == alice["id"]   # other device still valid

            # sessions are stamped with the owner and listed only for that owner
            common = dict(tenant_id="demo", workspace_id=None, answer="A", grounded=True, claims=[],
                          source_stats={}, coverage_gaps=[], rejected=0, sources=None)
            sa = await sess.save(question="alice q", user_id=alice["id"], **common)
            sb = await sess.save(question="bob q", user_id=bob["id"], **common)
            s0 = await sess.save(question="legacy q", user_email="a@x.io", **common)   # pre-accounts row
            assert {r["id"] for r in await sess.list(tenant_id="demo", user_id=alice["id"])} == {sa}
            assert {r["id"] for r in await sess.list(tenant_id="demo", user_id=bob["id"])} == {sb}
            assert (await sess.get(sa))["user_id"] == alice["id"]
            # append / delete are owner-guarded
            assert not await sess.append_turn(sa, {"question": "x", "answer": "y"}, user_id=bob["id"])
            assert await sess.append_turn(sa, {"question": "x", "answer": "y"}, user_id=alice["id"])
            assert not await sess.soft_delete(sa, user_id=bob["id"])
            assert not await sess.soft_delete(sa, user_id=None)
            assert await sess.soft_delete(sa, user_id=alice["id"])
            # legacy sessions saved under the email are adopted on login
            assert await sess.claim_by_email(user_id=alice["id"], email="A@x.io") == 1
            assert {r["id"] for r in await sess.list(tenant_id="demo", user_id=alice["id"])} == {s0}
        finally:
            await _cleanup(acc, sess)
    asyncio.run(body())
