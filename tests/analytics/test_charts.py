"""Chart primitives, and the table twin that is not optional.

The contract from the spec is that every chart carries the same numbers as a
real table underneath it. These tests drive charts.js in the page and compare
what the marks claim against what the table says, rather than checking that a
chart merely exists.
"""
import pytest

SETUP = """
const charts = await import('/js/analytics/charts.js');
const format = await import('/js/analytics/format.js');
const mount = document.getElementById('view');
mount.replaceChildren();
const PLATFORMS = [{ id: 'youtube' }, { id: 'instagram' }, { id: 'tiktok' }];
const POINTS = [
  { label: '9 Sep',  values: { youtube: 1200, instagram: 4000, tiktok: 2500 } },
  { label: '10 Sep', values: { youtube: 900,  instagram: 3500, tiktok: 2200 } },
  { label: '11 Sep', values: { youtube: 1500, instagram: 6000, tiktok: 3000 } },
  { label: '12 Sep', values: { youtube: 1100, instagram: 5200, tiktok: 2800 } },
];
"""


def js(page, body):
    return page.evaluate(
        "async (src) => await (new Function(`return (async () => { ${src} })()`))()",
        SETUP + body)


@pytest.fixture
def c(dashboard):
    return dashboard


# --- the twin ---------------------------------------------------------------

@pytest.mark.parametrize("kind", ["line", "bar", "stacked"])
def test_a_chart_and_its_twin_carry_identical_numbers(c, kind):
    """Not a summary of the numbers. The same numbers."""
    got = js(c, f"""
      mount.appendChild(charts.chart(
        {{ kind: '{kind}', name: 'Views by platform', points: POINTS, series: PLATFORMS }}));
      const marks = [...mount.querySelectorAll('.a-point')]
        .map((g) => Number(g.dataset.value)).sort((a, b) => a - b);
      const cells = [...mount.querySelectorAll('.a-twin tbody td.num[data-value]')]
        .map((td) => Number(td.dataset.value));
      return {{ marks, cells }};
    """)
    # Every mark's value appears in the table. The table also carries the Total
    # column, which the chart does not draw as its own mark.
    assert got["marks"]
    for value in got["marks"]:
        assert value in got["cells"]
    # Twelve marks plus the four Total cells the chart does not draw as a mark.
    assert len(got["marks"]) == 12
    assert len(got["cells"]) == 16


def test_the_twin_has_one_row_per_point_and_a_total_column(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'stacked', name: 'Views by platform', points: POINTS, series: PLATFORMS }));
      return {
        rows: mount.querySelectorAll('.a-twin tbody tr').length,
        headers: [...mount.querySelectorAll('.a-twin thead th')].map((th) => th.textContent),
      };
    """)
    assert got["rows"] == 4
    assert got["headers"] == ["Period", "YouTube", "Instagram", "TikTok", "Total"]


def test_the_twin_totals_match_the_stacked_columns(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'stacked', name: 'Views by platform', points: POINTS, series: PLATFORMS }));
      return [...mount.querySelectorAll('.a-twin tbody tr')].map((tr) => {
        const cells = [...tr.querySelectorAll('td.num')].map((td) => Number(td.dataset.value));
        return { parts: cells.slice(0, -1), total: cells.at(-1) };
      });
    """)
    for row in got:
        assert sum(row["parts"]) == row["total"]


def test_chart_refuses_to_draw_without_an_accessible_name(c):
    got = js(c, """
      try {
        charts.chart({ kind: 'line', points: POINTS, series: PLATFORMS });
        return 'no error';
      } catch (err) { return err.message; }
    """)
    assert "accessible name" in got


def test_an_unknown_kind_fails_loudly_rather_than_drawing_nothing(c):
    got = js(c, """
      try {
        charts.chart({ kind: 'pie', name: 'Nope', points: POINTS, series: PLATFORMS });
        return 'no error';
      } catch (err) { return err.message; }
    """)
    assert "unknown kind" in got


def test_no_data_draws_a_named_empty_state_not_a_blank_frame(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views by platform', points: [], series: PLATFORMS }));
      return {
        svg: mount.querySelectorAll('svg.a-chart').length,
        text: mount.querySelector('.a-empty').textContent,
      };
    """)
    assert got["svg"] == 0
    assert "Views by platform" in got["text"]


# --- the legend rule --------------------------------------------------------

def test_one_series_has_no_legend_and_two_do(c):
    got = js(c, """
      const one = charts.chart(
        { kind: 'line', name: 'One', points: POINTS, series: [{ id: 'youtube' }] });
      const two = charts.chart(
        { kind: 'line', name: 'Two', points: POINTS,
          series: [{ id: 'youtube' }, { id: 'tiktok' }] });
      mount.append(one, two);
      return {
        one: one.querySelectorAll('.a-legend').length,
        two: two.querySelectorAll('.a-legend li').length,
      };
    """)
    assert got == {"one": 0, "two": 2}


def test_the_legend_names_the_platforms_the_way_the_public_pages_do(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views', points: POINTS, series: PLATFORMS }));
      return [...mount.querySelectorAll('.a-legend li')].map((li) => li.textContent);
    """)
    assert got == ["YouTube", "Instagram", "TikTok"]


