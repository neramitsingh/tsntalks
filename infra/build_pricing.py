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

ROOT = Path(__file__).resolve().parents[1]
PRICING = ROOT / "data" / "pricing.json"

# Which generated block lives in which page. A block is delimited by
# <!-- pricing:NAME --> ... <!-- /pricing:NAME --> inside its container div.
BLOCKS = [
    ("site/index.html", "tiers-brief"),
    ("site/partner/index.html", "tiers-full"),
    ("site/partner/index.html", "bundles"),
]

IND = "      "          # the blocks sit two levels in, as the hand markup did

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


def render_tiers_brief(p: dict) -> list[str]:
    """The homepage cards: one line of pitch, one price, no breakdown."""
    out = []
    for t in p["tiers"]:
        out += [f'{IND}<div class="tier">',
                f'{IND}  {_tag("div", "k", t["numeral"])}',
                f'{IND}  {_tag("div", "n", t.get("short_name") or t["name"])}',
                f'{IND}  {_tag("div", "d", t["short"])}',
                f'{IND}  {_price(t)}',
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
                f'{IND}  {_tag("div", "k", t["numeral"])}',
                f'{IND}  {_tag("div", "n", t["name"])}',
                f'{IND}  <div class="d">',
                f'{IND}    {escape(t["long"], quote=False)}',
                *_bullets(lines, f"{IND}    "),
                f'{IND}  </div>',
                f'{IND}  {_price(t)}',
                f'{IND}</div>']
    return out


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
        cls = "bundle flag" if b.get("flagship") else "bundle"
        was = f'Regular {baht(b["regular"])}'
        out += [f'{IND}<div class="{cls}">',
                f'{IND}  {_tag("p", "tag", b["tag"])}',
                f'{IND}  {_tag("h3", None, b["term"])}',
                *_bullets([*b["includes"], f'{baht(b["ad_budget"])} ad budget included'],
                          f"{IND}  "),
                f'{IND}  <div class="price">',
                f'{IND}    {_tag("p", "was", was)}',
                f'{IND}    {_tag("p", "now", baht(b["amount"]))}',
                f'{IND}    {_tag("p", "reach", reach)}',
                f'{IND}  </div>',
                f'{IND}</div>']
    return out


RENDER = {
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
    return head + LF + LF.join(body) + LF + IND + text[j:]


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

    for rel, name in BLOCKS:
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
