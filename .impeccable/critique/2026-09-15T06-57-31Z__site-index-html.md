---
target: "https://neramitsingh.github.io/tsntalks/ (site/index.html)"
total_score: 21
p0_count: 2
p1_count: 3
timestamp: 2026-09-15T06-57-31Z
slug: site-index-html
---
Method: dual-agent (A: design review, browser-inspected at 1440 and 390 across all three pages · B: bundled detector + measured contrast in an isolated browser process)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | The page is titled "the numbers, *live*" and is serving stale data: `#strap` carries `strap stale`, so the pulse is suppressed and the only signal is a colour dim. `home.js:30` never prints the "N hours ago" that `live.js:230` does. |
| 2 | Match System / Real World | 3 | Copy is plain and sponsor-shaped, windows are named. Undercut by roman numerals implying a rank the prices contradict. |
| 3 | User Control and Freedom | 3 | `<details class="twin">` is a real escape hatch. `scroll-behavior: smooth` is forced globally; the only route home from `/partner` is the wordmark. |
| 4 | Consistency and Standards | 2 | The same five tiers are named differently on home vs `/partner`. Two live bundle taxonomies. `฿` renders in a different typeface from its own digits site-wide. Every table's header row is byte-identical to its data rows. |
| 5 | Error Prevention | 3 | The underwritten-vs-measured disclaimer at `partner/index.html:206` is genuinely good. `live.js:204` `img.remove()` turns a dead thumbnail into an unexplained black panel. |
| 6 | Recognition Rather Than Recall | 2 | Five tiers on home, the same five renamed and expanded on `/partner`, plus five bundles. Home and `/live` duplicate identical audience tables. |
| 7 | Flexibility and Efficiency | 2 | No comparison across 10+ priced options, no export, no sort/filter on 32 guests, nothing copyable for Sunny mid-call. |
| 8 | Aesthetic and Minimalist Design | 2 | Coherent, but the restraint *is* the reflex lane, and the dead space (211px hero gap, ~380px under the proportion bar, ~330px × 5 in the tier grid) is unmanaged rather than composed. |
| 9 | Error Recovery | 2 | `live-data.js:144` sets `.data-failed` and no stylesheet rule matches it. No `<noscript>` on any page. A dual-source failure ships three pages of headings over empty slots, silently. |
| 10 | Help and Documentation | 3 | The `/live` source footer — source, both windows, cadence, the 48h reporting delay — is the best writing on the site. |
| **Total** | | **21/40** | **Below average; structurally sound, compositionally generic** |

## Anti-Patterns Verdict

**Does this look AI-generated? Yes — and not for the reasons a linter can see.**

**Deterministic scan.** The bundled detector returned **2 findings, 0 errors**, and on inspection **both are false positives**:

- `side-tab` at `site.css:203` — not a card accent, it's the CSS-triangle play glyph inside the hero Watch button (`border-left: 12px solid` + transparent top/bottom). Every other `border-left/right` in the file is a 1px separator.
- `broken-image` at `live-data.js:93` — line 93 is a *code comment* containing the literal string `<img>`. Measured at runtime: 13/13 images load on home, 4/4 on live, zero broken images anywhere.

Against the shared absolute bans, the page is also clean where it counts: **no** `background-clip: text` gradient (0 matches), **no** `backdrop-filter` or glass (0 matches, and 0 `box-shadow` in the entire stylesheet), **no** arbitrary z-index (all 6 values small and ordered), **no** page-level horizontal overflow at 1440 or 390, **no** content-gated reveals, and **zero** reflex-reject fonts.

**That clean bill is the finding.** The slop here is not lint-level. It is compositional and second-order, which is exactly why it survived a rebuild that was explicitly briefed to avoid it.

**The second-order reflex — the direct answer to "still looks vibecoded".** Given the brief's anti-references (*not* cream, *not* SaaS-dashboard, *not* Playfair/Jakarta, dark + saffron), there is exactly one place a competent model lands next: **editorial-typographic**. That is what shipped, feature for feature against the fingerprint:

