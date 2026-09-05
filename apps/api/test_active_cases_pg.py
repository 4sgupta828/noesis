"""Active Cases (anonymous publication) — integration against a local Postgres.

Skipped unless NOESIS_TEST_PG_DSN is set. Proves the board copy carries no identity: no owner,
asker, patient reference or attachments, and scrubbed text; that only the owner can publish or
retract; and that re-publishing refreshes under the same case id.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from api.sessions import SessionStore

DSN = os.environ.get("NOESIS_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="set NOESIS_TEST_PG_DSN for pg integration")
VERT = "test_" + uuid.uuid4().hex[:8]


async def _cleanup(sess: SessionStore) -> None:
    async with (await sess._get_pool()).acquire() as conn:
        await conn.execute("DELETE FROM noesis_active_case WHERE vertical=$1", VERT)
        await conn.execute("DELETE FROM noesis_research_session WHERE vertical=$1", VERT)


def test_publish_is_anonymous_owner_guarded_and_idempotent() -> None:
    async def body():
        sess = SessionStore(DSN, vertical=VERT)
        try:
            sid = await sess.save(tenant_id="demo", workspace_id=None,
                                  question="Ravi Kumar, MRN 778812, eGFR 28 on metformin 1000 mg — continue?",
                                  answer="Reduce metformin at eGFR 28 [1]. Contact ravi@example.org.",
                                  grounded=True, claims=[], source_stats={}, coverage_gaps=[], rejected=0,
                                  sources=[], user_name="Dr Priya Nair", user_email="priya@clinic.org",
                                  attachments=[{"name": "labs.pdf"}], user_id="owner-1")
            await sess.set_patient(sid, "Ravi Kumar / 778812", user_id="owner-1")
            other = await sess.save(tenant_id="demo", workspace_id=None, question="Not mine", answer="x",
                                    grounded=False, claims=[], source_stats={}, coverage_gaps=[], rejected=0,
                                    sources=[], user_id="owner-2")

            res = await sess.active_publish([sid, other, "nope"], user_id="owner-1")
            assert [p["session_id"] for p in res["published"]] == [sid]
            assert sorted(res["skipped"]) == sorted([other, "nope"])
            cid = res["published"][0]["case_id"]
            assert cid != sid

            # the public copy: identity-free and scrubbed
            row = await sess.active_get(cid)
            assert row is not None and row["anonymous"] is True
            for k in ("user_id", "user_name", "user_email", "patient_ref", "attachments", "tenant_id", "share_token"):
                assert k not in row, k
            blob = str(row)
            for leak in ("Ravi", "Kumar", "778812", "Priya", "Nair", "priya@clinic.org", "ravi@example.org", "labs.pdf"):
                assert leak not in blob, leak
            assert "eGFR 28" in row["question"] and "1000 mg" in row["question"]

            listed = await sess.active_list()
            assert [c["case_id"] for c in listed] == [cid]
            assert "Ravi" not in listed[0]["question"] and "Ravi" not in listed[0]["excerpt"]
            assert (await sess.active_list(q="metformin"))[0]["case_id"] == cid
            assert await sess.active_list(q="zzz-no-match") == []

            mine = await sess.active_mine(user_id="owner-1")
            assert mine and mine[0]["session_id"] == sid and mine[0]["case_id"] == cid
            assert await sess.active_mine(user_id="owner-2") == []

            # re-publish keeps the case id (one board entry per session)
            res2 = await sess.active_publish([sid], user_id="owner-1")
            assert res2["published"][0]["case_id"] == cid
            assert len(await sess.active_list()) == 1

            # retract: not the owner → refused; owner → gone; admin may retract anything
            assert not await sess.active_unpublish(cid, user_id="owner-2")
            assert await sess.active_get(cid) is not None
            assert await sess.active_unpublish(cid, user_id="owner-1")
            assert await sess.active_get(cid) is None
            res3 = await sess.active_publish([sid], user_id="owner-1")
            assert await sess.active_unpublish(res3["published"][0]["case_id"], user_id=None, admin=True)
            assert await sess.active_list() == []
        finally:
            await _cleanup(sess)
    asyncio.run(body())


def test_admin_publishes_any_account_and_unowned() -> None:
    async def body():
        sess = SessionStore(DSN, vertical=VERT)
        try:
            theirs = await sess.save(tenant_id="demo", workspace_id=None, question="Their case, eGFR 40", answer="x [1]",
                                     grounded=True, claims=[], source_stats={}, coverage_gaps=[], rejected=0,
                                     sources=[], user_id="owner-9")
            nobody = await sess.save(tenant_id="demo", workspace_id=None, question="Unowned case", answer="y",
                                     grounded=False, claims=[], source_stats={}, coverage_gaps=[], rejected=0,
                                     sources=[], user_id=None)
            assert [s["id"] for s in await sess.admin_list(user_id="owner-9")] == [theirs]
            assert [s["id"] for s in await sess.admin_list(user_id=None)] == [nobody]
            # a non-admin, non-owner cannot publish either; an admin can publish both
            assert (await sess.active_publish([theirs, nobody], user_id="someone"))["published"] == []
            res = await sess.active_publish([theirs, nobody], user_id=None, admin=True)
            assert sorted(p["session_id"] for p in res["published"]) == sorted([theirs, nobody])
            assert [m["session_id"] for m in await sess.active_mine(user_id="owner-9")] == [theirs]
            assert [m["session_id"] for m in await sess.active_mine(user_id=None)] == [nobody]
            assert len(await sess.active_list()) == 2
        finally:
            await _cleanup(sess)
    asyncio.run(body())
