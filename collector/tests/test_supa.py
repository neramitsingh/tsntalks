import json

import responses

from tsn_collector.supa import Supa

URL = "https://example.supabase.co"


@responses.activate
def test_upsert_chunks_and_sets_merge_headers():
    calls = []

    def cb(req):
        calls.append((req.url, req.headers["Prefer"], json.loads(req.body)))
        return (201, {}, "")

    responses.add_callback(responses.POST, f"{URL}/rest/v1/post_snapshots", callback=cb)
    s = Supa(URL, "svc", chunk=2)
    rows = [{"post_id": f"p{i}", "taken_at": "t", "views": i} for i in range(5)]
    n = s.upsert("post_snapshots", rows, on_conflict="post_id,taken_at")
    assert n == 5
    assert len(calls) == 3
    assert calls[0][0].endswith("on_conflict=post_id%2Ctaken_at")
    assert calls[0][1] == "resolution=merge-duplicates,return=minimal"
    assert [len(c[2]) for c in calls] == [2, 2, 1]


@responses.activate
def test_upsert_empty_is_noop():
    s = Supa(URL, "svc")
    assert s.upsert("posts", [], on_conflict="id") == 0
    assert len(responses.calls) == 0


@responses.activate
def test_select_and_rpc():
    responses.add(responses.GET, f"{URL}/rest/v1/accounts", json=[{"id": "a"}])
    responses.add(responses.POST, f"{URL}/rest/v1/rpc/live_json", json={"ok": True})
    s = Supa(URL, "svc")
    assert s.select("accounts", select="id") == [{"id": "a"}]
    assert s.rpc("live_json", {}) == {"ok": True}
    assert responses.calls[0].request.headers["apikey"] == "svc"