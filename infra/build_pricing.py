"""Render data/pricing.json into the rate-card blocks of the site's HTML.

The prices are editorial: a sponsor must be able to read them with JavaScript
off, a crawler must see them, and Sunny must be able to grep the repo for a
figure. So they are real static markup — but written in exactly one place,
data/pricing.json, and stamped into the pages from here.

    python infra/build_pricing.py            rewrite the blocks in place
    python infra/build_pricing.py --check    fail if the pages are out of step

The Pages workflow runs --check, so a price edited in the JSON and not baked
into the HTML fails the deploy instead of shipping two different rate cards.
"""
from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
PRICING = ROOT / "data" / "pricing.json"

# Which generated block lives in which page, and at what indent. A block is
# delimited by <!-- pricing:NAME --> ... <!-- /pricing:NAME --> inside its
# container. The indent is per block because the hero's floor price sits one
# level shallower than the rate-card blocks.
BLOCKS = [
    ("site/index.html", "hero-floor", ""),
    ("site/index.html", "tiers-brief", "      "),
    ("site/index.html", "bundles-floor", ""),
    ("site/partner/index.html", "fork-episode-floor", ""),
    ("site/partner/index.html", "fork-campaign-floor", ""),
    ("site/partner/index.html", "tiers-full", "      "),
    ("site/partner/index.html", "bundles", "      "),
]

# The reply address for the per-option "Ask about this" links. The rate card
# is static on purpose, so the address is baked here rather than fetched; the
# page's script upgrades the primary buttons to LINE when contact.json has it.
CONTACT = ROOT / "site" / "data" / "contact.json"

IND = "      "          # the rate-card blocks sit two levels in, as the hand markup did

LF = "\n"
CRLF = "\r\n"


def baht(n: int) -> str:
    """Never compact, never rounded — the sponsor types this into a message."""
    return f"฿{n:,}"


def _tag(name: str, cls: str | None, text: str) -> str:
    c = f' class="{cls}"' if cls else ""
    return f"<{name}{c}>{escape(text, quote=False)}</{name}>"


def _bullets(items: list[str], indent: str) -> list[str]:
    return [f"{indent}<ul>",
            *[f"{indent}  <li>{escape(i, quote=False)}</li>" for i in items],
            f"{indent}</ul>"]


def _price(t: dict) -> str:
    return (f'<div class="p">{baht(t["amount"])}'
            f'<small>{escape(t["unit"], quote=False)}</small></div>')


def render_hero_floor(p: dict) -> list[str]:
    """The cheapest tier, quoted in the hero. A sponsor arrives from a LINE link
    with seconds to spare, so the entry price is in the first screen — and it is
    generated here so it can never drift from the rate card below it."""
    lo = min(t["amount"] for t in p["tiers"])
    return [f'{IND_OF["hero-floor"]}<b id="floor">{baht(lo)}</b>']


def render_bundles_floor(p: dict) -> list[str]:
    """The cheapest package, quoted under the home rate card. Generated for the
    same reason as the hero floor: a typed figure drifts."""
    lo = min(b["amount"] for b in p["bundles"])
    return [f'{IND_OF["bundles-floor"]}<b id="bfloor">{baht(lo)}</b>']


# The rate card opens on a fork — one episode, or a campaign — and each side
# quotes its own floor so a reader picks a lane before reading ten prices.
def render_fork_episode_floor(p: dict) -> list[str]:
    return [f'<b>{baht(min(t["amount"] for t in p["tiers"]))}</b>']


def render_fork_campaign_floor(p: dict) -> list[str]:
    return [f'<b>{baht(min(b["amount"] for b in p["bundles"]))}</b>']


def _ask(t: dict) -> str:
    """A reply link with the option already named in the subject, so the
    sponsor never has to describe what they are asking about."""
    email = json.loads(CONTACT.read_text(encoding="utf-8"))["email"]
    subject = quote(f'TSN Talks sponsorship: {t.get("short_name") or t["name"]}')
    return f'<a class="ask" href="mailto:{email}?subject={subject}">Ask about this</a>'


# The tiers lead with the price. It used to come fourth, at 18px, behind a 30px
# roman numeral — and the numerals implied a rank the prices contradicted
# (I=฿25,000, II=฿20,000, III=฿15,000). They are gone.
def render_tiers_brief(p: dict) -> list[str]:
    """The homepage cards: one line of pitch, one price, no breakdown."""
    out = []
    for t in p["tiers"]:
        out += [f'{IND}<div class="tier">',
                f'{IND}  {_price(t)}',
                f'{IND}  {_tag("div", "n", t.get("short_name") or t["name"])}',
                f'{IND}  {_tag("div", "d", t["short"])}',
                f'{IND}</div>']
    return out


def render_tiers_full(p: dict) -> list[str]:
    """The partner page: the same tiers with what each one actually includes."""
    out = []
    for i, t in enumerate(p["tiers"]):
        if i:
            out.append("")
        # Tier V prices its two cuts inside the list, so those figures come from
        # the data like every other price rather than words baked into the copy.
        lines = ([f'{o["name"]}, {baht(o["amount"])}: {o["detail"]}' for o in t["options"]]
                 if t.get("options") else t.get("includes", []))
        out += [f'{IND}<div class="tier">',
                f'{IND}  {_price(t)}',
                f'{IND}  {_tag("div", "n", t["name"])}',
                f'{IND}  <div class="d">',
                f'{IND}    {escape(t["long"], quote=False)}',
                *_bullets(lines, f"{IND}    "),
                f'{IND}    {_ask(t)}',
                f'{IND}  </div>',
                f'{IND}</div>']
    return out