| Editorial-typographic fingerprint | What TSN Talks ships |
|---|---|
| Display serif, often italic | Bodoni Moda 400–900 with a full italic axis; italic on every heading |
| Small tracked metadata labels | 11–13px / .12–.14em uppercase, 9 CSS rules, 8 rendered on home, 7 on partner |
| Ruled hairline separators | `--rule` as 1px on the strap, index list, every table row, every legend card, the founder block, the tier block, every bundle, the footer |
| Monochrome restraint | One hue family across three pages; TikTok teal and Instagram purple survive only as 9px data swatches |
| No imagery | `/partner` — the page where money is decided — has **0 images**, verified in the DOM |

**Bodoni Moda is not on the reflex-reject list, but it is the substitution move.** The list bans Playfair Display, which the *old* site used; the rebuild reached for the nearest un-banned Didone. Same shape, same lane, one name over. The detector cannot see this, and it is the single largest contributor to the verdict.

**The eight named tells, ranked by contribution to the "vibecoded" read:**

1. **Every image contains the show's own typography, cropped mid-word, with the site's typography printed on top.** Raw YouTube `maxresdefault.jpg` stills already carry TSN Talks' real identity — heavy condensed gold caps, the guest's name huge. `site.css:157` crops at `object-position: 70% 30%`, scrims it, then `.guest` sets the same name *again* at 136.8px Bodoni six inches left. On the 390px poster wall: "USD / ERED TO THE FIRST / AN IN HISTORY.", "WHY I LAUN / HUMAN ST / THA", "UKHDEV / SETHI" — ten tiles, every one mutilated and double-named. The CSS comment at `site.css:163` proves the author saw this and answered it with a heavier gradient instead of a composition.
2. **The headline formula the brief explicitly banned is on every heading of every page.** Nine headings, one construction — roman words → comma → italic gold word → full stop — driven by `h1 em, h2 em, h3 em { font-style: italic; color: var(--gold2) }` at `site.css:105`. "Season two, *so far.*" · "Who is *listening.*" · "Put your brand *in the room.*" · "The numbers, *live.*" · "When the hits *happened.*" · "Who is *watching.*" · "Now *playing.*" · "Five ways *to partner.*" · "Best value *packages.*" That is a template with a slot, not a voice.
3. **Italic-gold applied to thirteen unrelated element types on home alone** — the wordmark, three heading `em`s, the `M` suffix on the big number, both table captions, all five roman numerals, the pull quote. One decorative move stretched across every category is the signature of a style declared rather than designed.
4. **The hero-metric template, banned by name, appears three times** — `live/index.html:41` (150px `.bignum` over a `.fine` label), `index.html:66` (same pair), and the 4-cell `.strap`. Rendering it in Bodoni instead of Inter does not change what it is.
5. **Five identical cards in a row on `/partner`, each with a tracked uppercase eyebrow above its heading.** `repeat(auto-fit, minmax(240px,1fr))`, each card tag → h3 → bullets → price. Measured: 5 of 5 `.bundle .tag` sit directly above the card's `<h3>`. And the taxonomy was never merged — "Starter · Brand intro", "Growth · Visibility boost", "Bundle A", "Bundle B · Premium · Most popular", "Bundle C · Flagship" are two naming systems shipped together.
6. **Roman numerals as pricing scaffold, contradicting the data.** I–V imply rank; the prices run ฿25,000 / ฿20,000 / ฿15,000 / ฿70,000 / ฿20,000. Not ordered by price, value, or anything. Scaffolding because "pricing sections have numbers".
7. **The currency symbol is in a different typeface from every price.** Hanken Grotesk has no Thai block, so `฿` (U+0E3F) falls back to a system face at all 15+ price points — narrower, double-barred, taller than the cap height beside it. On a Thai media kit whose whole job is quoting baht, this is a half-second tell.
8. **Unmanaged dead space where a layout decision belongs.** 211px of empty ground between the CTA and the strap in an 828px hero; ~380px of void under the proportion bar while the right half carries two tables; `.tier`'s title column computes to 498px to hold "Signature segment" — ~330px of nothing, five rows deep.

**Visual overlays:** none. Neither assessment injected the detector into the page, so there is no overlay in a browser tab to look at. The evidence is the measurements plus screenshots at `scratchpad\home-1440.png`, `home-390.png`, `live-1440.png`, `live-390.png`, `partner-1440.png`, `partner-390.png`.

