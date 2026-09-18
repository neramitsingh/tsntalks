# TSN Talks Plan 4: Charts on Observable Plot

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-drawn SVG inside `site/js/analytics/charts.js` with Observable Plot, keep every contract the dashboard already tests (table twins, focus-and-hover tooltips, fixed platform colours, the legend rule, no dual axes), and fix the five reading defects Ney found on the 16-Sep screenshots: fractional ticks on integer counts, a full axis drawn for an all-zero window, the last date label colliding with its neighbour, "Gained" and "Lost" both saffron on the subscribers panel, and three platforms of different magnitude stacked into one column.

**Architecture:** `charts.js` keeps its public API — `chart(spec)`, `panel`, `windowSub`, `legend`, `tableTwin`, `sparkline`, `empty`, `errorNote`, `notReported`, `SERIES_COLOR`, `seriesColor`, `seriesName` — and the four exported drawing primitives keep their names and signatures. Their bodies change from "compute pixels, emit `<path>`" to "build a Plot spec, call `Plot.plot()`, decorate". Plot owns scales, axes, ticks, gridlines and marks; a post-pass adds the class names the CSS and the tests rely on (`a-line`, `a-bar`, `a-gridline`, `a-axis`, `a-peak`), strips Plot's own stylesheet and fixed width, and lays an overlay of focusable `.a-point` hotspots over the marks, positioned with the plot's own scales, so `wireTooltip()` and every tooltip test are untouched. One new kind, `multiples`, draws one small chart per series with its own y-scale and a single shared twin, for the case where stacking hides everyone but TikTok. x is always a band scale of period labels; Plot draws only the ticks it is given, so thinning is explicit and the last label is no longer forced.

