"""Contrast and colour-blind separation for the dashboard's own palette.

tests/site/test_contrast.py covers site.css. analytics.css adds five colours the
public pages never use — the up/down pair on deltas and the three health states
— and puts the platform colours on a panel that is lighter than the ground the
public pages validated them against. Both of those need checking here rather
than assumed from there.

The maths is the same as tests/site/test_contrast.py: WCAG relative luminance,
and the Viénot, Brettel & Mollon (1999) dichromat simulation in linear sRGB.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SITE_CSS = (ROOT / "site" / "css" / "site.css").read_text(encoding="utf-8")
ANALYTICS_CSS = (ROOT / "site" / "css" / "analytics.css").read_text(encoding="utf-8")
CSS = SITE_CSS + "\n" + ANALYTICS_CSS


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg):
    a, b = sorted((_lum(_rgb(fg)), _lum(_rgb(bg))), reverse=True)
    return (a + 0.05) / (b + 0.05)


def token(name):
    """The last definition wins, the way the cascade resolves it."""
    matches = re.findall(rf"--{name}\s*:\s*(#[0-9A-Fa-f]{{6}})", CSS)
    assert matches, f"token --{name} not found"
    return matches[-1]


# The two grounds a number can sit on in the dashboard: the page ground and a
# panel. The panel is lighter, so it is the harder of the two.
GROUNDS = ("bg", "panel", "panel-hi")
TEXT = ("cream", "cream-dim", "muted")

def test_the_panel_token_really_is_a_panel_and_not_the_ground():
    assert token("panel") != token("bg")


def test_body_and_label_text_clear_aa_on_every_dashboard_ground():
    bad = [f"--{fg} on --{bg} is {ratio(token(fg), token(bg)):.2f}:1"
           for bg in GROUNDS for fg in TEXT if ratio(token(fg), token(bg)) < 4.5]
    assert bad == []


def test_delta_colours_clear_aa_as_text():
    """`+12.4%` is text, not a swatch, so it needs 4.5:1 and not 3:1."""
    bad = [f"--{fg} on --{bg} is {ratio(token(fg), token(bg)):.2f}:1"
           for bg in GROUNDS for fg in ("up", "down") if ratio(token(fg), token(bg)) < 4.5]
    assert bad == []


def test_health_states_clear_aa_as_text():
    bad = [f"--{fg} on --{bg} is {ratio(token(fg), token(bg)):.2f}:1"
           for bg in GROUNDS for fg in ("up", "warn", "down")
           if ratio(token(fg), token(bg)) < 4.5]
    assert bad == []


def test_platform_colours_still_clear_three_to_one_on_a_panel():
    """The public pages validated these against --bg. Chart marks here sit on a
    panel, which is lighter, so the same claim has to be re-checked."""
    weak = [f"--{p} on --{bg} is {ratio(token(p), token(bg)):.2f}:1"
            for bg in ("panel", "panel-hi") for p in ("yt", "tt", "ig")
            if ratio(token(p), token(bg)) < 3.0]
    assert weak == []


def test_a_gridline_never_out_contrasts_the_marks_on_it():
    """A gridline that reads as a series is a chart with an extra line in it."""
    grid = re.search(r"--grid\s*:\s*rgba\(([^)]+)\)", ANALYTICS_CSS)
    assert grid, "--grid is not an rgba() value"
    alpha = float(grid.group(1).split(",")[-1])
    assert alpha <= 0.15, f"--grid alpha {alpha} is too strong for a hairline"


# --- dichromat separation ---------------------------------------------------

def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


CVD = {
    "deuteranopia": ((0.625, 0.375, 0.0), (0.700, 0.300, 0.0), (0.0, 0.300, 0.700)),
    "protanopia":   ((0.567, 0.433, 0.0), (0.558, 0.442, 0.0), (0.0, 0.242, 0.758)),
    "tritanopia":   ((0.950, 0.050, 0.0), (0.0, 0.433, 0.567), (0.0, 0.475, 0.525)),
}


def simulate(hex_colour, kind):
    r, g, b = (_lin(c) for c in _rgb(hex_colour))
    return tuple(sum(m * v for m, v in zip(row, (r, g, b))) for row in CVD[kind])


def test_the_three_series_colours_stay_separable_for_colour_blind_viewers():
    """The same assertion tests/site/test_contrast.py makes, re-made here
    because the dashboard puts all three in one chart far more often than the
    public pages do."""
    too_close = []
    for kind in CVD:
        sim = {p: simulate(token(p), kind) for p in ("yt", "tt", "ig")}
        for a, b in (("yt", "tt"), ("yt", "ig"), ("tt", "ig")):
            d = sum((x - y) ** 2 for x, y in zip(sim[a], sim[b])) ** 0.5
            if d < 0.10:
                too_close.append(f"{a} vs {b} under {kind}: {d:.3f}")
    assert too_close == []


FORMAT_JS = (ROOT / "site" / "js" / "analytics" / "format.js").read_text(encoding="utf-8")


def test_a_delta_never_carries_its_meaning_by_colour_alone():
    """Green against red is the one pair a dichromat viewer cannot separate.
    The dashboard uses it anyway, and that is only defensible because a delta
    always carries a sign AND an arrow as well — colour is the third channel,
    not the first. This asserts the two non-colour channels exist."""
    assert re.search(r"export const ARROW\s*=\s*\{[^}]*up:\s*'▲'", FORMAT_JS),         "format.js no longer exports the up/down arrow glyphs"
    assert "MINUS" in FORMAT_JS and "'+'" in FORMAT_JS,         "signed() no longer emits an explicit sign"

    css = ANALYTICS_CSS
    assert '.a-delta .arrow' in css, "the delta component no longer renders an arrow"


@pytest.mark.parametrize("kind", list(CVD))
def test_how_far_apart_up_and_down_actually_are(kind):
    """Not an assertion that they separate — under deuteranopia and protanopia
    a green/red pair largely does not, and pretending otherwise would be worse
    than saying so. This records the number so that a future change to --up or
    --down that makes it *worse* is visible in the diff, and it holds the floor
    at the point where the two would be indistinguishable even as luminance."""
    a, b = simulate(token("up"), kind), simulate(token("down"), kind)
    distance = sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
    assert distance >= 0.05, f"{kind}: {distance:.3f} — even the luminance matches now"