## Overall Impression

The engineering under this site is better than the design on top of it. Provenance, data-contract and contrast discipline are genuinely strong — the parts that are hard to get right are right. What's wrong is that the visual system was *specified* rather than *designed*: a display serif, an italic accent, a tracked micro-label and a hairline rule were chosen once and then applied everywhere they would fit. That is what reads as generated.

**The single biggest opportunity: the show's real identity is already in the building, and the site is painting over it.** Heavy condensed gold capitals, a gold vintage mic mark, guest names set huge — all sitting underneath the scrim on every tile, covered with a gradient and replaced by a Didone. There is no condensed face anywhere in the stylesheet. Swapping `--display` from Bodoni Moda to a condensed gold display face collapses tells 1, 2, 3 and the second-order lane verdict simultaneously — more slop signal removed by one substitution than any other change available.

## What's Working

1. **Provenance discipline, and it is the best thing here.** Every table caption names its own window and platform because `barTable()` makes the caption a required argument, not an optional one. The `/live` footer names the source, both rolling windows, the collection cadence *and* the 48-hour platform reporting delay. `partner/index.html:206` draws the line between underwritten targets and measured numbers in plain English. This is the part that would survive a hostile buyer, and it is what PRODUCT.md says success depends on.
2. **The baked-then-live data contract.** `live-data.js:121` renders from committed JSON first, then re-renders from Storage only if `fetched_at` is newer. No spinner, no skeleton flash, no layout shift, either source can die without taking the page down — and every formatter lives in one module, so two pages cannot round the same figure differently.
3. **Contrast on a dark saffron ground — the hard case — holds almost everywhere.** Measured across **544 text elements at both 1440 and 390: zero failures on flat backgrounds.** `--muted #A08468` is the weakest token and still clears 5.71:1 on `--bg`, 5.53:1 on `--bg2`, 5.29:1 on `--bg3`. PRODUCT.md predicted muted labels on tinted panels would be the first failure; they aren't. Reduced motion covers 7 of 8 animations, each named individually rather than blanket-killed.

## Priority Issues

### [P0] The imagery pipeline is fighting the brand instead of using it

**Why it matters:** It is the first thing on the page, it is where the eye lands, and it is *why* the site looks generated — the brand is present in the pixels and the design is painting over it. It also directly violates PRODUCT.md's "any redesign starts from these."

**Fix:** (a) Crop tiles to the guest's face — `object-position: 50% 22%` with a 16:9→1:1 crop so the baked title band is cropped *out*, not scrimmed. (b) Delete the duplicate name overprint on `.po.big`/`.po.mid` (`home.js:58`); the still already says it. (c) Set `--display` to a **condensed gold display face** and demote Bodoni Moda to the pull quote, or drop it. Alternative if licensing blocks it: 10 clean guest portraits into `img/episodes/` — the override chain at `live-data.js:82` already supports it with no code change.

**Suggested command:** `/impeccable craft hero + poster wall` (a rebuild, not a polish)

### [P0] The primary persona never reaches a price

**Why it matters:** PRODUCT.md's sponsor arrives from a LINE link, on a phone, with five seconds, deciding on ฿15k–฿185k. On a 390px phone `#partner` starts at y=5,485 of a 7,121px page — **77% down, about 6.5 screens**. Above it: a 1,040px poster wall of four-digit view counts and a 1,365px column of 22 season-one names. The nav CTA is the only hint this is a sales surface, and `site.css:546` drops the nav to two items below 560px.

**Fix:** Put the offer in the fold — one line under `.role`, before `.watch`: *"Sponsor an episode from ฿15,000 · in front of 2.37M views across three platforms"*, with the saffron `.btn` primary and `.watch` demoted. Kill the 211px gap (`.strap` margin 64px→24px, hero `min-height` 78vh→68vh on phones). Move `#partner` above `#guests`, and collapse the 22-name season-one list into a `<details>`.

**Suggested command:** `/impeccable layout site/index.html`, then `/impeccable clarify` for the hero line

### [P1] The heading formula and the editorial lane are the "vibecoded" read