**Tech Stack:** d3 7.9.0 (cdnjs, SRI-pinned) and `@observablehq/plot` 0.6.17 UMD (jsDelivr original dist file, SRI-pinned — cdnjs does not host Plot, checked 2026-09-18; Plot's UMD needs the `d3` global first). Plain ES modules, no build step. Playwright (Python) + pytest, served from `tests/analytics/conftest.py` with both libraries cached under `tests/analytics/stubs/vendor/` exactly as SheetJS is today.

**Spec:** `docs/superpowers/specs/2026-09-15-tsn-talks-live-design.md` §3.4, §6, §8. Product brief: `PRODUCT.md`. The dataviz rules in the header comment of `charts.js` still bind.

**Who runs what:** one Claude-lane remote worker on the desktop, tasks in order, one commit each. **Nav does Part A (the SQL) inline and in parallel;** the worker only changes copy for it (Task 11). Nav reviews by diff, by rerunning both suites, and by opening the six tabs on real data.

---

## Part A — Nav, not the worker: `db/007_first_seen_baseline.sql`

The 2.37M column on 14 Sep is a data rule, not a drawing bug. `rollup_views`, `rollup_engagement` (both in `db/006`) and `post_deltas` (`db/004`) take a post's baseline as "its last snapshot before the period, else 0". A post published a year ago and first snapshotted on 14 Sep therefore gains its whole lifetime on 14 Sep, and every window that includes 14 Sep has one column that flattens everything else.

New rule, same three functions: **baseline = last snapshot before the period start; else, if the post was published before the period start, its first snapshot ever (so only growth since we started watching counts); else 0 (a post published inside the period did gain everything inside it).** Nav writes, applies and smokes this against `tsntalks` the same afternoon the worker is dispatched. The worker's Task 11 changes the three sentences of UI copy that describe the old rule and must not touch `db/`.

---

## The contracts that do not move

These are what `tests/analytics/test_charts.py`, `test_tabs.py` and `test_contrast.py` already check. Plot is being put *under* them, not instead of them.

- `chart(spec)` returns a `<figure class="a-figure">` holding, in order: `ul.a-legend` (only when ≥ 2 series), one or more `svg.a-chart`, `div.a-tip[hidden]`, `figcaption.vh`, `details.a-twin`. Empty input returns a figure with only `p.a-empty`.
- Every drawn value is a `g.a-point[tabindex="0"][role="img"][aria-label][data-value][data-tip]` containing a `.a-hit` shape and a `<title>`. `aria-label` reads `"<period> · <series name>: <full value>"`.
- `svg.a-chart` has a `viewBox` and **no** `width` or `height` attribute.
- Gridlines are `line.a-gridline`, hairline and solid. Lines are `path.a-line` at ≤ 2px. The one direct label is `text.a-peak`. Axis text is `text.a-axis`.
- `SERIES_COLOR` for the three platforms is fixed for the life of the project.
- The twin carries the same numbers as the marks, one row per point, a Total column when there are ≥ 2 series.

---

## File structure

```
tsntalks/
  site/
    analytics/
      index.html                      + d3 and Plot script tags (Task 1)
      artifacts/monthly-review.html   + the same two tags (Task 1)
    js/analytics/
      charts.js                       rewritten internals; same exports (Tasks 2–8)
      tabs/overview.js                views over time → multiples (Task 10); copy (Task 11)
      tabs/growth.js                  subscribers lost drawn below zero (Task 9)
      tabs/posts.js                   copy (Task 11)
      artifacts/monthly-review.js     copy (Task 11)
    css/analytics.css                 Plot text, area fill, multiples grid (Task 12)
  tests/analytics/
    conftest.py                       vendor cache + routes for d3 and Plot (Task 1)
    test_plot_runtime.py              the aria-label contract with Plot 0.6.17 (Task 1)   (NEW)
    test_charts.py                    two tests adjusted, seven added (Tasks 2–8)
    test_tabs.py                      overview + growth expectations (Tasks 9–10)
    shoot.py                          screenshots of the six tabs on fixtures (Task 13)   (NEW)
  docs/superpowers/plans/plan-4-shots/  six PNGs for Nav's review (Task 13)               (NEW)
```

Only `charts.js` knows Plot exists. Tabs and artifacts keep calling `chart()`.

---

### Task 1: Load d3 and Plot, and pin the aria-label contract

**Files:**
- Modify: `site/analytics/index.html` (the `<head>`, after the supabase-js tag)
- Modify: `site/analytics/artifacts/monthly-review.html` (same place — it is the one artifact page that imports `charts.js`)
- Modify: `tests/analytics/conftest.py`
- Create: `tests/analytics/test_plot_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
"""Plot is loaded from a CDN and its DOM is what charts.js decorates. This pins
the two facts charts.js depends on: the globals exist at the pinned versions,
and Plot labels its mark and axis groups with the aria-labels the decorator
selects on. If a version bump changes either, this fails before anything else."""


def test_plot_and_d3_are_present_at_the_pinned_versions(dashboard):
    got = dashboard.evaluate("() => ({ d3: window.d3?.version, plot: typeof window.Plot?.plot })")
    assert got == {"d3": "7.9.0", "plot": "function"}


def test_plot_labels_the_groups_the_decorator_relies_on(dashboard):
    labels = dashboard.evaluate("""() => {
      const svg = Plot.plot({
        width: 300, height: 120,
        x: { type: 'band', domain: ['a', 'b'] },
        y: { grid: true },
        marks: [
          Plot.line([{ x: 'a', y: 1 }, { x: 'b', y: 2 }], { x: 'x', y: 'y' }),
          Plot.barY([{ x: 'a', y: 1 }], { x: 'x', y: 'y' }),
        ],
      });
      return [...svg.querySelectorAll('g[aria-label]')].map((g) => g.getAttribute('aria-label'));
    }""")
    for needed in ("y-grid", "x-axis tick label", "y-axis tick label", "line", "bar"):
        assert needed in labels, f"Plot no longer labels {needed!r}: {labels}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/analytics/test_plot_runtime.py -q`
Expected: 2 failed — `window.d3` is undefined.

- [ ] **Step 3: Add the tags to both pages**

In `site/analytics/index.html`, directly after the supabase-js `<script>` and before the `app.js` module tag:

```html
<!-- d3 and Observable Plot, pinned exactly, with integrity hashes. Plot's UMD
     needs the d3 global first. d3 is on cdnjs; Plot is NOT (api.cdnjs.com has
     no @observablehq package, checked 2026-09-18), so it comes from jsDelivr as
     the ORIGINAL dist file, never jsDelivr's on-the-fly .min, so the hash holds. -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"
        integrity="sha384-CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i"
        crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script src="https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.17/dist/plot.umd.min.js"
        integrity="sha384-JUpn2GgRr0gxU0xOBd8D8P634jhRCwobtG8G2MMEkX1RnGJ7/FJNnuukpfT+H2w1"
        crossorigin="anonymous" referrerpolicy="no-referrer"></script>
```

Add the identical two tags to `site/analytics/artifacts/monthly-review.html` after its supabase-js tag.

- [ ] **Step 4: Teach the harness to serve both from the vendor cache**

In `tests/analytics/conftest.py`, next to `SHEETJS_URL`/`SHEETJS_SRI`, add:

```python
D3_URL = "https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"
D3_SRI = "sha384-CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i"
PLOT_URL = "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.17/dist/plot.umd.min.js"
PLOT_SRI = "sha384-JUpn2GgRr0gxU0xOBd8D8P634jhRCwobtG8G2MMEkX1RnGJ7/FJNnuukpfT+H2w1"
CDN_D3 = "**/d3.min.js"
CDN_PLOT = "**/plot.umd.min.js"
```

Generalise `sheetjs_bytes()` into `vendor_bytes(url, sri, filename)` with the same body (cache under `VENDOR / filename`, fetch once, verify the SRI, return `None` if it cannot be fetched), and keep `sheetjs_bytes = lambda: vendor_bytes(SHEETJS_URL, SHEETJS_SRI, "xlsx.full.min.js")` so nothing else changes. In `Stub.install()` add two routes beside `CDN_SHEETJS`:

```python
        page.route(CDN_D3, lambda route: self._vendor(route, D3_URL, D3_SRI, "d3.min.js"))
        page.route(CDN_PLOT, lambda route: self._vendor(route, PLOT_URL, PLOT_SRI, "plot.umd.min.js"))
```

with

```python
    def _vendor(self, route, url, sri, filename):
        data = vendor_bytes(url, sri, filename)
        if data is None:
            route.abort()   # the runtime test then fails with a clear message, not a hang
            return
        route.fulfill(status=200, body=data, headers={"content-type": "application/javascript"})
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/analytics/test_plot_runtime.py -q`
Expected: 2 passed. (First run downloads ~480 KB into `tests/analytics/stubs/vendor/`, which is gitignored.)

- [ ] **Step 6: Run the whole suite; nothing else may have moved**

Run: `python -m pytest tests/ -q`
Expected: all green, same count as before plus 2.

- [ ] **Step 7: Commit**

```bash
git add site/analytics/index.html site/analytics/artifacts/monthly-review.html tests/analytics/conftest.py tests/analytics/test_plot_runtime.py
git commit -m "feat(analytics): load d3 7.9.0 and Observable Plot 0.6.17, pinned, and pin the aria-label contract"
```

---

### Task 2: The Plot core inside charts.js — lines first

This task rewrites `lineSeries` on Plot and adds the shared machinery every later primitive uses. `barSeries`, `stackedBars` and `horizontalBars` keep their old bodies until their own tasks, so the suite stays green at every commit.

**Files:**
- Modify: `site/js/analytics/charts.js`
- Modify: `tests/analytics/test_charts.py` (one test adjusted: the gap test)

- [ ] **Step 1: Adjust the gap test to the new shape, and add the Plot-presence test**

Plot draws one `<path>` per series and breaks it at a null with a second `M` subpath. The old test counted paths; the contract is subpaths. Replace `test_a_gap_in_the_data_breaks_the_line_rather_than_joining_across_it` with:

```python
def test_a_gap_in_the_data_breaks_the_line_rather_than_joining_across_it(c):
    """A straight segment across a week nobody measured is a claim we cannot
    support. Two subpaths, not one — however many <path> elements carry them."""
    got = js(c, """
      const gapped = [
        { label: 'a', values: { youtube: 100 } },
        { label: 'b', values: { youtube: 200 } },
        { label: 'c', values: { youtube: null } },
        { label: 'd', values: { youtube: 300 } },
        { label: 'e', values: { youtube: 400 } },
      ];
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views', points: gapped, series: [{ id: 'youtube' }] }));
      return [...mount.querySelectorAll('path.a-line')].map((p) => p.getAttribute('d'));
    """)
    assert sum(d.count("M") for d in got) == 2
    assert "c" not in "".join(got)  # nothing is drawn at the gap


def test_lines_are_drawn_by_plot_and_wear_the_house_classes(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views', points: POINTS, series: PLATFORMS }));
      const svg = mount.querySelector('svg.a-chart');
      return {
        plotStyle: svg.querySelector('style') === null,
        grid: svg.querySelectorAll('g[aria-label="y-grid"] line.a-gridline').length,
        axis: svg.querySelectorAll('text.a-axis').length > 0,
        lines: svg.querySelectorAll('g[aria-label="line"] path.a-line').length,
        fixedWidth: svg.hasAttribute('width') || svg.hasAttribute('height'),
        viewBox: svg.getAttribute('viewBox'),
      };
    """)
    assert got["plotStyle"], "Plot's injected <style> must be removed; analytics.css owns type"
    assert got["grid"] >= 3 and got["axis"]
    assert got["lines"] == 3
    assert not got["fixedWidth"] and got["viewBox"] == "0 0 720 260"
```

- [ ] **Step 2: Run to verify the new test fails and the old ones still pass**

Run: `python -m pytest tests/analytics/test_charts.py -q`
Expected: `test_lines_are_drawn_by_plot_and_wear_the_house_classes` FAILS (no `g[aria-label="line"]`); the gap test passes on the old code too (two paths, one M each) — that is fine, it is guarding the transition.

- [ ] **Step 3: Write the core and the new `lineSeries`**

In `charts.js`, keep the header comment, the imports, `W`, `H`, `PAD`, `SVG`, `SERIES_COLOR`, `seriesColor`, `seriesName`, `el`, `html`, `thinning`, `hotspot`, `assertName`, and everything from `legend` down. **Delete** `ticks`, `frame`, `newChart`, `labelThePeak` and the old `lineSeries`. Add, after `assertName`:

```js
/* --- the Plot core --------------------------------------------------------- */

function plotLib() {
  const P = globalThis.Plot;
  if (!P || !globalThis.d3) {
    throw new Error('charts: Observable Plot and d3 must be loaded before charts.js (see analytics/index.html)');
  }
  return P;
}

/**
 * A series colour as a hex string Plot can use as a constant.
 *
 * SERIES_COLOR holds CSS custom properties so the tokens stay in one file.
 * Plot cannot take `var(--yt)` as a colour (it would build a categorical scale
 * over the strings and repaint the platforms), so the token is resolved from
 * the document once per draw. The tests run on the real stylesheet, which is
 * what keeps test_contrast.py honest about these values.
 */
function resolvedColor(id) {
  const token = seriesColor(id);
  const m = /^var\((--[\w-]+)\)$/.exec(token);
  if (!m) return token;
  const v = getComputedStyle(document.documentElement).getPropertyValue(m[1]).trim();
  return v || '#E8621A';
}

/** Long rows for Plot: one per (point, series) that has a value. */
function longRows(points, series) {
  const rows = [];
  points.forEach((p, i) => {
    for (const s of series) {
      const v = p.values?.[s.id];
      rows.push({ i, label: p.label, series: s.id, value: v == null ? null : Number(v) });
    }
  });
  return rows;
}

/** Ticks for a count axis: never fractional when the data is integers. */
function yTickCount(values) {
  const finite = values.filter((v) => v != null && Number.isFinite(v));
  const max = Math.max(0, ...finite.map(Math.abs));
  const integers = finite.every(Number.isInteger);
  return integers && max <= 5 ? Math.max(1, Math.ceil(max)) : 5;
}

/**
 * The x axis is a band of period labels, always. Plot draws exactly the ticks
 * it is handed, so thinning is explicit here, and the last label is no longer
 * forced — that is what put "15 Sept" on top of "16 Sept". The exact period of
 * every point is in its tooltip and in the twin.
 */
function xBand(points) {
  const domain = points.map((p) => p.label);
  const every = thinning(points.length);
  return { type: 'band', domain, ticks: domain.filter((_, i) => i % every === 0),
           label: null, padding: 0.32, tickSize: 0 };
}

const BASE = () => ({
  width: W, height: H,
  marginTop: PAD.top, marginRight: PAD.right, marginBottom: PAD.bottom, marginLeft: PAD.left,
  style: { background: 'transparent', overflow: 'visible' },
});

/**
 * Plot's SVG, made ours.
 *
 *  - Plot injects a <style> that sets system-ui at 10px on the figure and a
 *    max-width; analytics.css owns type here, so it goes.
 *  - Plot sets a fixed width and height; the viewBox alone is kept so the
 *    browser scales the drawing (test: charts scale by viewBox).
 *  - Groups keep Plot's aria-labels; the elements inside get the house classes
 *    the CSS and the tests select on.
 */
function decorate(svg, name) {
  svg.querySelector('style')?.remove();
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  svg.removeAttribute('font-family');
  svg.removeAttribute('font-size');
  svg.setAttribute('class', 'a-chart');
  svg.setAttribute('role', 'group');
  svg.setAttribute('aria-label', name);
  for (const line of svg.querySelectorAll('g[aria-label="y-grid"] line')) {
    line.setAttribute('class', 'a-gridline');
    line.removeAttribute('stroke');
    line.removeAttribute('stroke-opacity');
  }
  for (const g of svg.querySelectorAll('g[aria-label$="tick label"]')) {
    g.removeAttribute('fill');
    for (const t of g.querySelectorAll('text')) t.setAttribute('class', 'a-axis');
  }
  for (const p of svg.querySelectorAll('g[aria-label="line"] path')) p.setAttribute('class', 'a-line');
  for (const r of svg.querySelectorAll('g[aria-label="bar"] rect, g[aria-label="rect"] rect')) {
    r.setAttribute('class', 'a-bar');
  }
  return svg;
}

/** Plot's scales, as functions of a label and a value. */
function scalesOf(svg) {
  const x = svg.scale('x');
  const y = svg.scale('y');
  const bw = x.bandwidth ?? 0;
  return {
    xMid: (label) => x.apply(label) + bw / 2,
    xLeft: (label) => x.apply(label),
    bandwidth: bw,
    y: (v) => y.apply(v),
  };
}

/** The single direct label: the highest value drawn. */
function peakLabel(svg, rows, sc, format) {
  let best = null;
  for (const r of rows) if (r.value != null && (!best || r.value > best.value)) best = r;
  if (!best) return;
  svg.appendChild(el('text', {
    x: sc.xMid(best.label), y: sc.y(best.value) - 8, class: 'a-peak', 'text-anchor': 'middle',
  }, format(best.value)));
}

/* --- the primitives -------------------------------------------------------- */

/**
 * Lines over time. Stocks — followers, cumulative anything.
 *
 * One Plot line mark per series with a constant stroke, so no colour scale is
 * ever built: the platform colours are tokens, not a palette Plot may reorder.
 * A null breaks the line (Plot's default) rather than joining across it, and a
 * faint area sits under each line so the eye reads the level, not just the edge.
 */
export function lineSeries({ name, points, series, format = compact }) {
  assertName(name);
  const Plot = plotLib();
  const rows = longRows(points, series);
  const values = rows.map((r) => r.value);
  const marks = [];
  for (const s of series) {
    const mine = rows.filter((r) => r.series === s.id);
    const colour = resolvedColor(s.id);
    marks.push(Plot.areaY(mine, { x: 'label', y: 'value', fill: colour, fillOpacity: 0.08 }));
    marks.push(Plot.line(mine, { x: 'label', y: 'value', stroke: colour, strokeWidth: 1.5,
                                 strokeLinejoin: 'round', strokeLinecap: 'round' }));
  }
  const min = Math.min(0, ...values.filter((v) => v != null));
  const max = Math.max(1, ...values.filter((v) => v != null));
  const svg = Plot.plot({
    ...BASE(),
    x: xBand(points),
    y: { grid: true, label: null, domain: [min, max], nice: true, ticks: yTickCount(values),
         tickFormat: (v) => format(v), tickSize: 0 },
    marks,
  });
  decorate(svg, name);
  const sc = scalesOf(svg);
  for (const r of rows) {
    if (r.value == null) continue;
    svg.appendChild(hotspot(
      el('circle', { cx: sc.xMid(r.label), cy: sc.y(r.value), r: 8, class: 'a-hit' }),
      { label: `${r.label} · ${seriesName(r.series)}: ${full(r.value)}`, value: r.value },
    ));
    svg.appendChild(el('circle', {
      cx: sc.xMid(r.label), cy: sc.y(r.value), r: 2, fill: resolvedColor(r.series), class: 'a-dotmark',
    }));
  }
  peakLabel(svg, rows, sc, format);
  return svg;
}
```

Note for the decorator: Plot names a line mark's group `line` and a barY/barX mark's group `bar`; Task 1's runtime test is what guarantees that.

- [ ] **Step 4: Run the chart tests**

Run: `python -m pytest tests/analytics/test_charts.py -q`
Expected: all green, including the new one and the adjusted gap test. If `test_gridlines_are_hairline_and_solid` fails on `stroke-dasharray`, Plot has left a `stroke-dasharray` attribute on the grid lines — remove it in `decorate` next to `stroke-opacity`.

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest tests/ -q`
Expected: green. The Growth and Overview tabs draw lines through this function now.

- [ ] **Step 6: Commit**

```bash
git add site/js/analytics/charts.js tests/analytics/test_charts.py
git commit -m "feat(charts): lines drawn by Observable Plot behind the same chart() contract"
```

---

### Task 3: Bars on Plot — grouped-by-sign, not side-by-side

`barSeries` has two callers: followers gained/lost and YouTube subscribers gained/lost, both "one series up, one down". Side-by-side grouped bars are the one thing Plot's band scale does not do without faceting, and faceting breaks the thinned x axis. So `barSeries` draws every series at the same x, full band width; callers hand the down series as negatives (gained/lost already does). The twin keeps positive counts.

**Files:**
- Modify: `site/js/analytics/charts.js`
- Modify: `tests/analytics/test_charts.py`

- [ ] **Step 1: Write the failing test**

```python
def test_bars_diverge_from_the_zero_line_and_wear_their_series_colour(c):
    got = js(c, """
      const pts = [
        { label: 'a', values: { gained: 40, lost: -3 } },
        { label: 'b', values: { gained: 12, lost: -9 } },
      ];
      mount.appendChild(charts.chart({ kind: 'bar', name: 'Gained and lost', points: pts,
        series: [{ id: 'gained', name: 'Gained' }, { id: 'lost', name: 'Lost' }] }));
      const svg = mount.querySelector('svg.a-chart');
      const zero = svg.querySelector('line.a-zeroline');
      /* Plot sets a constant fill on the mark's <g>, not on each rect: read the computed style. */
      const bars = [...svg.querySelectorAll('rect.a-bar')].map((r) => ({
        y: Number(r.getAttribute('y')), h: Number(r.getAttribute('height')), fill: getComputedStyle(r).fill }));
      const up = [...svg.querySelectorAll('.a-point')].map((g) => Number(g.dataset.value));
      return { zero: zero && Number(zero.getAttribute('y1')), bars, up };
    """)
    assert got["zero"] is not None
    above = [b for b in got["bars"] if b["y"] + b["h"] <= got["zero"] + 0.5]
    below = [b for b in got["bars"] if b["y"] >= got["zero"] - 0.5]
    assert len(above) == 2 and len(below) == 2
    assert len({b["fill"] for b in got["bars"]}) == 2, "gained and lost must not share a colour"
    assert sorted(got["up"]) == [-9, -3, 12, 40]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/analytics/test_charts.py -q -k diverge`
Expected: FAIL — the old `barSeries` draws grouped bars and no `.a-zeroline` per Plot (the old frame drew one; the assertion on fills fails because `gained`/`lost` resolve to the up/down tokens already — read the failure, it should be the geometry or the zero line, not the colours).

- [ ] **Step 3: Replace `barSeries`**

```js
/**
 * Columns per period. One series up, the other handed in as negatives, drawn
 * at the same x and diverging from a brighter zero line. Two positive series
 * that must be compared side by side are a `multiples` chart, not this.
 */
export function barSeries({ name, points, series, format = compact }) {
  assertName(name);
  const Plot = plotLib();
  const rows = longRows(points, series).filter((r) => r.value != null);
  const values = rows.map((r) => r.value);
  const min = Math.min(0, ...values);
  const max = Math.max(1, ...values);
  const marks = series.map((s) => Plot.barY(rows.filter((r) => r.series === s.id), {
    x: 'label', y: 'value', fill: resolvedColor(s.id), insetLeft: 1, insetRight: 1,
  }));
  const svg = Plot.plot({
    ...BASE(),
    x: xBand(points),
    y: { grid: true, label: null, domain: [min, max], nice: true, ticks: yTickCount(values),
         tickFormat: (v) => format(v), tickSize: 0 },
    marks,
  });
  decorate(svg, name);
  const sc = scalesOf(svg);
  if (min < 0) {
    svg.appendChild(el('line', {
      x1: PAD.left, x2: W - PAD.right, y1: sc.y(0), y2: sc.y(0), class: 'a-zeroline',
    }));
  }
  const zero = sc.y(0);
  for (const r of rows) {
    const top = Math.min(sc.y(r.value), zero);
    svg.appendChild(hotspot(
      el('rect', { x: sc.xLeft(r.label), y: top, width: sc.bandwidth,
                   height: Math.max(Math.abs(sc.y(r.value) - zero), 1), class: 'a-hit' }),
      { label: `${r.label} · ${seriesName(r.series)}: ${full(Math.abs(r.value))}`, value: r.value },
    ));
  }
  return svg;
}
```

- [ ] **Step 4: Run the chart tests, then the suite**

Run: `python -m pytest tests/analytics/test_charts.py -q` then `python -m pytest tests/ -q`
Expected: green. `test_focus_shows_the_tooltip_and_blur_hides_it` uses `kind: 'bar'` with one positive series and still passes.

- [ ] **Step 5: Commit**

```bash
git add site/js/analytics/charts.js tests/analytics/test_charts.py
git commit -m "feat(charts): diverging bars on Plot, one colour per direction, a brighter zero line"
```

---

### Task 4: Stacked columns on Plot

**Files:**
- Modify: `site/js/analytics/charts.js`

- [ ] **Step 1: The tests already exist** — `test_a_chart_and_its_twin_carry_identical_numbers[stacked]`, `test_the_twin_totals_match_the_stacked_columns`, `test_only_the_peak_gets_a_direct_label`. Run them to see them pass on the old code, then they are the guard:

Run: `python -m pytest tests/analytics/test_charts.py -q -k "stacked or peak"`
Expected: green (old code).

- [ ] **Step 2: Replace `stackedBars`**

```js
/** Stacked columns. Parts of one whole, per period. */
export function stackedBars({ name, points, series, format = compact }) {
  assertName(name);
  const Plot = plotLib();
  /* Stack in JS so the overlay knows every segment's ends; Plot draws y1..y2. */
  const segs = [];
  const totals = points.map((p) => {
    let base = 0;
    for (const s of series) {
      const v = p.values?.[s.id] ?? 0;
      if (!v) continue;
      segs.push({ label: p.label, series: s.id, value: v, y0: base, y1: base + v });
      base += v;
    }
    return base;
  });
  const max = Math.max(1, ...totals);
  const marks = series.map((s) => Plot.barY(segs.filter((g) => g.series === s.id), {
    x: 'label', y1: 'y0', y2: 'y1', fill: resolvedColor(s.id), insetLeft: 1, insetRight: 1, insetTop: 1,
  }));
  const svg = Plot.plot({
    ...BASE(),
    x: xBand(points),
    y: { grid: true, label: null, domain: [0, max], nice: true, ticks: yTickCount(totals),
         tickFormat: (v) => format(v), tickSize: 0 },
    marks,
  });
  decorate(svg, name);
  const sc = scalesOf(svg);
  for (const g of segs) {
    svg.appendChild(hotspot(
      el('rect', { x: sc.xLeft(g.label), y: sc.y(g.y1), width: sc.bandwidth,
                   height: Math.max(sc.y(g.y0) - sc.y(g.y1), 1), class: 'a-hit' }),
      { label: `${g.label} · ${seriesName(g.series)}: ${full(g.value)}`, value: g.value },
    ));
  }
  const peak = totals.indexOf(Math.max(...totals));
  if (totals[peak] > 0) {
    svg.appendChild(el('text', {
      x: sc.xMid(points[peak].label), y: sc.y(totals[peak]) - 6, class: 'a-peak', 'text-anchor': 'middle',
    }, format(totals[peak])));
  }
  return svg;
}
```

- [ ] **Step 3: Run the chart tests and the suite**

Run: `python -m pytest tests/analytics/test_charts.py -q` then `python -m pytest tests/ -q`
Expected: green. `insetTop: 1` is the 2px surface gap between segments from the dataviz rules, at this scale.

- [ ] **Step 4: Commit**

```bash
git add site/js/analytics/charts.js
git commit -m "feat(charts): stacked columns on Plot with a 1px gap between segments"
```

---

### Task 5: Horizontal bars on Plot

**Files:**
- Modify: `site/js/analytics/charts.js`

- [ ] **Step 1: The guard already exists** — `test_horizontal_bars_print_the_number_beside_the_bar`. Run it: green on old code.

- [ ] **Step 2: Replace `horizontalBars`**

```js
/** Horizontal bars. Categories with names too long to stand under a column. */
export function horizontalBars({ name, points, format = compact, colour = 'var(--saffron)' }) {
  assertName(name);
  const Plot = plotLib();
  const rowH = 22;
  const height = Math.max(points.length * rowH + 20, 60);
  const rows = points.map((p) => ({ label: p.label, value: Math.max(p.value ?? 0, 0) }));
  const max = Math.max(1, ...rows.map((r) => r.value));
  const fill = /^var\(/.test(colour) ? resolvedColor('value') : colour;
  const svg = Plot.plot({
    width: W, height, marginTop: 6, marginRight: 90, marginBottom: 6, marginLeft: 150,
    style: { background: 'transparent', overflow: 'visible' },
    x: { axis: null, domain: [0, max] },
    y: { type: 'band', domain: rows.map((r) => r.label), label: null, padding: 0.3, tickSize: 0 },
    marks: [Plot.barX(rows, { x: 'value', y: 'label', fill, insetTop: 1, insetBottom: 1 })],
  });
  decorate(svg, name);
  svg.setAttribute('viewBox', `0 0 ${W} ${height}`);
  const x = svg.scale('x');
  const y = svg.scale('y');
  for (const r of rows) {
    const top = y.apply(r.label);
    const w = x.apply(r.value) - x.apply(0);
    svg.appendChild(hotspot(
      el('rect', { x: x.apply(0), y: top, width: Math.max(w, 2), height: y.bandwidth, class: 'a-hit' }),
      { label: `${r.label}: ${full(r.value)}`, value: r.value },
    ));
    /* The number in text, next to the bar. PRODUCT.md: numbers are never only a bar length. */
    svg.appendChild(el('text', {
      x: x.apply(r.value) + 8, y: top + y.bandwidth / 2 + 4, class: 'a-barval',
    }, format(r.value)));
  }
  return svg;
}
```

- [ ] **Step 3: Run the chart tests and the suite** — green.

- [ ] **Step 4: Commit**

```bash
git add site/js/analytics/charts.js
git commit -m "feat(charts): horizontal bars on Plot, number still printed beside the bar"
```

---

### Task 6: Integer ticks for counts, and the all-zero empty state

**Files:**
- Modify: `site/js/analytics/charts.js` (`chart()` only)
- Modify: `tests/analytics/test_charts.py`

- [ ] **Step 1: Write the two failing tests**

```python
def test_a_count_axis_never_shows_a_fraction(c):
    """Max 1 used to produce 0 / 0.25 / 0.5 / 0.75 / 1 on a chart of people."""
    got = js(c, """
      const pts = [{ label: 'a', values: { gained: 1 } }, { label: 'b', values: { gained: 0 } }];
      mount.appendChild(charts.chart({ kind: 'bar', name: 'Gained', points: pts, series: [{ id: 'gained' }] }));
      return [...mount.querySelectorAll('g[aria-label="y-axis tick label"] text.a-axis')].map((t) => t.textContent);
    """)
    assert got == ["0", "1"]


def test_an_all_zero_window_says_so_instead_of_drawing_an_axis(c):
    got = js(c, """
      const pts = [{ label: 'a', values: { gained: 0, lost: 0 } }, { label: 'b', values: { gained: 0, lost: 0 } }];
      const fig = charts.chart({ kind: 'bar', name: 'Gained and lost', points: pts,
        series: [{ id: 'gained' }, { id: 'lost' }], zero: 'Nobody arrived or left in this window.' });
      mount.appendChild(fig);
      return { svg: fig.querySelectorAll('svg.a-chart').length, text: fig.querySelector('.a-empty')?.textContent,
               twin: fig.querySelectorAll('.a-twin').length };
    """)
    assert got["svg"] == 0
    assert got["text"] == "Nobody arrived or left in this window."
    assert got["twin"] == 1, "the numbers are still there for anyone who wants to check"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/analytics/test_charts.py -q -k "fraction or all_zero"`
Expected: the fraction test may already pass (Task 2's `yTickCount`); the all-zero test FAILS with `svg == 1`.

- [ ] **Step 3: Add the all-zero branch to `chart()`**

In `chart()`, after the `!points.length` early return and before `const draw = DRAW[kind]`:

```js
  /* Every value zero or absent: an axis over nothing is a chart that says
     "0.25 people". Say what happened in words and keep the twin. */
  const allZero = kind === 'hbar'
    ? points.every((p) => !(p.value))
    : points.every((p) => series.every((s) => !(p.values?.[s.id])));
  if (allZero) {
    figure.appendChild(html('p', 'a-empty', spec.zero ?? `Every value in ${name} is zero for this window.`));
    figure.appendChild(tableTwin(
      spec.rows ?? defaultTwinRows(points, series, kind),
      spec.columns ?? defaultTwinColumns(series, kind, format),
      { summary: spec.summary ?? 'Show the numbers' },
    ));
    return figure;
  }
```

- [ ] **Step 4: Run the tests and the suite** — green. Then run the growth tab test to confirm the fixture's gained/lost panel still draws (its fixture has non-zero values) — if it does not, the fixture is all zero and the panel now shows the sentence; adjust `test_tabs.py`'s expectation for that panel to the sentence, not the svg.

- [ ] **Step 5: Commit**

```bash
git add site/js/analytics/charts.js tests/analytics/test_charts.py
git commit -m "feat(charts): integer ticks on counts; an all-zero window says so and keeps its twin"
```

---

### Task 7: Series colours by direction, whatever the id

**Files:**
- Modify: `site/js/analytics/charts.js` (`seriesColor`)
- Modify: `tests/analytics/test_charts.py`

- [ ] **Step 1: Write the failing test**

```python
def test_gained_and_lost_take_their_direction_colours_whatever_the_metric_is_called(c):
    got = js(c, """
      return ['yt_subs_gained', 'yt_subs_lost', 'ig_follows', 'ig_unfollows',
              'tt_followers_gained', 'tt_followers_lost', 'gained', 'lost', 'youtube', 'previous']
        .map((id) => charts.seriesColor(id));
    """)
    up, down = "var(--up)", "var(--down)"
    assert got == [up, down, up, down, up, down, up, down, "var(--yt)", "var(--muted)"]
```

- [ ] **Step 2: Run to verify it fails** — `yt_subs_gained` comes back as `var(--saffron)`.

- [ ] **Step 3: Replace `seriesColor`**

```js
/**
 * A series colour. The platforms are fixed. Anything that reads as arriving
 * (gained, follows) is the up colour and anything leaving (lost, unfollows) is
 * the down colour, whatever metric_daily key it arrived under — the
 * subscribers panel shipped with both bars saffron because its ids were
 * `yt_subs_gained` and `yt_subs_lost`.
 */
export const seriesColor = (id) => {
  if (SERIES_COLOR[id]) return SERIES_COLOR[id];
  if (/(gained|follows)$/.test(id) && !/unfollows$/.test(id)) return SERIES_COLOR.gained;
  if (/(lost|unfollows)$/.test(id)) return SERIES_COLOR.lost;
  return 'var(--saffron)';
};
```

- [ ] **Step 4: Run the test and the suite** — green.

- [ ] **Step 5: Commit**

```bash
git add site/js/analytics/charts.js tests/analytics/test_charts.py
git commit -m "fix(charts): gained/lost series take the direction colours whatever their metric id"
```

---

### Task 8: `kind: 'multiples'` — one small chart per series, own y-scale, one twin

**Files:**
- Modify: `site/js/analytics/charts.js`
- Modify: `tests/analytics/test_charts.py`
- Modify: `site/css/analytics.css` (the grid; the rest of the CSS is Task 12)

- [ ] **Step 1: Write the failing test**

```python
def test_multiples_give_each_series_its_own_scale_and_share_one_twin(c):
    got = js(c, """
      const pts = [
        { label: '9 Sep',  values: { youtube: 120, tiktok: 90000 } },
        { label: '10 Sep', values: { youtube: 150, tiktok: 70000 } },
        { label: '11 Sep', values: { youtube: 90,  tiktok: 110000 } },
      ];
      const fig = charts.chart({ kind: 'multiples', name: 'Views by platform', points: pts,
        series: [{ id: 'youtube' }, { id: 'tiktok' }] });
      mount.appendChild(fig);
      const svgs = [...fig.querySelectorAll('svg.a-chart')];
      const tops = svgs.map((s) => [...s.querySelectorAll('g[aria-label="y-axis tick label"] text')].at(-1)?.textContent);
      return {
        svgs: svgs.length, tops,
        titles: [...fig.querySelectorAll('.a-multiple h3')].map((h) => h.textContent),
        legend: fig.querySelectorAll('.a-legend').length,
        twins: fig.querySelectorAll('.a-twin').length,
        headers: [...fig.querySelectorAll('.a-twin thead th')].map((th) => th.textContent),
        points: fig.querySelectorAll('.a-point').length,
      };
    """)
    assert got["svgs"] == 2 and got["tops"][0] != got["tops"][1]
    assert got["titles"] == ["YouTube", "TikTok"]
    assert got["legend"] == 0, "the titles name the series; a legend would say it twice"
    assert got["twins"] == 1 and got["headers"] == ["Period", "YouTube", "TikTok", "Total"]
    assert got["points"] == 6
```

- [ ] **Step 2: Run to verify it fails** — `unknown kind "multiples"`.

- [ ] **Step 3: Add the primitive and register it**

```js
/**
 * Small multiples. One chart per series, each on its own y-scale, sharing the
 * x band and one twin. For series of different magnitude — TikTok at 1.5M over
 * YouTube at 244K — where a stack shows one platform and two slivers.
 */
export function multiples({ name, points, series, format = compact }) {
  assertName(name);
  const wrap = html('div', 'a-multiples');
  for (const s of series) {
    const cell = html('div', 'a-multiple');
    const h = html('h3', null, s.name ?? seriesName(s.id));
    h.style.color = seriesColor(s.id);
    cell.appendChild(h);
    cell.appendChild(lineSeries({
      name: `${name} — ${s.name ?? seriesName(s.id)}`, points, series: [s], format, height: 150,
    }));
    wrap.appendChild(cell);
  }
  return wrap;
}
```

Two edits to Task 2's code make `height` real: `const BASE = (height = H) => ({ width: W, height, marginTop: ..., ... })` and `export function lineSeries({ name, points, series, format = compact, height = H })` spreading `...BASE(height)` in its `Plot.plot` call. Then add `multiples` to `DRAW`. In `chart()`, the draw result may now be a `div` holding several svgs: replace `figure.appendChild(svg)` and `wireTooltip(figure, svg, tip)` with

```js
  const drawn = draw({ ...spec, format });
  const key = drawn.matches?.('svg') ? legend(series) : null;   // multiples carry their own titles
  if (key) figure.appendChild(key);
  figure.appendChild(drawn);
  const tip = html('div', 'a-tip');
  tip.hidden = true;
  figure.appendChild(tip);
  for (const svg of drawn.matches?.('svg') ? [drawn] : drawn.querySelectorAll('svg.a-chart')) {
    wireTooltip(figure, svg, tip);
  }
```

and in `analytics.css` add:

```css
/* Small multiples: one chart per series, own y-scale, shared x band. */
.a-multiples { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px 18px; }
.a-multiple h3 { margin: 0 0 4px; font-size: 11.5px; font-weight: 600; letter-spacing: .02em; }
```

- [ ] **Step 4: Run the test and the suite** — green.

- [ ] **Step 5: Commit**

```bash
git add site/js/analytics/charts.js site/css/analytics.css tests/analytics/test_charts.py
git commit -m "feat(charts): small multiples — one chart per series on its own scale, one twin"
```

---

### Task 9: Growth tab — subscribers lost drawn below the line

**Files:**
- Modify: `site/js/analytics/tabs/growth.js` (`subscribersPanel`)
- Modify: `tests/analytics/test_tabs.py`

- [ ] **Step 1: Write the failing test** (in the Growth section of `test_tabs.py`, using the existing `gr` fixture and `panel_named` helper)

```python
def test_subscribers_lost_are_drawn_below_the_zero_line_and_listed_as_positive_counts(gr):
    section = panel_named(gr, "YouTube subscribers")
    got = section.evaluate("""(el) => {
      const svg = el.querySelector('svg.a-chart');
      const zero = Number(svg.querySelector('line.a-zeroline')?.getAttribute('y1'));
      const marks = [...svg.querySelectorAll('.a-point')].map((g) => Number(g.dataset.value));
      const lost = [...el.querySelectorAll('details.a-twin tbody tr')]
        .map((tr) => Number(tr.querySelectorAll('td.num')[1]?.dataset.value ?? 0));
      const swatches = [...el.querySelectorAll('.a-legend i')].map((i) => getComputedStyle(i).backgroundColor);
      return { zero, negatives: marks.filter((v) => v < 0).length, lost, swatches };
    }""")
    assert got["zero"] > 0
    assert got["negatives"] == sum(1 for v in got["lost"] if v > 0)
    assert all(v >= 0 for v in got["lost"])
    assert len(set(got["swatches"])) == 2
```

- [ ] **Step 2: Run to verify it fails** — no `.a-zeroline` (lost is drawn positive today).

- [ ] **Step 3: Change `subscribersPanel`** to hand `metricPanel` a `twin` and negate lost. Replace the function:

```js
function subscribersPanel(result, w) {
  return metricPanel(result, w, {
    title: 'YouTube subscribers',
    name: 'YouTube subscribers gained and lost',
    metrics: ['yt_subs_gained', 'yt_subs_lost'],
    seriesNames: { yt_subs_gained: 'Gained', yt_subs_lost: 'Lost' },
    format: full,
    /* Lost is drawn below the line, as on the followers panel; the twin keeps the count positive. */
    negate: ['yt_subs_lost'],
    twin: {
      columns: [
        { key: 'label', name: 'Period' },
        { key: 'gained', name: 'Gained', num: true, format: full },
        { key: 'lost', name: 'Lost', num: true, format: full },
        { key: 'net', name: 'Net', num: true, format: full },
      ],
      rows: (rows) => rows.map((r) => ({
        label: periodLabel(r.period, w.granularity),
        gained: r.values.yt_subs_gained ?? null,
        lost: r.values.yt_subs_lost ?? null,
        net: (r.values.yt_subs_gained ?? 0) - (r.values.yt_subs_lost ?? 0),
      })),
    },
  });
}
```

and in `metricPanel`, accept `negate = []` in its options and build points as

```js
        values: Object.fromEntries(metrics.map((m) => {
          const v = r.values[m] ?? null;
          return [m, v != null && negate.includes(m) ? -v : v];
        })),
```

- [ ] **Step 4: Run the growth tests and the suite** — green.

- [ ] **Step 5: Commit**

```bash
git add site/js/analytics/tabs/growth.js tests/analytics/test_tabs.py
git commit -m "feat(growth): subscribers lost drawn below the line, listed positive, in the down colour"
```

---

### Task 10: Overview — views over time as three small charts

**Files:**
- Modify: `site/js/analytics/tabs/overview.js` (`viewsPanel`)
- Modify: `tests/analytics/test_tabs.py` (`test_views_are_drawn_as_stacked_columns_and_followers_as_lines`)

- [ ] **Step 1: Rewrite the test first**

Replace `test_views_are_drawn_as_stacked_columns_and_followers_as_lines` with:

```python
def test_views_are_one_small_chart_per_platform_and_followers_one_line_chart(ov):
    """TikTok at 1.5M stacked over YouTube at 244K shows one platform and two
    slivers. Each platform gets its own scale; followers stay one line chart
    because a bar chart of a stock invites the reader to add the bars up."""
    got = ov.evaluate("""() => {
      const out = {};
      for (const p of document.querySelectorAll('#view .a-panel')) {
        const title = p.querySelector('h2')?.textContent ?? '';
        const svgs = [...p.querySelectorAll('svg.a-chart')];
        if (svgs.length) out[title] = { charts: svgs.length,
          lines: svgs.reduce((n, s) => n + s.querySelectorAll('path.a-line').length, 0),
          bars: svgs.reduce((n, s) => n + s.querySelectorAll('rect.a-bar').length, 0),
          twins: p.querySelectorAll('details.a-twin').length };
      }
      return out;
    }""")
    assert got["Views over time"] == {"charts": 3, "lines": 3, "bars": 0, "twins": 1}
    assert got["Follower growth"]["charts"] == 1 and got["Follower growth"]["lines"] == 3
```

- [ ] **Step 2: Run to verify it fails** — `charts == 1, bars > 0`.

- [ ] **Step 3: Change `viewsPanel`**: `kind: 'stacked'` → `kind: 'multiples'`, and drop `width: 'half'` from its `resultPanel` spec so the three charts get the full row (leave `followersPanel` at `half`; check the grid still reads — if the followers panel now sits alone on a half row, remove its `half` too).

- [ ] **Step 4: Run the overview tests and the suite** — green. The TikTok-only test (`svg.a-chart` count 2) still holds: one multiple plus one line chart.

- [ ] **Step 5: Commit**

```bash
git add site/js/analytics/tabs/overview.js tests/analytics/test_tabs.py
git commit -m "feat(overview): views over time as one small chart per platform on its own scale"
```

---

### Task 11: Copy for the first-seen baseline (Part A lands the SQL)

Three sentences describe the old rule. Nav's `db/007` changes the rule to: a post we started watching inside the window counts only the views it gained after its first snapshot; a post published inside the window counts everything. Do not touch `db/`.

**Files:**
- Modify: `site/js/analytics/tabs/overview.js:176-177`
- Modify: `site/js/analytics/tabs/posts.js` (the note near the "Gained here" column, if any prose describes the rule; the column header stays)
- Modify: `site/js/analytics/artifacts/monthly-review.js:160`
- Modify: `tests/analytics/test_tabs.py` (add the assertion below)

- [ ] **Step 1: Write the failing test**

```python
def test_the_gained_note_describes_the_first_seen_baseline(ov):
    note = ov.locator("#view .a-panel", has_text="Top posts in this window").locator("p.a-note").last.text_content()
    assert "first saw it" in note
    assert "whole total" not in note
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Change the three sentences**

overview.js:
```js
      '"Gained here" is the change inside this window; "views total" is lifetime. '
      + 'A post we started watching inside the window counts only the views it gained after we first saw it; '
      + 'a post published inside the window counts all of them.'));
```

monthly-review.js:
```js
    + 'A post published this month counts its whole total as gained; a post we only started watching this month counts what it gained after we first saw it.'));
```

posts.js carries only the "Gained here" column header and no sentence about the rule (checked 2026-09-18); leave it unchanged and drop it from the commit.

- [ ] **Step 4: Run the suite** — green.

- [ ] **Step 5: Commit**

```bash
git add site/js/analytics/tabs/overview.js site/js/analytics/tabs/posts.js site/js/analytics/artifacts/monthly-review.js tests/analytics/test_tabs.py
git commit -m "docs(analytics): the gained notes describe the first-seen baseline (db/007)"
```

---

### Task 12: Type and marks in analytics.css

Plot's own stylesheet is gone (Task 2), so the chart text must be styled by us, and a few rules are new.

**Files:**
- Modify: `site/css/analytics.css` (the `/* --- charts --- */` block)

- [ ] **Step 1: Add, after `svg.a-chart { ... }`**

```css
/* Plot's injected stylesheet is removed by charts.js; type is set here so every
   chart wears Hanken Grotesk and tabular figures like the rest of the page. */
svg.a-chart text { font-family: var(--text); font-variant-numeric: tabular-nums lining-nums; }
svg.a-chart g[aria-label$="tick label"] text { fill: var(--muted); font-size: 11px; }
svg.a-chart g[aria-label="area"] path { pointer-events: none; }
```

Keep `.a-line`, `.a-bar`, `.a-gridline`, `.a-zeroline`, `.a-axis`, `.a-peak`, `.a-barval`, `.a-hit`, `.a-point`, `.a-tip` exactly as they are — the tests read them.

- [ ] **Step 2: Run `tests/analytics/test_contrast.py` and the chart tests** — green.

- [ ] **Step 3: Commit**

```bash
git add site/css/analytics.css
git commit -m "style(analytics): chart type owned by analytics.css now that Plot's stylesheet is stripped"
```

---

### Task 13: Screenshots for review

Nav reviews pictures, not diffs, for a chart change. Produce six PNGs on the fixtures, one per tab, at 1440 wide.

**Files:**
- Create: `tests/analytics/shoot.py`
- Create: `docs/superpowers/plans/plan-4-shots/*.png`

- [ ] **Step 1: Write the script**

```python
"""Screenshots of the six tabs on the committed fixtures, for review.
Run: python tests/analytics/shoot.py  (from the repo root; uses the same stubs as the suite).

Everything here is what the `dashboard` fixture in conftest.py does, minus pytest:
the same static server over site/, the same Supabase stub, the same sign-in."""
import socket
import sys
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "analytics"))

from playwright.sync_api import sync_playwright  # noqa: E402

from conftest import ANALYTICS, SITE, QuietHandler, Supabase, sign_in  # noqa: E402
from test_tabs import open_tab  # noqa: E402

OUT = ROOT / "docs" / "superpowers" / "plans" / "plan-4-shots"
TABS = ["overview", "growth", "posts", "episodes", "audience", "health"]


def serve_site():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=str(SITE)))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    httpd, base_url = serve_site()
    stub = Supabase()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        stub.install(page)
        sign_in(page)
        page.goto(base_url + ANALYTICS)
        page.wait_for_selector("#shell:not([hidden])")
        for tab in TABS:
            open_tab(page, tab)
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / f"{tab}.png"), full_page=True)
            print("shot", tab)
        browser.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
```

`Supabase`, `sign_in`, `ANALYTICS`, `SITE` and `QuietHandler` are module-level names in `tests/analytics/conftest.py`; `open_tab` is at the top of `tests/analytics/test_tabs.py`. If `_context()` in conftest sets anything beyond the viewport (read it), mirror that on `new_context` here.

- [ ] **Step 2: Run it and look at the six PNGs**

Run: `python tests/analytics/shoot.py`
Expected: six files. Open each. Check: no colliding date labels, integer ticks on counts, gained above and lost below the line in two colours, three small view charts on the overview, every chart under Hanken Grotesk.

- [ ] **Step 3: Run the whole suite one last time**

Run: `python -m pytest tests/ -q`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/analytics/shoot.py docs/superpowers/plans/plan-4-shots/
git commit -m "chore(analytics): screenshot script and the six tabs on fixtures after Plan 4"
```

---

## Nav's verification when it lands

1. `fetch-remote-worker.ps1 -Repo tsntalks -Name tsn-p4`; read `git diff HEAD...worker/tsn-p4` commit by commit. Thirteen commits expected.
2. Rerun `python -m pytest tests/ -q` on the laptop and on the desktop; confirm no test was edited to pass except the three this plan names (gap, overview kinds, subscribers).
3. Open the six PNGs, then the live `/analytics` on real data, every tab, 30-day and 12-month frames, "Compare with previous period" on.
4. Confirm `db/007` (Part A) is applied and the Overview's views chart no longer has the 14 Sep column.
5. Check `site/analytics/index.html` and `monthly-review.html` load d3 before Plot and both hashes match the plan.
6. Forbidden list untouched: `site/index.html`, `site/live/`, `site/partner/`, `site/js/home.js`, `site/js/live.js`, `collector/`, `db/`.
