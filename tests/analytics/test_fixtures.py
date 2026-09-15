"""The fixtures have to be a consistent world, or every test built on them lies.

These are the cross-checks a reviewer would do by hand against the real database
once `db/004_analytics.sql` is applied: the same views counted two ways come to
the same total, and an episode's reach is the sum of its cuts. If a fixture is
ever regenerated and stops reconciling, this fails here rather than in a renderer
three tabs away.

See fixtures/README.md for what the numbers describe and which cross-checks are
deliberately absent.
"""
import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
PLATFORMS = ("youtube", "instagram", "tiktok")
KINDS = ("yt_age", "yt_gender", "yt_country", "ig_age", "ig_gender", "ig_city", "ig_country")


def load(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def views():
    return load("rollup_views")


@pytest.fixture(scope="module")
def followers():
    return load("rollup_followers")


@pytest.fixture(scope="module")
def engagement():
    return load("rollup_engagement")


@pytest.fixture(scope="module")
def posts():
    return load("post_deltas")


@pytest.fixture(scope="module")
def episodes():
    return load("episode_rollup")


@pytest.fixture(scope="module")
def demographics():
    return load("demographics_compare")


# --- shape -------------------------------------------------------------------

@pytest.mark.parametrize("name,keys", [
    ("rollup_views", {"period", "platform", "views", "posts_published"}),
    ("rollup_followers", {"period", "platform", "followers", "gained", "lost"}),
    ("rollup_engagement", {"period", "platform", "likes", "comments", "shares",
                           "engagement_rate"}),
    ("post_deltas", {"post_id", "platform", "title", "url", "published_at", "views_start",
                     "views_end", "views_gained", "likes", "comments", "shares", "reach",
                     "engagement_rate", "episode_id"}),
    ("episode_rollup", {"episode_id", "season", "number", "title", "guest", "role",
                        "published_at", "youtube_video_id", "yt_views", "clip_count",
                        "clip_views_youtube", "clip_views_instagram", "clip_views_tiktok",
                        "total_reach"}),
])
def test_columns_match_the_function_signature(name, keys):
    """Every row carries exactly the columns db/004_analytics.sql returns."""
    rows = load(name)
    assert rows, f"{name} fixture is empty"
    assert [set(r) for r in rows] == [keys] * len(rows)


def test_demographics_compare_is_keyed_by_kind(demographics):
    assert set(demographics) == set(KINDS)
    cols = {"dimension", "value", "prev_value", "delta", "window_start", "window_end",
            "prev_window_start", "prev_window_end"}
    for kind, rows in demographics.items():
        assert rows, f"{kind} is empty"
        assert all(set(r) == cols for r in rows), kind


@pytest.mark.parametrize("name", ["rollup_views", "rollup_followers", "rollup_engagement"])
def test_period_fixtures_are_seven_bangkok_days_in_utc(name):
    rows = load(name)
    periods = sorted({r["period"] for r in rows})
    assert periods == [f"2026-09-{8 + i:02d}T17:00:00+00:00" for i in range(7)]
    assert len(rows) == 21
    assert {r["platform"] for r in rows} == set(PLATFORMS)


# --- the cross-checks --------------------------------------------------------

def test_views_reconcile_between_the_period_rollup_and_the_post_table(views, posts):
    """rollup_views summed over the window == post_deltas.views_gained summed.

    Two different functions counting the same thing two different ways. On the
    real database this is the check that catches a broken snapshot boundary.
    """
    by_period = {p: 0 for p in PLATFORMS}
    for r in views:
        by_period[r["platform"]] += r["views"]
    by_post = {p: 0 for p in PLATFORMS}
    for r in posts:
        by_post[r["platform"]] += r["views_gained"]
    assert by_period == by_post
    assert by_period == {"youtube": 9700, "instagram": 36900, "tiktok": 23300}


def test_episode_reach_is_the_sum_of_its_cuts(episodes, posts):
    latest = {r["post_id"]: r["views_end"] for r in posts}
    for e in episodes:
        clips = e["clip_views_youtube"] + e["clip_views_instagram"] + e["clip_views_tiktok"]
        assert e["total_reach"] == e["yt_views"] + clips, e["guest"]
        assert e["yt_views"] == latest[f"yt:{e['youtube_video_id']}"], e["guest"]


def test_followers_gained_and_lost_are_the_two_halves_of_the_change(followers):
    """Day one attributes nothing: there is no earlier snapshot to subtract."""
    by_plat = {p: [] for p in PLATFORMS}
    for r in sorted(followers, key=lambda r: r["period"]):
        by_plat[r["platform"]].append(r)
    for plat, rows in by_plat.items():
        assert (rows[0]["gained"], rows[0]["lost"]) == (0, 0), plat
        for prev, cur in zip(rows, rows[1:]):
            change = cur["followers"] - prev["followers"]
            assert cur["gained"] - cur["lost"] == change, plat
            assert cur["gained"] >= 0 and cur["lost"] >= 0, plat


def test_engagement_rate_is_the_ratio_of_sums_not_a_mean_of_rates(engagement, views):
    """The rate the SQL computes, recomputed from its own numerator and the
    matching views row. A mean of per-post rates would not land here."""
    v = {(r["period"], r["platform"]): r["views"] for r in views}
    for r in engagement:
        total = r["likes"] + r["comments"] + r["shares"]
        assert r["engagement_rate"] == pytest.approx(
            total / v[(r["period"], r["platform"])], abs=5e-7), r


def test_post_engagement_rate_is_a_fraction_not_a_percentage(posts):
    for r in posts:
        assert 0 < r["engagement_rate"] < 1, r["post_id"]


# --- the edge cases that exist on purpose -------------------------------------

def test_reach_is_reported_only_where_a_platform_reports_it(posts):
    """Instagram reports reach. YouTube and TikTok do not, and post_deltas
    returns null rather than the zero the collector stored — a zero there reads
    as "nobody saw this post"."""
    for r in posts:
        if r["platform"] == "instagram":
            assert r["reach"] and r["reach"] > 0, r["post_id"]
        else:
            assert r["reach"] is None, r["post_id"]


def test_a_post_can_lose_views(posts):
    """Platforms recount. post_deltas does not clamp, so a renderer must cope."""
    assert [r["post_id"] for r in posts if r["views_gained"] < 0] == ["tt:FIXCLIP03"]


def test_posts_first_seen_in_the_window_count_their_whole_total(posts):
    new = [r for r in posts if r["views_start"] == 0]
    assert {r["post_id"] for r in new} == {"ig:FIXCLIP01", "tt:FIXCLIP01"}
    assert all(r["views_gained"] == r["views_end"] for r in new)


def test_every_post_is_matched_to_an_episode_except_the_one_that_is_not(posts):
    """The collector matches on title, and sometimes it cannot. The Episodes tab
    has an Unassigned panel because of exactly this row."""
    unmatched = [r["post_id"] for r in posts if r["episode_id"] is None]
    assert unmatched == ["tt:FIXCLIP03"]


def test_episode_clip_counts_agree_with_the_post_table(episodes, posts):
    """episode_rollup's clip_count is the number of matched posts that are not
    the long cut. If the two fixtures drift, the Episodes tab shows a count it
    cannot then list."""
    for e in episodes:
        long_cut = f"yt:{e['youtube_video_id']}"
        clips = [r for r in posts
                 if r["episode_id"] == e["episode_id"] and r["post_id"] != long_cut]
        assert e["clip_count"] == len(clips), e["guest"]
        for platform, column in (("youtube", "clip_views_youtube"),
                                 ("instagram", "clip_views_instagram"),
                                 ("tiktok", "clip_views_tiktok")):
            expected = sum(r["views_end"] for r in clips if r["platform"] == platform)
            assert e[column] == expected, (e["guest"], platform)


def test_a_youtube_clip_is_not_the_same_thing_as_the_long_cut(episodes):
    """Clips are excluded by post id, not by platform: a Short is a clip too."""
    ep1 = next(e for e in episodes if e["episode_id"] == 1)
    assert ep1["clip_views_youtube"] > 0
    assert ep1["clip_count"] == 3


def test_one_demographic_kind_has_no_comparable_earlier_window(demographics):
    rows = demographics["ig_city"]
    assert all(r["prev_value"] is None and r["delta"] is None for r in rows)
    assert all(r["prev_window_start"] is None and r["prev_window_end"] is None for r in rows)


def test_percentage_kinds_sum_to_about_a_hundred_and_count_kinds_do_not(demographics):
    for kind in ("yt_age", "yt_gender"):
        assert sum(r["value"] for r in demographics[kind]) == pytest.approx(100, abs=1)
    for kind in ("yt_country", "ig_age", "ig_gender", "ig_city", "ig_country"):
        assert sum(r["value"] for r in demographics[kind]) > 500, kind


def test_the_country_split_moves_the_way_the_old_media_kit_got_wrong(demographics):
    """India's share falls while Thailand's rises. The Audience tab must label
    the window it is describing, or it can repeat the 54%-India claim."""
    rows = {r["dimension"]: r for r in demographics["yt_country"]}
    assert rows["TH"]["delta"] > 0
    assert rows["IN"]["delta"] < 0


# --- nothing real in here ----------------------------------------------------

def test_no_real_guest_or_video_id_leaked_into_a_fixture():
    """Fixtures are synthetic. Real guest names and real video ids live in
    data/episodes.json; none of them may appear here."""
    real = json.loads((Path(__file__).resolve().parents[2] / "data" / "episodes.json")
                      .read_text(encoding="utf-8"))
    names = set()
    for video_id, e in real.items():
        if video_id.startswith("_"):
            continue
        names.add(video_id)
        if e.get("guest"):
            names.add(e["guest"])
    blob = "\n".join(p.read_text(encoding="utf-8") for p in FIX.glob("*.json")).lower()
    assert [n for n in names if n.lower() in blob] == []