# The campaigns are rows on the same wooden plate as the tiers, one line each,
# so five offers can be compared down one column of prices. They used to be
# five identical bordered cards named "Bundle A / B / C", which is the card
# grammar the critique called the category default and a name that told a
# reader nothing. The term leads (one week, one month, two months) because that
# is what a sponsor actually chooses between; the kit's own tag follows it.
def render_bundles(p: dict) -> list[str]:
    out = []
    for i, b in enumerate(p["bundles"]):
        if i:
            out.append("")
        reach = f'{b["reach"]:,} guaranteed reach'
        # The saving is arithmetic, never a second number to keep in step.
        saving = b["regular"] - b["amount"]
        if b.get("show_saving") and saving > 0:
            reach += f" · you save {baht(saving)}"
        cls = "deal flag" if b.get("flagship") else "deal"
        was = f'Regular {baht(b["regular"])}'
        out += [f'{IND}<div class="{cls}">',
                f'{IND}  {_tag("div", "n", b["term"])}',
                f'{IND}  {_tag("div", "lab", b["tag"])}',
                f'{IND}  <div class="d">',
                *_bullets([*b["includes"], f'{baht(b["ad_budget"])} ad budget included'],
                          f"{IND}    "),
                f'{IND}  </div>',
                f'{IND}  <div class="p">',
                f'{IND}    {_tag("span", "was", was)}',
                f'{IND}    {_tag("b", None, baht(b["amount"]))}',
                f'{IND}    {_tag("small", None, reach)}',
                f'{IND}  </div>',
                f'{IND}</div>']
    return out


IND_OF = {name: ind for _, name, ind in BLOCKS}

RENDER = {
    "hero-floor": render_hero_floor,
    "bundles-floor": render_bundles_floor,
    "fork-episode-floor": render_fork_episode_floor,
    "fork-campaign-floor": render_fork_campaign_floor,
    "tiers-brief": render_tiers_brief,
    "tiers-full": render_tiers_full,
    "bundles": render_bundles,
}


def read(path: Path) -> tuple[str, str]:
    """Text with LF endings, plus whatever ending the file actually uses — the
    HTML is CRLF on disk and a rewrite must not churn every line."""
    raw = path.read_bytes().decode("utf-8")
    return raw.replace(CRLF, LF), (CRLF if CRLF in raw else LF)


def write(path: Path, text: str, eol: str) -> None:
    path.write_bytes(text.replace(LF, eol).encode("utf-8"))


def replace_block(text: str, name: str, body: list[str], where: str) -> str:
    open_m, close_m = f"<!-- pricing:{name} -->", f"<!-- /pricing:{name} -->"
    i, j = text.find(open_m), text.find(close_m)
    if i < 0 or j < 0:
        sys.exit(f"{where}: missing {open_m} … {close_m}")
    head = text[: i + len(open_m)]
    # A block with no indent is inline: it sits inside a sentence, and a newline
    # on either side of it would render as a space before the full stop.
    if IND_OF[name] == "":
        return head + "".join(s.strip() for s in body) + text[j:]
    return head + LF + LF.join(body) + LF + IND_OF[name] + text[j:]


def check_prose(p: dict, errors: list[str]) -> None:
    """The partner page's meta description quotes the cheapest tier and the top
    bundle in a hand-written sentence. Prose stays hand-written — but it may not
    quietly fall out of step with the numbers it is quoting."""
    lo = baht(min(t["amount"] for t in p["tiers"]))
    hi = baht(max(b["amount"] for b in p["bundles"]))
    meta, _ = read(ROOT / "site/partner/index.html")
    line = next((x for x in meta.splitlines() if 'name="description"' in x), "")
    for want in (lo, hi):
        if want not in line:
            errors.append(
                f"site/partner/index.html: meta description does not quote {want}. "
                f"The rate card now runs {lo} to {hi} — rewrite the sentence by hand.")


def main() -> int:
    # Every message here carries a ฿ figure, and a Windows console defaults to
    # cp1252 — without this the drift report prints escapes instead of prices.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if any page is out of step, changing nothing")
    args = ap.parse_args()

    pricing = json.loads(PRICING.read_text(encoding="utf-8"))
    errors: list[str] = []
    written: list[str] = []

    for rel, name, _ind in BLOCKS:
        path = ROOT / rel
        before, eol = read(path)
        after = replace_block(before, name, RENDER[name](pricing), rel)
        if before == after:
            continue
        if args.check:
            errors.append(f"{rel}: block '{name}' is out of step with data/pricing.json")
        else:
            write(path, after, eol)
            written.append(f"{rel} [{name}]")

    check_prose(pricing, errors)

    if errors:
        for e in errors:
            print(f"drift: {e}", file=sys.stderr)
        print("\nRun: python infra/build_pricing.py", file=sys.stderr)
        return 1

    print(LF.join(f"wrote {w}" for w in written)
          or ("checked: pages match data/pricing.json" if args.check else "already up to date"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
