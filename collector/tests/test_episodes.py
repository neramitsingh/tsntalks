import json
from pathlib import Path

from tsn_collector import episodes as E

FX = Path(__file__).parent / "fixtures"


def test_parse_season2_colon():
    r = E.parse_title("TSN TALKS S2 E10: Sunny Khurana, Founder & CEO, Spark.love")
    assert r == E.Parsed(season=2, number="10", guest="Sunny Khurana", role="Founder & CEO, Spark.love")


def test_parse_season2_comma():
    r = E.parse_title("TSN Talks S2 E9, Mr. Deepak Sajnani, President of Thai-Sindhi Association")
    assert r.season == 2 and r.number == "9" and r.guest == "Mr. Deepak Sajnani"
    assert r.role == "President of Thai-Sindhi Association"


def test_parse_season2_colon_between_s_and_e_and_pipe():
    r = E.parse_title("TSN Talks S2:E5: Gagan Ajmani | Thai Founders Think Too Small? Hear from the Guy Who Raised $12M")
    assert r.season == 2 and r.number == "5" and r.guest == "Gagan Ajmani"
    assert r.role.startswith("Thai Founders Think Too Small?")


def test_parse_pipe_with_comma_in_number():
    r = E.parse_title("TSN Talks S2 E4: Sukhdev Sethi |  He Closed $1.5M and Beat 6,000 People from 151 Countries in Sales.")
    assert r.guest == "Sukhdev Sethi" and r.role.startswith("He Closed $1.5M and Beat 6,000")


def test_parse_marker_at_end():
    r = E.parse_title("How AI Can Secretly Manipulate You | Sunny Chawla (Sunnylogy) | S02:E03")
    assert r == E.Parsed(season=2, number="3", guest="Sunny Chawla (Sunnylogy)", role="How AI Can Secretly Manipulate You")


def test_parse_kickoff():
    r = E.parse_title("Season 2 Kickoff: Special Episode with Mr. Nikorn Sachdev")
    assert r == E.Parsed(season=2, number="0", guest="Mr. Nikorn Sachdev", role="Season kickoff special")


def test_parse_season1_dash():
    r = E.parse_title("TSN Talks Ep. 03 - Kirty Khanijou")
    assert r == E.Parsed(season=1, number="3", guest="Kirty Khanijou", role="")


def test_parse_season1_ep_colon_forms():
    assert E.parse_title("TSN Talks Ep: 18 - Dr Nivit Kalra, Cardiologist & Co-founder, Prime Care Clinic ") == \
        E.Parsed(1, "18", "Dr Nivit Kalra", "Cardiologist & Co-founder, Prime Care Clinic")
    assert E.parse_title("TSN Talks Ep: 15: Manish Sethi") == E.Parsed(1, "15", "Manish Sethi", "")
    assert E.parse_title("TSN Talks Ep.05 - Mana Khanijou") == E.Parsed(1, "5", "Mana Khanijou", "")
    assert E.parse_title("TSN Talks Ep 22: Nathapol Sirinarang, President of BNI The One Chapter ") == \
        E.Parsed(1, "22", "Nathapol Sirinarang", "President of BNI The One Chapter")


def test_parse_part_forms():
    assert E.parse_title("TSN Talks Ep. 11, Part 1: Dr. Sunil Phol") == E.Parsed(1, "11", "Dr. Sunil Phol (Part 1)", "")
    assert E.parse_title("TSN Talks Ep. 13 - Dr. Sunil (Part 2) ") == E.Parsed(1, "13", "Dr. Sunil (Part 2)", "")


def test_parse_non_episode_returns_none():
    assert E.parse_title("This week on TSN Talks 🎙 we sit down with...") is None
    assert E.parse_title("TSN Talks Season 1 Finale Lineup!") is None
    assert E.parse_title(None) is None


def test_every_catalogue_title_parses():
    flat = json.loads((FX / "ytdlp_flat.json").read_text(encoding="utf-8"))
    failed = [e["title"] for e in flat["entries"] if E.parse_title(e["title"]) is None]
    assert failed == []
    keys = [(p.season, p.number) for p in (E.parse_title(e["title"]) for e in flat["entries"])]
    assert len(keys) == len(set(keys)), "season/number must be unique across the catalogue"


def test_match_terms():
    p = E.Parsed(season=2, number="10", guest="Sunny Khurana", role="Founder")
    assert E.match_terms(p) == ["sunny khurana", "khurana", "s2 e10", "s2:e10", "s02:e10", "s2 e10"][:5]
    p1 = E.Parsed(season=1, number="3", guest="Kirty Khanijou", role="")
    assert E.match_terms(p1) == ["kirty khanijou", "khanijou", "ep 3", "ep. 3", "ep 03", "ep. 03", "episode 3", "episode 03"]
    dr = E.Parsed(season=1, number="11", guest="Dr. Sunil Phol (Part 1)", role="")
    assert E.match_terms(dr)[:2] == ["sunil phol", "phol"]


def test_match_post_prefers_full_name_then_surname():
    eps = [
        {"id": 1, "match_terms": ["sunny khurana", "khurana", "s2 e10"]},
        {"id": 2, "match_terms": ["sukit khurana", "khurana", "ep 19"]},
    ]
    assert E.match_post("Major Sukit Khurana opens up", eps) == 2
    assert E.match_post("In Episode 19, Major Sukrit opens up", eps) is None
    assert E.match_post("Sunny Khurana on love", eps) == 1
    assert E.match_post("Khurana speaks", eps) is None  # ambiguous surname, no match
    assert E.match_post(None, eps) is None
