from tsn_collector import episodes as E


def test_parse_season2_colon():
    r = E.parse_title("TSN TALKS S2 E10: Sunny Khurana, Founder & CEO, Spark.love")
    assert r == E.Parsed(season=2, number="10", guest="Sunny Khurana", role="Founder & CEO, Spark.love")


def test_parse_season2_comma():
    r = E.parse_title("TSN Talks S2 E9, Mr. Deepak Sajnani, President of Thai-Sindh Association")
    assert r.season == 2 and r.number == "9" and r.guest == "Mr. Deepak Sajnani"
    assert r.role == "President of Thai-Sindh Association"


def test_parse_season1_dash():
    r = E.parse_title("TSN Talks Ep. 03 - Kirty Khanijou")
    assert r == E.Parsed(season=1, number="03", guest="Kirty Khanijou", role="")


def test_parse_season1_colon_with_paren():
    r = E.parse_title("TSN TALKS Ep. 01: Dhammandeep Singh Khanijaun (Dan)")
    assert r.season == 1 and r.number == "01" and r.guest == "Dhammandeep Singh Khanijaun (Dan)"


def test_parse_part_suffix():
    r = E.parse_title("TSN Talks Ep. 13 - Dr. Sunil (Part 2)")
    assert r.number == "13" and r.guest == "Dr. Sunil (Part 2)"


def test_parse_non_episode_returns_none():
    assert E.parse_title("This week on TSN Talks 🎙 we sit down with...") is None
    assert E.parse_title("TSN Talks Season 1 Finale Lineup!") is None


def test_match_terms():
    p = E.Parsed(season=2, number="10", guest="Sunny Khurana", role="Founder")
    assert E.match_terms(p) == ["sunny khurana", "khurana", "s2 e10"]
    p1 = E.Parsed(season=1, number="03", guest="Kirty Khanijou", role="")
    assert E.match_terms(p1) == ["kirty khanijou", "khanijou", "ep 03", "ep. 03", "episode 03", "episode 3"]


def test_match_post_prefers_full_name_then_surname():
    eps = [
        {"id": 1, "match_terms": ["sunny khurana", "khurana", "s2 e10"]},
        {"id": 2, "match_terms": ["major sukit khurana", "khurana", "ep 19"]},
    ]
    assert E.match_post("Major Sukit Khurana opens up", eps) == 2
    assert E.match_post("In Episode 19, Major Sukrit opens up", eps) is None
    assert E.match_post("Sunny Khurana on love", eps) == 1
    assert E.match_post("Khurana speaks", eps) is None  # ambiguous surname, no match
    assert E.match_post(None, eps) is None