**Why it matters:** This is the second-order reflex, and it is why the page reads as AI *even though every individual choice is defensible*. Monoculture never announces itself in any single value — which is exactly why the detector came back clean.

**Fix:** (a) Rewrite all nine headings so no two share a construction — one single word, one question, one number, one fragment with no punctuation — and delete the `em`-italic-gold rule entirely; carry emphasis in weight and size. (b) Cut tracked uppercase labels to **at most two**, made a named system. (c) One place for gold italic — the wordmark — and nowhere else. (d) Replace `--display` per P0. (e) Strip `--rule` from `.strap`, `.founder`, `.legend .card`, `details.twin`, `footer`; six fewer hairlines and it stops reading as a type specimen. (f) Delete the dead `.eyebrow` rule (`site.css:110`, referenced in zero HTML and zero JS) and the dead `--gold` token (`site.css:18`).

**Suggested command:** `/impeccable typeset`, then `/impeccable bolder site/css/site.css`

### [P1] `/partner` ships zero imagery and twelve priced options

**Why it matters:** Zero imagery on an image-led brief is a bug, not restraint — and on the page where money is decided, the show itself is entirely absent. Twelve options with no comparison affordance is a decision the visitor defers. The real count is twelve: five tiers, five bundles, plus ฿20,000 Basic / ฿45,000 Standard **hidden inside a bullet** at `partner/index.html:107` in 13.5px muted.

**Fix:** (a) Ship imagery — a full-bleed studio still behind the `h1`, one guest portrait per tier showing that placement in situ. The assets exist in the episodes. (b) Collapse to **three** headline offers (Episode ฿15k, Month ฿70k, Flagship ฿185k) with the rest behind one `<details>`. (c) Give price the hierarchy: `.tier .p` from 18px to `clamp(26px, 2.6vw, 34px)` in `--display`; swap the `.tier` grid from `64px 1fr 1.2fr auto` to `1fr auto` and kill the 330px dead column. (d) `min-height: 2.6em` on `.bundle .reach` so the five prices share a baseline — measured, the flagship ฿185,000 is the one out of line, at y=1819 against 1839 for the other four. (e) Pick one bundle taxonomy. (f) Fix `฿` — add `'Noto Sans Thai'` to the `--text` stack ahead of the fallbacks, or use `THB `.

**Suggested command:** `/impeccable distill site/partner/index.html`

### [P1] Five real contrast failures the flat-background pass could not see

**Why it matters:** A flat-background contrast walk passes 544/544, which is why this was invisible. Pixel-sampling the glyph boxes against the actual photograph behind them finds five failures — all the same element, the 11px uppercase tracked kicker over a third-party thumbnail:

| Page | p5 ratio | % of glyph box below 4.5:1 | Element |
|---|---|---|---|
| live | **1.41** | **62.3%** | `.po.big .t .n` — "Latest episode · 23 Aug 2026", `--gold2` |
| live | **2.81** | 37.7% | `.po.mid .t .n` — "Top on Instagram", `--ig #7C6BF0` |
| home | **3.48** | 14.8% | `.po.mid .t .n` — "S2 · E9", `--gold2` |
| live | 4.35 | 7.8% | `.po.mid .t .n` — "Top on TikTok", `--tt` |
| live | 4.67 | 3.0% | `.po.mid .t .n` — "Top on YouTube", `--yt` |

The CSS comment at `site.css:269` already anticipates this — *"a platform-coloured kicker needs a real ground under it"* — and the scrim was strengthened for `.wall.now .po.mid`. The measurement says it still isn't enough, and `.po.big` on `/live` never got the treatment at all.

**Fix:** Give `.po .t .n` a solid ground rather than a gradient — a filled chip in `--bg` at 85% alpha; a text shadow is not enough at 11px/700. Extend it to `.po.big` on `/live`. If the face-crop fix in P0 lands, the kicker may leave these tiles entirely, which solves it structurally.

**Suggested command:** `/impeccable polish site/css/site.css`

### [P2] The live promise is not being kept, and the failure state is unstyled

