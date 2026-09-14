"""Every text colour must clear WCAG AA on the ground it is actually used on.

PRODUCT.md calls out muted labels on tinted panels as the first place this fails,
and the poster wall puts --muted-adjacent text straight onto --bg3.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[2] / "site" / "css" / "site.css").read_text(encoding="utf-8")


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
    m = re.search(rf"--{name}\s*:\s*(#[0-9A-Fa-f]{{6}})", CSS)
    assert m, f"token --{name} not found in site.css"
    return m.group(1)


def test_body_and_secondary_text_clear_aa_on_every_ground():
    bad = []
    for ground in ("bg", "bg2", "bg3"):
        for fg in ("cream", "cream-dim", "muted"):
            r = ratio(token(fg), token(ground))
            if r < 4.5:
                bad.append(f"--{fg} on --{ground} is {r:.2f}:1")
    assert bad == []


def test_accent_text_clears_aa_on_the_ground():
    bad = [f"--{fg} on --bg is {ratio(token(fg), token('bg')):.2f}:1"
           for fg in ("saffron2", "gold2") if ratio(token(fg), token("bg")) < 4.5]
    assert bad == []


def test_button_label_clears_aa_on_saffron():
    r = ratio(token("bg"), token("saffron"))
    assert r >= 4.5, f"--bg on --saffron is {r:.2f}:1"


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# Viénot, Brettel & Mollon (1999) dichromat simulation, applied in linear sRGB.
CVD = {
    "deuteranopia": ((0.625, 0.375, 0.0), (0.700, 0.300, 0.0), (0.0, 0.300, 0.700)),
    "protanopia":   ((0.567, 0.433, 0.0), (0.558, 0.442, 0.0), (0.0, 0.242, 0.758)),
    "tritanopia":   ((0.950, 0.050, 0.0), (0.0, 0.433, 0.567), (0.0, 0.475, 0.525)),
}


def simulate(hex_colour, kind):
    r, g, b = (_lin(c) for c in _rgb(hex_colour))
    return tuple(sum(m * v for m, v in zip(row, (r, g, b))) for row in CVD[kind])


def test_platform_colours_are_legible_swatches():
    """A 9px swatch is a non-text graphic: WCAG asks 3:1 against its ground."""
    weak = [f"--{p} on --bg is {ratio(token(p), token('bg')):.2f}:1"
            for p in ("yt", "tt", "ig") if ratio(token(p), token("bg")) < 3.0]
    assert weak == []


def test_platform_colours_stay_separable_for_colour_blind_viewers():
    """The spec fixes these three colours and claims colour-blind separation.
    They separate by hue, not luminance, so test that claim, not the luminance."""
    too_close = []
    for kind in CVD:
        sim = {p: simulate(token(p), kind) for p in ("yt", "tt", "ig")}
        for a, b in (("yt", "tt"), ("yt", "ig"), ("tt", "ig")):
            d = sum((x - y) ** 2 for x, y in zip(sim[a], sim[b])) ** 0.5
            if d < 0.10:
                too_close.append(f"{a} vs {b} under {kind}: {d:.3f}")
    assert too_close == []