# --- keyboard and tooltip ---------------------------------------------------

def test_every_point_is_reachable_by_tab_and_names_its_value(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views', points: POINTS, series: [{ id: 'youtube' }] }));
      const pts = [...mount.querySelectorAll('.a-point')];
      return {
        count: pts.length,
        focusable: pts.every((p) => p.getAttribute('tabindex') === '0'),
        labels: pts.map((p) => p.getAttribute('aria-label')),
      };
    """)
    assert got["count"] == 4
    assert got["focusable"]
    assert got["labels"][0] == "9 Sep · YouTube: 1,200"


def test_focus_shows_the_tooltip_and_blur_hides_it(c):
    got = js(c, """
      const fig = charts.chart(
        { kind: 'bar', name: 'Views', points: POINTS, series: [{ id: 'tiktok' }] });
      mount.appendChild(fig);
      const pts = [...mount.querySelectorAll('.a-point')];
      const tip = fig.querySelector('.a-tip');
      const before = tip.hidden;
      pts[2].focus();
      const shown = { hidden: tip.hidden, text: tip.textContent };
      pts[2].blur();
      return { before, shown, after: tip.hidden };
    """)
    assert got["before"] is True
    assert got["shown"]["hidden"] is False
    assert "11 Sep" in got["shown"]["text"] and "3,000" in got["shown"]["text"]
    assert got["after"] is True


def test_hover_shows_the_same_tooltip_as_focus(c):
    got = js(c, """
      const fig = charts.chart(
        { kind: 'bar', name: 'Views', points: POINTS, series: [{ id: 'tiktok' }] });
      mount.appendChild(fig);
      const pt = mount.querySelectorAll('.a-point')[1];
      const tip = fig.querySelector('.a-tip');
      pt.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }));
      const hovered = tip.textContent;
      pt.focus();
      return { hovered, focused: tip.textContent };
    """)
    assert got["hovered"] == got["focused"]


def test_escape_dismisses_the_tooltip(c):
    got = js(c, """
      const fig = charts.chart(
        { kind: 'bar', name: 'Views', points: POINTS, series: [{ id: 'tiktok' }] });
      mount.appendChild(fig);
      const pt = mount.querySelectorAll('.a-point')[0];
      const tip = fig.querySelector('.a-tip');
      pt.focus();
      pt.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      return tip.hidden;
    """)
    assert got is True


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


# --- the rules the spec fixes -----------------------------------------------

def test_gridlines_are_hairline_and_solid(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views', points: POINTS, series: PLATFORMS }));
      const line = mount.querySelector('.a-gridline');
      const s = getComputedStyle(line);
      return { width: s.strokeWidth, dash: s.strokeDasharray };
    """)
    assert got["width"] in ("1px", "1")
    assert got["dash"] in ("none", "")


def test_marks_are_thin(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views', points: POINTS, series: PLATFORMS }));
      return getComputedStyle(mount.querySelector('.a-line')).strokeWidth;
    """)
    assert float(got.replace("px", "")) <= 2


def test_only_the_peak_gets_a_direct_label(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'stacked', name: 'Views', points: POINTS, series: PLATFORMS }));
      return [...mount.querySelectorAll('text.a-peak')].map((t) => t.textContent);
    """)
    # 11 Sep totals 10,500 — the tallest column, and the only labelled one.
    # compact() rounds to 11K above ten thousand; the exact figure is in the
    # twin, which is the rule for every compact number on every surface here.
    assert got == ["11K"]


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


def test_a_missing_value_reads_as_not_reported_in_the_twin(c):
    got = js(c, """
      const gapped = [{ label: 'a', values: { youtube: null } }];
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views', points: gapped, series: [{ id: 'youtube' }] }));
      const td = mount.querySelector('.a-twin tbody td.num');
      return { text: td.textContent, klass: td.className, value: td.dataset.value };
    """)
    assert got["text"] == "—"
    assert "none" in got["klass"]
    assert got["value"] is None


def test_horizontal_bars_print_the_number_beside_the_bar(c):
    """PRODUCT.md: numbers are written in text, never only as bar lengths."""
    got = js(c, """
      mount.appendChild(charts.chart({
        kind: 'hbar', name: 'Views by country',
        points: [{ label: 'Thailand', value: 45000 }, { label: 'India', value: 9000 }],
      }));
      return {
        values: [...mount.querySelectorAll('text.a-barval')].map((t) => t.textContent),
        twin: [...mount.querySelectorAll('.a-twin tbody td')].map((t) => t.textContent),
      };
    """)
    assert got["values"] == ["45K", "9K"]
    assert got["twin"] == ["Thailand", "45,000", "India", "9,000"]


def test_charts_scale_by_viewbox_rather_than_by_measuring(c):
    got = js(c, """
      mount.appendChild(charts.chart(
        { kind: 'line', name: 'Views', points: POINTS, series: PLATFORMS }));
      const svg = mount.querySelector('svg.a-chart');
      return {
        viewBox: svg.getAttribute('viewBox'),
        width: svg.getAttribute('width'),
        cssWidth: getComputedStyle(svg).width,
      };
    """)
    assert got["viewBox"]
    assert got["width"] is None, "a fixed width defeats the viewBox"
    assert got["cssWidth"] != "0px"