**Why it matters:** The entire differentiator is "these numbers are live". Right now the deployed strap carries `strap stale` and `/live` reads "5 hours ago". A muted colour shift is not a status indicator — nobody notices the absence of a dot they never saw. Worse, `live-data.js:144` sets `.data-failed` and **no rule matches it** anywhere in the CSS or HTML; there is no `<noscript>` on any page; and every figure on home and `/live` is injected into an empty container. A dual-source failure ships three pages of headings over blank slots, silently, contradicting the comment at `live-data.js:117` that promises the opposite.

**Fix:** (a) `home.js:30` should emit the same `· N hours ago` that `live.js:230` does, and `.strap.stale` should carry a visible amber marker, not just dim. (b) Add the missing `.data-failed` rule with a real message. (c) Fix the collector or raise `STALE_AFTER_MS` (3h against an hourly collector means two missed runs kills it). (d) Call the existing `clip()` helper at `live.js:184` instead of `.slice(0, 70)` — it is defined at `live.js:10` for exactly this and never called anywhere, which is why captions truncate mid-phrase with no ellipsis. (e) `scrollbar-width: thin; scrollbar-color: var(--rule-hi) transparent` on `.cols-scroll` so the OS scrollbar stops cutting a white band across the chart.

**Suggested command:** `/impeccable harden site/js`, then `/impeccable polish site/live`

### [P2] The only photograph of a person on the site is distorted and unmasked

**Why it matters:** `index.html:80` sets `width="380" height="475"` on an **800×706** source, and `site.css:401` sets `width: 100%` with **no `object-fit`** — so the presentational height survives and the computed style is `object-fit: fill`. Measured: natural aspect ratio 1.133, rendered 0.800. **The face is squeezed 29.4% horizontally.** Separately, 60.9% of that box is near-white (corners read 252,252,252) — a studio cut-out on a `#0D0706` page, a 20:1 hard-edged rectangle that is now the brightest object on the entire site. `filter: saturate(.9)` does nothing to it.

**Fix:** Add `object-fit: cover` (or drop the `height` attribute), and either knock the background out to a transparent PNG or set it deliberately in a white plate with a caption. The offset outlined rectangle behind it (`site.css:402`, `z-index: -1`) currently reads as a stray bracket poking out of a white block rather than a frame.

**Suggested command:** `/impeccable polish site/index.html`

### [P2] Every table's header row is visually identical to its data rows

**Why it matters:** `site.css:327` styles `table.rep th` as 11px/600/uppercase/.12em/muted. Line 332 then targets `table.rep tbody th`. The tables are built with `innerHTML` and rows are appended without an explicit `<tbody>`, so the browser auto-inserts one — and `tbody th` therefore matches *every* `th`, including `scope="col"`, overriding all five properties. Measured on `#monthstab`, header and data rows compute identically: 14px / 400 / none / normal / same colour / same border. Confirmed across all six tables on the two data pages. Semantically fine for screen readers; visually, the header row of every table on the live-numbers page is indistinguishable from its data.

**Fix:** Change the line 332 selector to `table.rep tbody th[scope="row"]` so it stops matching column headers.

**Suggested command:** `/impeccable polish site/css/site.css`

## Persona Red Flags

**Sceptical Bangkok brand manager — LINE link, phone, five seconds, ฿15k–฿185k.**

- Sees a guest's name and job title. Does not learn what TSN Talks is, who it reaches, or that it can be sponsored. The `.ep-line` wraps at 390px with an orphaned "2026".
- The `.strap` breaks at 390px: the `border-right` on the first span lands at the wrap point, leaving a dangling vertical rule at the right edge.
- Scrolls once into the poster wall: ten tiles reading **2,579 down to 131 views**, two of them indistinguishable "Sunny Chawla" tiles because `site.css:289` hides the episode number on small tiles. The first evidence he meets contradicts the 2,366,207 strap he just read.
- Scrolls six more screens before a price appears.
- If he taps Partner instead: a text-only page, no face, no logo, five options then five more, tier prices in 18px with the roman numerals set bigger than them.

**Sunny, pulling numbers mid sponsor conversation.**

