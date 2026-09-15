---
target: "https://neramitsingh.github.io/tsntalks/ (site/index.html, all three pages)"
total_score: 26
p0_count: 1
p1_count: 2
timestamp: 2026-09-15T08-13-51Z
slug: site-index-html
---
Method: dual-agent (A: design review over twelve captures at 1440 and 390, all three pages · B: bundled detector CLI plus runtime overlay injected in an isolated browser on all three pages)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Live dot, Bangkok timestamp, stale state in words, data-failed message all present. A missing still is still a silent empty box. |
| 2 | Match System / Real World | 3 | Plain language, ฿ finally in the right face. The contact channel is `mailto:` for an audience that arrives from LINE. |
| 3 | User Control and Freedom | 3 | Sticky nav, anchors, collapsibles. Every tile is `target=_blank` with no cue. |
| 4 | Consistency and Standards | 3 | One system throughout. /live injects an `<h3>` straight under the `<h1>` at runtime; the founder quote is set as a heading. |
| 5 | Error Prevention | 3 | Static site, prefilled mail subject, price drift gated in CI. |
| 6 | Recognition Rather Than Recall | 2 | "Bundle A / B / C"; bundle bullets refer back to tiers without linking; platform colours must be carried between sections. |
| 7 | Flexibility and Efficiency | 2 | No way to compare ten offers, no per-episode lookup, nothing forwardable as one card. |
| 8 | Aesthetic and Minimalist Design | 2 | Minimal in ornament, not in load, and the aesthetic is the category default. |
| 9 | Error Recovery | 2 | Data failure handled; image failure is not (no typographic fallback tile). |
| 10 | Help and Documentation | 3 | The /live footnote on windows and platform delay is exactly right; the reach disclaimer is 13px muted under five cards. |
| **Total** | | **26/40** | **Competent, not distinctive (up from 21 this morning)** |

## Anti-Patterns Verdict

**Does this look AI-generated? After a beat, yes. Not instantly any more.** The lint-level tells from this morning are gone: no text over photographs, no view-rank decay gradient, no italic-gold slot in every heading, no roman numerals, price in the fold, ฿ in the right face. What is left is the system itself, and the system is guessable.

**Second-order reflex, confirmed.** Brief: "dark podcast media kit, not SaaS-cream, not editorial." The next place a model lands is exactly what shipped: black ground, heavy condensed grotesk caps, hairline rules, one saffron accent, 16:9 thumbnails in bordered boxes, tabular numbers, split hero (type left, image right), and the same section grammar on every section of every page (caps headline left, small lede top-right, hairline, content). The lane is the **streaming-platform press kit** (Netflix Tudum, Spotify Advertising, DAZN media pages). A competitor would describe theirs in the same sentence.

**The rework's core move backfired in one specific way.** Archivo at 70% width was chosen to match the artwork. It sits 300px from the artwork and is a near-miss of it: the thumbnails use a taller, narrower Bebas-class face with a different R and S. Similar-but-not-identical is the banned pairing. It reads as a knock-off of the show's type rather than the show's type.

**The show's identity assets appear nowhere except inside thumbnails.** The nav mark is typed "TSN TALKS" in Archivo, not the gold mic logo. The real logo appears once on the entire site, inside the middle showreel still on /partner. No portrait is ever large. No image is full-bleed. The studio's warm orange rim light, visible behind every guest, is absent from a palette that is flat #0D0706. Brand words in PRODUCT.md: warm, cinematic, trusted. The site delivers trusted.

**Deterministic scan:** the static CLI over all three HTML files returned **0 findings, exit 0**. The runtime overlay found **21** (home 6, live 10, partner 5). Most are false positives: `all-caps-body` on 31 to 42 character UI labels, buttons and table captions; `tight-leading` on display headings set at .95 deliberately; `ai-color-palette` on TikTok teal, which PRODUCT.md fixes for the life of the project. Four are real: `tracked-caps` on `.ep-line`, the one surviving gold eyebrow-with-rule, and it is the first element on the page; `all-caps-body` on the 134-character founder quote in condensed caps; `skipped-heading` on /live, where `live.js` injects `<h3>TikTok</h3>` under the `<h1>` at runtime, invisible to the static scan; `line-length` at ~173 characters on the /partner tier descriptions, which have no max-width in a 1,100px column.