def test_a_sparkline_is_the_one_mark_allowed_without_a_twin(c):
    """And only inline, beside cells that already carry the numbers."""
    got = js(c, """
      const s = charts.sparkline([1, 4, 2, 8, 5], { name: 'views trend' });
      mount.appendChild(s);
      return { label: s.getAttribute('aria-label'), paths: s.querySelectorAll('path').length };
    """)
    assert got == {"label": "views trend", "paths": 1}


def test_a_sparkline_with_one_point_draws_nothing_rather_than_a_flat_line(c):
    got = js(c, "return charts.sparkline([7]).querySelectorAll('path').length;")
    assert got == 0


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


def test_gained_and_lost_take_their_direction_colours_whatever_the_metric_is_called(c):
    got = js(c, """
      return ['yt_subs_gained', 'yt_subs_lost', 'ig_follows', 'ig_unfollows',
              'tt_followers_gained', 'tt_followers_lost', 'gained', 'lost', 'youtube', 'previous']
        .map((id) => charts.seriesColor(id));
    """)
    up, down = "var(--up)", "var(--down)"
    assert got == [up, down, up, down, up, down, up, down, "var(--yt)", "var(--muted)"]


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


# --- panels -----------------------------------------------------------------

def test_a_panel_subtitle_names_its_window(c):
    got = js(c, """
      const p = charts.panel({
        title: 'Views by platform',
        sub: charts.windowSub('Views', new Date('2026-09-08T17:00:00Z'),
                              new Date('2026-09-15T17:00:00Z')),
      });
      mount.appendChild(p);
      return { sub: p.querySelector('.sub').textContent,
               window: p.querySelector('.a-window').textContent };
    """)
    # "Sept", not "Sep": that is what en-GB gives for September, and it is what
    # the public pages already print through the same live-data.js formatter.
    assert got["window"] == "9–15 Sept 2026"
    assert got["sub"].startswith("Views ·")


def test_a_panel_subtitle_is_never_interpolated_as_html(c):
    """Half of what lands in a subtitle is a guest name or a platform caption."""
    got = js(c, """
      const p = charts.panel({ title: 'T', sub: '<img src=x onerror=alert(1)>' });
      mount.appendChild(p);
      return { imgs: p.querySelectorAll('img').length, text: p.querySelector('.sub').textContent };
    """)
    assert got["imgs"] == 0
    assert got["text"] == "<img src=x onerror=alert(1)>"


# --- after Plan 4's first look at real screenshots ------------------------------

def test_the_area_under_a_line_is_drawn_only_when_there_is_one_line(c):
    """Three overlapping 8% fills under the follower lines added up to a block
    that read as a fourth series. One line keeps its faint ground; several
    lines are lines."""
    got = js(c, """
      const one = charts.chart({ kind: 'line', name: 'One', points: POINTS, series: [{ id: 'youtube' }] });
      const three = charts.chart({ kind: 'line', name: 'Three', points: POINTS, series: PLATFORMS });
      mount.append(one, three);
      return {
        one: one.querySelectorAll('g[aria-label="area"] path').length,
        three: three.querySelectorAll('g[aria-label="area"] path').length,
        lines: three.querySelectorAll('path.a-line').length,
      };
    """)
    assert got == {"one": 1, "three": 0, "lines": 3}


def test_small_multiples_draw_on_a_narrower_canvas_so_their_type_stays_readable(c):
    """At a third of the row, a 720-wide viewBox scales 11px labels down to
    about 7px. Each multiple draws at 360 x 150 instead."""
    got = js(c, """
      const fig = charts.chart({ kind: 'multiples', name: 'Views by platform', points: POINTS, series: PLATFORMS });
      mount.appendChild(fig);
      return [...fig.querySelectorAll('svg.a-chart')].map((s) => s.getAttribute('viewBox'));
    """)
    assert got == ["0 0 360 150"] * 3


def test_a_narrow_canvas_thins_its_date_labels_harder(c):
    """Seven labels fit under a 720-wide chart and crowd a 360-wide one. Thinning
    counts label budget per canvas width, so the multiples show every other date."""
    got = js(c, """
      const seven = [9, 10, 11, 12, 13, 14, 15].map((d) => ({ label: `${d} Sept`, values: { youtube: d * 100 } }));
      const wide = charts.chart({ kind: 'line', name: 'Wide', points: seven, series: [{ id: 'youtube' }] });
      const narrow = charts.chart({ kind: 'multiples', name: 'Narrow', points: seven, series: [{ id: 'youtube' }] });
      mount.append(wide, narrow);
      const labels = (fig) => [...fig.querySelectorAll('g[aria-label="x-axis tick label"] text')].map((t) => t.textContent);
      return { wide: labels(wide), narrow: labels(narrow) };
    """)
    assert len(got["wide"]) == 7
    assert got["narrow"] == ["9 Sept", "11 Sept", "13 Sept", "15 Sept"]
