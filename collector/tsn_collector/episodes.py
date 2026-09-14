"""Episode titles → episodes rows; post titles → episode ids. Pure functions."""
from __future__ import annotations

import re
from dataclasses import dataclass

TITLE_RE = re.compile(
    r"^\s*TSN\s*TALKS\s*(?:S(?P<s>\d+)\s*E(?P<e>\d+)|Ep\.?\s*(?P<n>\d+))\s*[:\-–,\s]\s*(?P<rest>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Parsed:
    season: int
    number: str
    guest: str
    role: str


def parse_title(title: str | None) -> Parsed | None:
    if not title:
        return None
    m = TITLE_RE.match(title.splitlines()[0])
    if not m:
        return None
    rest = m.group("rest")
    if m.group("s"):
        season, number = int(m.group("s")), m.group("e")
    else:
        season, number = 1, m.group("n")
    if "," in rest:
        guest, role = rest.split(",", 1)
    else:
        guest, role = rest, ""
    return Parsed(season=season, number=number, guest=guest.strip(), role=role.strip())


def match_terms(p: Parsed) -> list[str]:
    name = re.sub(r"\s*\(.*?\)\s*", " ", p.guest).strip().lower()
    words = [w for w in name.split() if w not in {"dr.", "dr", "mr.", "mr", "ms.", "ms", "major"}]
    terms = [name]
    if len(words) >= 2:
        terms.append(words[-1])
    if p.season == 1:
        n = p.number
        terms += [f"ep {n}", f"ep. {n}", f"episode {n}"]
        if n != str(int(n)):
            terms.append(f"episode {int(n)}")
    else:
        terms.append(f"s{p.season} e{int(p.number)}")
    out = []
    for t in terms:
        if t not in out:
            out.append(t)
    return out


def match_post(title: str | None, episodes: list[dict]) -> int | None:
    """Return the episode id a post belongs to. Full-name terms win; a surname shared by two episodes is ambiguous."""
    if not title:
        return None
    t = title.lower()
    full_hits = [e["id"] for e in episodes if any(len(term.split()) >= 2 and term in t for term in e["match_terms"])]
    if len(full_hits) == 1:
        return full_hits[0]
    if len(full_hits) > 1:
        return None
    surname_hits = [e["id"] for e in episodes if any(len(term.split()) == 1 and not term.startswith("ep") and term in t
                                                     for term in e["match_terms"])]
    return surname_hits[0] if len(surname_hits) == 1 else None