**Visual overlays:** injection succeeded on all three pages in an isolated browser; the overlays were captured to `scratchpad/shots/overlay-{home,live,partner}.png` and the tabs were closed afterward. No overlay is open in a browser tab now.

## Overall Impression

The engineering is right and the design is a default. Two reworks in one day both operated at stylesheet level: swap the display face, remove the tells, obey the anti-reference list. Designing by prohibition produces the next-nearest template every time, which is why the lane moved from editorial to streaming press kit and the "vibecoded" read survived. The single biggest opportunity is the one PRODUCT.md already names: the show has a visual world (warm-lit studio, portraits, gold mic mark, names set huge) and the site has never used it as material, only as thumbnails in boxes.

## What's Working

1. **The honesty system.** Every figure carries its window and source; stale is said in words; the /live footnote names Zernio, both rolling windows and the 48-hour platform delay; the reach disclaimer separates underwritten targets from measurements. This is the product's actual differentiator, and it is executed properly.
2. **Price in the fold, rate card as static markup.** A sponsor knows the floor inside one screen, it reads with JavaScript off, and drift is caught three ways in CI.
3. **The /partner showreel.** Three stills whole, captioned "Your branding sits in this frame." The one place the site shows the thing being sold, and the one place the real logo appears. Artwork-whole also structurally removed every text-over-image contrast failure from this morning.

## Priority Issues

**[P0] Direction: the system is the category reflex and ignores the show's own identity.**
Why it matters: Ney's brief was "less AI generated"; the rework removed the tells and kept the template, and the type now sits beside the artwork as a near-miss. One of three brand words delivered.
Fix: a shape session that names one lane and builds from the show's assets. Use the real mic logo as the mark, the artwork's exact face for display, at least one full-bleed portrait per page, the studio's light in the ground colour. Keep the data system, the rate-card pipeline, the copy, and artwork-whole wherever thumbnails remain.
Suggested command: `/impeccable shape`, then `/impeccable bolder`.

**[P1] The home page reads as a YouTube channel page in a dark skin.**
Why it matters: the hero and the lead wall tile are the same image (`AXukyl9hVp0`, verified in the DOM), one screen apart. Below it, ten 16:9 thumbnails shown whole, each designed to shout in a feed, make the site's entire imagery YouTube packaging. Artwork-whole fixed the scrim problem and created this one. About 3,000px of phone scroll for a sponsor who may recognise none of the faces.
Fix: never repeat the hero episode in the wall; demote the wall to a strip of names and faces (or an `/episodes` page); use clean frames or portraits, not thumbnails, for any large image; add a typographic fallback tile (guest name set large on `--bg3`) so a slow or missing still is never a black hole.
Suggested command: `/impeccable layout`, then `/impeccable harden`.

**[P1] /partner is ten offers with no decision aid, and the CTA is the wrong channel.**
Why it matters: tiers are unsorted, so the first row a reader meets is ฿25,000 after the hero promised "from ฿15,000"; ฿20,000 appears twice; per-episode and per-month are mixed; bundles are named by letter in five identical cards; tier descriptions run ~173 characters per line at 1440; "Talk to us" opens a mail app inside LINE's in-app browser, which is where the sponsor came from; 5,190px of phone scroll with no sticky CTA.
Fix: open with a two-way fork ("Sponsor one episode, from ฿15,000" / "Run a campaign, from ฿29,000"); sort tiers by price; rename bundles by outcome; collapse the five cards into one comparison table with the flagship highlighted; primary CTA a LINE or WhatsApp deep link with the tier prefilled, email secondary; sticky CTA on phone; `max-width: 62ch` on `.tier .d`.
Suggested command: `/impeccable distill`, then `/impeccable clarify`.

