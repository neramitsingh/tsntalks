# Product

## Register

brand

The site is a media kit: the visitor's impression is the deliverable. The dedicated live page overrides to the **product** register (a data surface sponsors read), but it inherits the brand's visual system and voice.

## Users

- **Sponsors and their marketing people.** Thai-Indian business owners, brand managers at companies targeting the Thai-Indian community in Bangkok. They arrive from a LINE or WhatsApp link Sunny sent, usually on a phone, deciding whether a ฿15,000 to ฿185,000 package is worth it. State of mind: sceptical, comparing, five seconds of attention before they decide to keep scrolling.
- **Sunny and the TSN team.** Check the live page after an episode drops, pull numbers for a sponsor conversation, see whether the show is growing. Weekly, on desktop and phone.

## Product Purpose

TSN Talks is a Thai-Indian interview series presented by Thai Sikh News. The site sells episode sponsorship. Today every number on it is hand-typed and ages the day it is written. The live surfaces replace typed claims with numbers read from YouTube, Instagram and TikTok through Zernio, refreshed on a schedule, so a sponsor sees current reach and momentum without anyone updating the page.

Success: a sponsor reads the live page and believes the numbers without asking "as of when?". Sunny never edits a statistic by hand again.

## Brand Personality

Warm, cinematic, trusted. The house voice is "unheard stories, authentic voices": community trust rather than advertising polish. The live surfaces add a broadcast register on top: on air, last updated, the newsroom wall behind the interview studio. Confident about real numbers, never inflated.

## Anti-references

- **The current site itself** (Sep 2026): centered hero with glowing orbs, a pill badge, a strip of four identical stat boxes, a small tracked uppercase eyebrow above every section, the "Unheard stories. *Authentic voices.*" italic-serif headline formula, 29 identical episode cards with hover play buttons, Playfair Display and Plus Jakarta Sans. Ney's verdict 2026-09-15: "rework the whole design to make it look less AI generated". Keep the palette, replace everything else.
- **The second build (15 Sep 2026, Archivo condensed on near-black).** Every lint-level tell removed and still guessable: black ground, heavy condensed caps, hairline rules, one accent, sixteen-by-nine thumbnails in bordered boxes, split hero, the same headline-left lede-right grammar on every section. The streaming-platform press-kit lane. Its display face sat 300px from the artwork's Bebas-lineage capitals as a near-miss. Ney's verdict: still not it. The lesson recorded in the spec: designing by prohibition lands in the next-nearest template; start from the room, not from a rule list.
- A generic SaaS analytics dashboard: grey cards, one accent, a KPI row with sparklines, "hero metric" template.
- YouTube Studio or a Google Analytics clone re-skinned. Familiar but placeless.
- Vanity framing: rounded-up follower counts, cumulative-only totals with no time window, numbers with no source.
- Cream or beige grounds, glass cards, gradient text. The brand is dark and saffron; stay there.

## The visual world (decided 15 Sep 2026: "the studio")

The site is set in the room the show is recorded in: dark wood, amber light under the bookshelves, a warm rim on the guest. Ground colour from that room, never black. Photographs are frames from the episodes themselves (`site/img/episodes/`, `site/img/faces/`), never YouTube thumbnails, which carry a headline and the guest's name baked in. Display type is Antonio in capitals, the closest free match to the artwork's own condensed face; Bebas Neue for tracked labels; Hanken Grotesk for text. The show's mark is the gold mic logo, not a typed logotype. The home page is a sales surface first: the offer is the hero, the guests are proof, the rate card is the product. Sketches for the three directions that were weighed live in `sketches/home-S*.html`.

## Existing identity to build from (not the website)

The show's real visual language lives in its video assets, not the site: a gold vintage microphone logo with a waveform, heavy condensed gold capitals ("TSN TALKS", guest names on every thumbnail), episode stills with the guest's name set huge, and proper portrait photography of guests. The Thai Sikh News mark is the Thai and Indian flags in a saffron ring. Any redesign starts from these.

## Design Principles

1. **Position, not deficit.** Show where the show stands and where it is heading. Never a countdown, never a gap to a target.
2. **One picture first.** Every dense surface leads with a single visual of the structure (a proportion bar, a timeline, a map), then grouped detail collapsed by default. Sponsors and Sunny both read position faster than they read tables.
3. **Every number carries its window and its source.** Lifetime totals sit next to a 90-day momentum figure; each block says which platform it came from and when it was last refreshed.
4. **The show is the hero, the platforms are channels.** Episodes and guests stay visible; platform logos are labels, not the subject.
5. **Same house, different room.** The live page inherits the media kit's palette, type and motion language. It may be denser and more tabular, but it must never look like a different company.

## Accessibility & Inclusion

WCAG AA. Cream body text on the dark ground must hold 4.5:1; muted labels on tinted panels are the first place this fails, so check them. Every animation (live pulse, rolling counters, ticker) has a reduced-motion alternative: static values, instant transitions. Numbers are also written in text, never only as bar lengths. Thai and English audiences: English copy on the surface, and platform names and guest names must not be truncated on narrow phones.
