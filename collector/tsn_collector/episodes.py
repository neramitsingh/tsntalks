"""Episode titles -> episodes rows; post titles -> episode ids. Pure functions.

Title shapes seen on the channel (2026-09):
  TSN TALKS S2 E10: Guest, Role
  TSN Talks S2 E9, Guest, Role
  TSN Talks S2:E5: Guest | Topic
  TSN Talks S2 E4: Guest |  Topic with 6,000 in it
  Topic | Guest (Company) | S02:E03          (marker at the end)
  Season 2 Kickoff: Special Episode with Mr. Guest
  TSN Talks Ep 22: Guest, Role
  TSN Talks Ep. 19 - Guest
  TSN Talks Ep: 18 - Guest, Role
  TSN Talks Ep: 15: Guest
  TSN Talks Ep.05 - Guest
  TSN Talks Ep. 11, Part 1: Guest
  TSN Talks Ep. 13 - Guest (Part 2)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

HEAD_RE = re.compile(
    r"^\s*TSN\s*TALKS\s*(?:S(?P<s>\d+)\s*[:\s]?\s*E(?P<e>\d+)|Ep\.?:?\s*(?P<n>\d+))\s*[:\-–,|]\s*(?P<rest>.+?)\s*$",
    re.IGNORECASE,
)
TAIL_RE = re.compile(r"^(?P<rest>.+?)\s*\|\s*S(?P<s>\d+)\s*:\s*E(?P<e>\d+)\s*$", re.IGNORECASE)
KICKOFF_RE = re.compile(r"^\s*Season\s*(?P<s>\d+)\s*Kickoff\s*[:\-–]\s*(?P<rest>.+?)\s*$", re.IGNORECASE)
PART_RE = re.compile(r"^Part\s*(?P<p>\d+)\s*[:\-]\s*(?P<g>.+)$", re.IGNORECASE)
HONORIFICS = {"dr.", "dr", "mr.", "mr", "ms.", "ms", "mrs.", "mrs", "major", "khun"}


@dataclass(frozen=True)
class Parsed:
    season: int
    number: str
    guest: str
    role: str


def _split_guest_role(rest: str) -> tuple[str, str]:
    if "|" in rest:
        guest, role = rest.split("|", 1)
    elif ", " in rest:
        guest, role = rest.split(", ", 1)
    else:
        guest, role = rest, ""
    guest, role = guest.strip(), role.strip()
    if (m := PART_RE.match(guest)):
        guest = f"{m.group('g').strip()} (Part {m.group('p')})"
    return guest, role


def parse_title(title: str | None) -> Parsed | None:
    if not title:
        return None
    first = title.splitlines()[0].strip()
    if (m := HEAD_RE.match(first)):
        season = int(m.group("s")) if m.group("s") else 1
        number = str(int(m.group("e") or m.group("n")))
        guest, role = _split_guest_role(m.group("rest"))
        return Parsed(season, number, guest, role)
    if (m := TAIL_RE.match(first)):
        parts = [p.strip() for p in m.group("rest").split("|") if p.strip()]
        guest = parts[-1]
        role = " | ".join(parts[:-1])
        return Parsed(int(m.group("s")), str(int(m.group("e"))), guest, role)
    if (m := KICKOFF_RE.match(first)):
        rest = m.group("rest")
        guest = rest.split(" with ", 1)[1].strip() if " with " in rest else rest
        return Parsed(int(m.group("s")), "0", guest, "Season kickoff special")
    return None


def match_terms(p: Parsed) -> list[str]:
    name = re.sub(r"\s*\(.*?\)\s*", " ", p.guest).strip().lower()
    words = [w for w in name.split() if w not in HONORIFICS]
    clean = " ".join(words)
    terms = [clean] if clean else []
    if len(words) >= 2:
        terms.append(words[-1])
    n = int(p.number)
    if p.season == 1:
        terms += [f"ep {n}", f"ep. {n}", f"ep {n:02d}", f"ep. {n:02d}", f"episode {n}", f"episode {n:02d}"]
    elif n > 0:
        terms += [f"s{p.season} e{n}", f"s{p.season}:e{n}", f"s{p.season:02d}:e{n:02d}", f"s{p.season} e{n:02d}"]
    out: list[str] = []
    for t in terms:
        if t and t not in out:
            out.append(t)
    return out


def _is_name_term(term: str) -> bool:
    return not re.match(r"^(ep|episode|s\d)", term)


def match_post(title: str | None, episodes: list[dict]) -> int | None:
    """Return the episode id a post belongs to. Full-name terms win; a surname shared by two episodes is ambiguous."""
    if not title:
        return None
    t = title.lower()
    full_hits = [e["id"] for e in episodes
                 if any(_is_name_term(term) and len(term.split()) >= 2 and term in t for term in e["match_terms"])]
    if len(full_hits) == 1:
        return full_hits[0]
    if len(full_hits) > 1:
        return None
    surname_hits = [e["id"] for e in episodes
                    if any(_is_name_term(term) and len(term.split()) == 1 and term in t for term in e["match_terms"])]
    return surname_hits[0] if len(surname_hits) == 1 else None