**[P2] /live draws decline and shouts at its own charts.**
Why it matters: the month chart is one 1.25M column (November 2025, one TikTok at 943,699 views) then a flat line to today. Honest, and as drawn it violates "position, not deficit": the takeaway is "peaked ten months ago". The big-number-plus-label-plus-three-columns block is the hero-metric template PRODUCT.md bans. The runtime `<h3>` under the `<h1>` is a real heading skip.
Fix: lead with a 90-day position block (net subscribers, hours watched, 90-day views) before the lifetime total; re-express lifetime as "where the 2.37M came from" by platform and episode rather than a time series that ends flat; make the platform legend headings `<h2>` or plain `<p>`.
Suggested command: `/impeccable shape` for the chart story, `/impeccable polish` for the heading.

**[P2] Founder block and the pull quote.**
Why it matters: the white studio cut-out on a cream plate is still the brightest object on the site; 134 characters of condensed all-caps is a headline, not a person speaking.
Fix: a real portrait or the cut-out on a saffron plate; the quote in the text face at 24 to 28px with a gold rule.
Suggested command: `/impeccable polish`.

**[P2] Hero composition.**
Why it matters: split template; the image floats vertically centred with dead space below it on desktop; a four-line all-caps tagline beside artwork that already shouts; the gold eyebrow-with-rule is the banned kicker and it is the first thing on the page; the identity is a typed logotype.
Fix: pick one, not a blend: artwork full-bleed with minimal site type over a clear zone, or type-led with the portrait at full column height. Kill the eyebrow. Put the mic logo in the nav.
Suggested command: `/impeccable layout`.

## Persona Red Flags

**Sceptical sponsor, phone, from a LINE link.** Finds the price at 650px (good). Then 3,000px of thumbnails of people they may not know; no sponsor logos or "founding sponsor" framing anywhere, so a media kit with zero social proof from buyers; tiers open at ฿25,000 after "from ฿15,000"; "guaranteed reach" beside "views" with the distinction in 13px muted text; ends at a `mailto:` inside LINE's browser. Nothing on the page can be forwarded as one card.

**Sunny, desktop, after an episode drops.** /live puts "Now playing" fourth and last; the only per-episode figure on the site is under that tile; no week-over-week anywhere; the 2,366,212 strap will not visibly move for him; the month chart says nothing about this week. /live is built for the sponsor, not for the second user PRODUCT.md names. If Plan 3 is his surface, /live should say so.

**First-timer.** "Bundle A / B / C", "signature segment", "lower third", "end card" undefined; Thai Sikh News is not explained until the fourth section; tiles jump to YouTube with no cue; season one, the show's proof of longevity, is one collapsed line.

## Minor Observations

- Month labels at 10.5px muted on a 300px chart; the phone chart scrolls sideways with no affordance beyond a thin scrollbar.
- Two "Sunny Chawla" tiles back to back with only the role line to tell them apart. Only one guest carries "Mr."
- "SEASON TWO" on the site against "SEASON 2" in the artwork.
- Bundle `h3` strings are data ("ONE MONTH · BUNDLE B · PREMIUM · MOST POPULAR"), not names.
- Three Google font families, one variable with a width axis, for a Thai 4G in-app-browser audience; nothing self-hosted.
- The `rise` animation on the h1 is the only motion apart from the live dot. The brand register permits one orchestrated load and this is a shrug.
- Home footer carries no timestamp; only /live repeats "Updated".
- 11px labels (`.po .n`, table `th`) on phones.

## Questions to Consider

- If the only text on the home page were the guests' names, would a sponsor still understand what they are buying?
- Why does a show with a logo have a typed logotype?
- Where is the studio's orange light in the palette? What does "warm" look like in pixels here?
- Should the wall be a wall at all, when the show is one guest at a time?
- Is 2.37M the number to lead with when 53% of it is one TikTok from November? What number would Sunny defend across a dinner table?
- Where does the sponsor actually reply: email, or the LINE thread they came from?
- Would Sunny put this on a screen at a Thai-Indian business dinner and feel it is his show, or a page about his show?