- Opens `/live`, footer says **"5 hours ago"**. He has to explain the delay out loud — the exact failure PRODUCT.md defines success against.
- There is no all-platform 90-day momentum figure anywhere. The four `.facts` are YouTube-only, and the headline one — 8,346 views in 90 days — sits 400px under "2.37M". If the sponsor reads both, Sunny is defending a 300:1 gap with no on-page framing. PRODUCT.md Principle 3 asked for lifetime *next to* momentum; that figure does not exist.
- "Now playing" leads with the latest episode at **219 views**, beside three black rectangles (three of four tiles have `currentSrc === null`).
- Nothing is copyable or exportable. To send a number he screenshots or retypes it.

**Screen-reader user.** The home page's `h1` is `.guest` — a person's name that changes weekly. A user lands and hears "Sunny Khurana, heading level one" with no page identity. The hero `<img>` is correctly `alt=""` as decoration, but `home.js:13` then assigns `alt="<guest> on TSN Talks"` to the replacement, so the decorative still becomes an announced image duplicating the `h1`.

**Low-bandwidth 4G phone — the realistic LINE arrival.** 13 remote `i.ytimg.com` images on home at ~1280×720 each, with an error-chain fallback that fires a *second* request per failed tile. The hero is `loading: eager`. Four variable font files, Bodoni Moda carrying both an optical-size and a full italic axis at 400–900, when the design uses exactly 400/500/600/700.

## Minor Observations

- `.guest` computes to **136.8px** at 1440 (clamp max 148px) and `.bignum` to 129.6px (max 150px) — both above the 96px display ceiling. The hero shouts the same name the still behind it is already shouting; the two cancel.
- The type scale is flat in two places: **twelve distinct font sizes inside a 7.5px band** (10.5→18px, adjacent ratios 1.03–1.09), and headings collapse on phones — h1/h2 is 1.31× at 1440 but **1.11× at 390**, because h1 hits its 40px floor at ~667px while h2 is still descending to 36px. On every phone the H1 and H2 are effectively the same size.
- `nav.over` is `position: absolute` — the nav scrolls away and never returns. On a 7,121px mobile page the Partner CTA is reachable for the first 844px only.
- `overflow-x: hidden` on `body` is masking rather than fixing whatever was overflowing.
- `.index h3 small` renders "Season one22 episodes" with no separator in the text layer — fine visually, concatenated for screen readers and in `textContent`.
- Bundle B and Bundle C both headline "One month"/"Two months" while the differentiating information sits in the eyebrow above; the `<h3>` is doing no work.
- The `/live` TikTok thumb is upscaled 1.45× (300px source into a 436px box); the Instagram thumb is a 9:16 portrait cover-cropped into a 9:4 letterbox, discarding ~79% of the frame.
- One reduced-motion gap: `.watch b::after`'s 0.25s border-colour transition isn't covered, because the `*` reset matches elements, not pseudo-elements. Cosmetic, not vestibular.
- The home page `<title>` — "TSN Talks — Thai-Indian stories, told at length" — is a better proposition line than anything on the page. It should be *in* the hero.
- `text-wrap: balance` is on all four display selectors; no `text-wrap: pretty` anywhere, so body copy gets no orphan control.

## Questions to Consider

1. **What if the site had no serif at all?** If `--display` were the show's own condensed gold face and Bodoni Moda were deleted, would the page still read as AI-generated — or would it suddenly read as *TSN Talks*? This single substitution removes more slop signal than any other change available.
2. **Why is the poster wall sorted by view count?** `home.js:41` sorts season two descending, which guarantees the largest tile carries the largest number and the rest visibly decay — a deficit gradient, the exact shape PRODUCT.md Principle 1 forbids. What if it sorted by recency or guest stature, and the view counts came off the tiles entirely? The tiles' job is "these are real people you've heard of", not "here is our traffic".
3. **Is 2.37M the right headline at all?** Most of it is one TikTok video from November. What if the headline were *"Nine Thai-Indian business leaders on the record this season"* — a claim no competitor can match and no chart can undercut — with 2.37M demoted to support?
4. **Should there be a `/partner` page at all?** The same five tiers live on both pages with different copy, so they will drift. What if home *were* the media kit, and `/partner` became the long-form terms page a buyer opens only after saying yes?
5. **Who is this for — the sponsor, or Sunny?** They want opposite things: a sponsor wants three options and a face; Sunny wants twelve options and every number quotable. Right now `/partner` serves neither. Which one loses?
