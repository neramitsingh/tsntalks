"""The six tabs.

Two kinds of test in here. Per-tab tests that check a tab says what it is
supposed to say, and structural tests at the bottom that hold for EVERY tab —
no chart without its table twin, no panel without its window, no blank state,
and a dead endpoint never taking a whole tab with it.
"""
import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"

BUILT = ["overview", "growth", "posts", "episodes", "audience", "health"]


def load(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def open_tab(page, tab):
    """Wait for the tab to have finished drawing, not merely to have started.

    #view carries data-tab and data-state so a test never reads the previous
    tab's panels — which is the same reason the dashboard clears the view on a
    tab change in the first place.
    """
    page.click(f"#tab-{tab}")
    page.wait_for_selector(f'#view[data-tab="{tab}"][data-state="ready"]')
    return page


def ready(page):
    page.wait_for_selector('#view[data-state="ready"]')
    return page


def panels(page):
    return page.locator("#view .a-panel")


# --- Overview ---------------------------------------------------------------

@pytest.fixture
def ov(dashboard):
    open_tab(dashboard, "overview")
    return dashboard


def test_the_answer_is_in_the_first_panel(ov):
    """"How are we doing" in five seconds. The four figures come first, and
    nothing below them is load-bearing."""
    first = panels(ov).first
    assert "How are we doing" in first.inner_text()
    labels = first.locator(".a-fig .k").all_text_contents()
    assert labels == ["Views", "Followers", "Posts published", "Engagement rate"]


def test_the_headline_figures_are_the_numbers_the_data_layer_computed(ov):
    text = panels(ov).first.inner_text()
    # 69,900 views over the stubbed window; compact() renders it as 69.9K... but
    # the full figure is in the title attribute, which is the rule everywhere.
    titles = ov.locator("#view .a-fig .n").evaluate_all(
        "els => els.map(e => e.getAttribute('title'))")
    assert "69,900" in titles
    assert "9,260" in titles              # followers: 4080 + 3080 + 2100
    assert "9" in text                    # nine posts published in the window


def test_a_delta_carries_a_sign_an_arrow_and_a_colour(dashboard):
    """Three channels. Green against red is the pair a dichromat viewer cannot
    separate, so colour is never the only one."""
    dashboard.check("#compare")
    dashboard.wait_for_selector("#view .a-delta[data-dir]")
    d = dashboard.locator("#view .a-delta").first
    assert d.locator(".arrow").count() == 1
    assert d.get_attribute("data-dir") in ("up", "down", "flat")
    assert dashboard.evaluate(
        "getComputedStyle(document.querySelector('#view .a-delta')).color") != "rgba(0, 0, 0, 0)"


def test_with_compare_off_the_figures_say_there_is_no_comparison(ov):
    texts = ov.locator("#view .a-delta").all_inner_texts()
    assert texts and all("no comparison" in t for t in texts)


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


def test_the_follower_panel_explains_the_carry_forward_and_the_first_period(ov):
    """Both are places a reader would otherwise draw the wrong conclusion:
    a flat period is not a period with no followers, and a first period showing
    no gain is an absence of evidence rather than a flat start."""
    text = ov.locator("#view .a-panel", has_text="Follower growth").inner_text()
    assert "repeats the previous value" in text
    assert "nothing earlier to compare" in text


def test_top_posts_lists_the_ten_that_gained_most(ov):
    section = ov.locator("#view .a-panel", has_text="Top posts in this window")
    rows = section.locator("tbody tr")
    assert rows.count() == 10
    gained = section.locator("tbody td.num").evaluate_all(
        "els => els.filter(e => e.cellIndex === 2).map(e => Number(e.dataset.value))")
    assert gained == sorted(gained, reverse=True)
    assert gained[0] == 18000          # ig:FIXCLIP01


def test_top_posts_distinguishes_gained_here_from_lifetime(ov):
    section = ov.locator("#view .a-panel", has_text="Top posts in this window")
    # text_contents, not inner_text: table headers are uppercased in CSS.
    headers = section.locator("thead th").all_text_contents()
    assert "Gained here" in headers and "Views total" in headers
    assert "lifetime" in section.inner_text()


def test_a_post_title_is_a_link_that_opens_safely(ov):
    link = ov.locator("#view .a-panel", has_text="Top posts").locator("tbody a").first
    assert link.get_attribute("target") == "_blank"
    assert "noopener" in link.get_attribute("rel")


def test_the_platform_column_is_never_colour_alone(ov):
    cells = ov.locator("#view .a-plat").all_inner_texts()
    assert cells
    assert all(c.strip() in ("YouTube", "Instagram", "TikTok") for c in cells)


def test_filtering_to_one_platform_drops_the_legend(dashboard):
    open_tab(dashboard, "overview")
    assert dashboard.locator("#view .a-legend").first.locator("li").count() == 3
    dashboard.click('[data-control="platform"]:text-is("TikTok")')
    # The redraw is async; waiting for a panel would match the one still there.
    dashboard.wait_for_function(
        "document.querySelectorAll('#view .a-legend').length === 0")
    assert dashboard.locator("#view svg.a-chart").count() == 2


# --- Growth -----------------------------------------------------------------

@pytest.fixture
def gr(dashboard):
    open_tab(dashboard, "growth")
    return dashboard


def panel_named(page, title):
    return page.locator("#view .a-panel").filter(has=page.locator(f'h2:text-is("{title}")'))


def test_growth_answers_which_channel_is_growing(gr):
    titles = gr.locator("#view .a-panel h2").all_text_contents()
    assert titles == ["Followers by platform", "Followers gained and lost",
                      "YouTube subscribers", "Watch time", "Average view duration"]


def test_followers_are_lines_and_gains_are_bars(gr):
    """A stock gets a line; a flow gets a bar. Bars of a stock invite a sum."""
    assert panel_named(gr, "Followers by platform").locator("path.a-line").count() > 0
    assert panel_named(gr, "Followers gained and lost").locator("rect.a-bar").count() > 0


def test_gained_and_lost_diverge_around_a_zero_line(gr):
    """Not a net line: +3 that hides 40 arriving and 37 leaving is a different
    story from three people arriving."""
    section = panel_named(gr, "Followers gained and lost")
    assert section.locator("line.a-zeroline").count() == 1
    values = section.locator("g.a-point").evaluate_all(
        "els => els.map(e => Number(e.dataset.value))")
    assert any(v > 0 for v in values)
    assert any(v < 0 for v in values)


def test_the_twin_lists_losses_as_the_positive_counts_they_are(gr):
    section = panel_named(gr, "Followers gained and lost")
    headers = section.locator("details.a-twin thead th").all_text_contents()
    assert headers == ["Period", "Gained", "Lost", "Net"]
    lost = section.evaluate("""(el) => [...el.querySelectorAll('details.a-twin tbody tr')]
        .map((tr) => Number(tr.children[2].dataset.value))""",
        section.element_handle())
    assert lost and all(v >= 0 for v in lost)


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


def test_watch_time_and_average_duration_are_two_charts_not_two_axes(gr):
    """The one rule the spec states twice. Different units never share an axis."""
    for title in ("Watch time", "Average view duration"):
        assert panel_named(gr, title).locator("svg.a-chart").count() == 1
    assert "different units never share an axis" in         panel_named(gr, "Average view duration").inner_text()


def test_the_panels_that_are_youtube_only_say_so(gr):
    text = panel_named(gr, "Watch time").inner_text()
    assert "Instagram and TikTok do not report watch time" in text


def test_a_metric_nobody_reported_is_named_rather_than_drawn_as_zero(browser, stub,
                                                                     analytics_url, signin):
    """A flat line at zero across a quarter is a claim that nobody watched."""
    stub.tables["metric_daily"] = [
        r for r in stub.tables["metric_daily"] if r["metric"] != "yt_minutes"]
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url + "?tab=growth")
    pg.wait_for_selector('#view[data-state="ready"]')

    section = pg.locator("#view .a-panel").filter(
        has=pg.locator('h2:text-is("Watch time")'))
    assert section.locator("svg.a-chart").count() == 0
    text = section.inner_text()
    assert "absence of data, not a zero" in text
    assert "YouTube" in text
    ctx.close()


def test_average_duration_is_weighted_by_views_not_a_mean_of_daily_means(dashboard):
    """A Tuesday with forty views must not count the same as the day an episode
    landed. Same mistake as a mean of rates, one level down."""
    got = dashboard.evaluate("""async () => {
      const data = await import('/js/analytics/data.js');
      const w = await data.windowFor({ frame: '30d', granularity: 'month', platform: 'all' });
      const r = await data.dailyMetrics(w, ['yt_views', 'yt_avg_duration']);
      const bucket = r.current.byPeriod.yt_avg_duration.at(-1);
      // Only the days inside that bucket; a 30-day frame read monthly spans two.
      const rows = r.current.byMetric.yt_avg_duration.filter((x) => x.day >= bucket.period);
      const views = new Map(r.current.byMetric.yt_views.map(
        (v) => [v.day.getTime(), v.value]));
      const plain = rows.reduce((a, x) => a + x.value, 0) / rows.length;
      const weighted = rows.reduce((a, x) => a + x.value * views.get(x.day.getTime()), 0)
        / rows.reduce((a, x) => a + views.get(x.day.getTime()), 0);
      return { got: bucket.value, plain, weighted, days: rows.length };
    }""")
    assert got["days"] > 1, "the fixture no longer spans enough days to tell them apart"
    assert got["got"] == pytest.approx(got["weighted"], rel=1e-9)
    assert got["got"] != pytest.approx(got["plain"], rel=1e-9)


def test_a_duration_is_shown_as_time_not_as_a_bare_number(gr):
    # text_content, not inner_text: the twin is a closed <details>.
    text = panel_named(gr, "Average view duration").locator("details.a-twin").text_content()
    assert "m " in text and "s" in text


# --- Posts ------------------------------------------------------------------

@pytest.fixture
def po(dashboard):
    open_tab(dashboard, "posts")
    return dashboard


def headers(page):
    """Column names without the sort marker the active column carries."""
    return [t.strip().rstrip("▲▼")
            for t in page.locator("#view thead th button.a-sort").all_text_contents()]


def column_values(page, name):
    """The data-value of one column, in the order the table draws it."""
    return page.evaluate("""(name) => {
      const heads = [...document.querySelectorAll('#view table.a-sortable thead th')];
      const i = heads.findIndex((th) => th.textContent.trim().startsWith(name));
      return [...document.querySelectorAll('#view table.a-sortable tbody tr:not(.a-expanded)')]
        .map((tr) => {
          const td = tr.children[i];
          return td.dataset.value === undefined ? td.textContent.trim() : Number(td.dataset.value);
        });
    }""", name)


def test_the_posts_table_has_every_column_the_spec_lists(po):
    assert headers(po) == ["Platform", "Published", "Post", "Views", "Likes", "Comments",
                           "Shares", "Reach", "Engagement", "Gained here"]


def test_every_post_is_listed(po):
    assert po.locator("#view table.a-sortable tbody tr:not(.a-expanded)").count() == len(load("post_deltas"))


def test_reach_reads_as_not_reported_where_a_platform_does_not_report_it(po):
    """A zero there would be a claim that nobody saw the post."""
    cells = po.evaluate("""() => {
      const heads = [...document.querySelectorAll('#view table.a-sortable thead th')];
      const i = heads.findIndex((th) => th.textContent.trim().startsWith('Reach'));
      return [...document.querySelectorAll('#view table.a-sortable tbody tr:not(.a-expanded)')].map((tr) => ({
        platform: tr.children[1].textContent.trim(),
        text: tr.children[i].textContent.trim(),
        none: tr.children[i].classList.contains('none'),
      }));
    }""")
    for c in cells:
        if c["platform"] == "Instagram":
            assert not c["none"] and c["text"] != "0"
        else:
            assert c["none"] and c["text"] == "—"


def test_the_table_opens_sorted_by_what_gained_most(po):
    gained = column_values(po, "Gained here")
    assert gained == sorted(gained, reverse=True)


def test_every_column_sorts_both_ways(po):
    for name in ("Views", "Likes", "Comments", "Shares", "Engagement", "Gained here"):
        po.click(f'#view thead th button.a-sort:has-text("{name}")')
        first = column_values(po, name)
        assert first == sorted(first, reverse=True), name
        po.click(f'#view thead th button.a-sort:has-text("{name}")')
        second = column_values(po, name)
        assert second == sorted(second), name


def test_sorting_records_itself_for_a_screen_reader(po):
    po.click('#view thead th button.a-sort:has-text("Likes")')
    states = po.locator("#view table.a-sortable thead th").evaluate_all(
        "els => els.map(e => e.getAttribute('aria-sort'))")
    assert states.count("descending") == 1
    assert states.count("ascending") == 0


def test_a_column_that_is_not_reported_sorts_to_the_bottom_either_way(po):
    """Null is not the smallest value; it is not a value."""
    for _ in range(2):
        po.click('#view thead th button.a-sort:has-text("Reach")')
        values = column_values(po, "Reach")
        dashes = [i for i, v in enumerate(values) if v == "—"]
        assert dashes == list(range(len(values) - len(dashes), len(values)))


def test_a_post_that_lost_views_is_shown_as_negative_not_hidden(po):
    po.click('#view thead th button.a-sort:has-text("Gained here")')   # ascending
    first = po.locator("#view table.a-sortable tbody tr:not(.a-expanded)").first
    assert "tt:FIXCLIP03" == first.get_attribute("data-post-id")
    assert first.locator("td.neg").count() >= 1


def narrow(page, needle):
    page.fill("#posts-search", needle)
    page.wait_for_function(
        "document.getElementById('posts-count').textContent.includes(' of ')")
    return page.locator("#view table.a-sortable tbody tr:not(.a-expanded)")


def test_the_title_filter_narrows_the_table_and_says_by_how_much(po):
    before = po.locator("#view table.a-sortable tbody tr:not(.a-expanded)").count()
    # Placeholder Singh has the long cut, one Reel and one TikTok.
    assert narrow(po, "Placeholder").count() == 3
    assert f"of {before} posts" in po.inner_text("#posts-count")


def test_the_filter_reads_the_post_id_as_well_as_the_title(po):
    """Pasting an id out of the database and finding the row is worth more than
    a filter that only matches prose."""
    assert narrow(po, "FIXSHORT01").count() == 1


def test_a_filter_that_matches_nothing_says_so_by_name(po):
    po.fill("#posts-search", "zzzz-no-such-post")
    po.wait_for_selector("#view .a-empty")
    assert "zzzz-no-such-post" in po.inner_text("#view .a-empty")


def test_the_filter_and_the_sort_survive_together(po):
    po.click('#view thead th button.a-sort:has-text("Views")')
    assert narrow(po, "Sample Kaur").count() == 2
    views = column_values(po, "Views")
    assert views == sorted(views, reverse=True)
    assert len(views) == 2


def test_clicking_a_row_expands_its_own_view_curve(po):
    po.locator("#view table.a-sortable tbody button.a-expand").first.click()
    po.wait_for_selector("#view tr.a-expanded svg.a-chart")
    expanded = po.locator("#view tr.a-expanded")
    assert expanded.count() == 1
    assert expanded.locator("details.a-twin").count() == 1
    assert po.locator('#view table.a-sortable tbody button.a-expand[aria-expanded="true"]').count() == 1


def test_the_expanded_curve_closes_again(po):
    toggle = po.locator("#view table.a-sortable tbody button.a-expand").first
    toggle.click()
    po.wait_for_selector("#view tr.a-expanded svg.a-chart")
    toggle.click()
    assert po.locator("#view tr.a-expanded").count() == 0


def test_the_expand_toggle_is_a_button_with_an_accessible_name(po):
    toggle = po.locator("#view table.a-sortable tbody button.a-expand").first
    assert toggle.get_attribute("aria-expanded") == "false"
    assert "view curve" in toggle.get_attribute("aria-label")


def test_the_platform_control_is_the_only_platform_filter(po):
    """Two controls that mean the same thing is how a dashboard starts lying."""
    assert "Platform is the control above" in po.inner_text("#view .a-filters")
    assert po.locator("#view .a-filters select").count() == 0


def test_the_exported_view_is_the_view_on_screen(po):
    """The posts-table artifact reads this, so what you filtered is what you get."""
    po.click('#view thead th button.a-sort:has-text("Likes")')
    narrow(po, "Testy")
    view = po.evaluate("""async () => {
      const m = await import('/js/analytics/tabs/posts.js');
      return { sort: m.postsView.sort, search: m.postsView.search,
               ids: m.postsView.rows.map((r) => r.postId) };
    }""")
    on_screen = po.locator("#view table.a-sortable tbody tr:not(.a-expanded)").evaluate_all(
        "els => els.map(e => e.dataset.postId)")
    assert view["ids"] == on_screen
    assert view["sort"] == {"key": "likes", "dir": "desc"}
    assert view["search"] == "Testy"


# --- Episodes ---------------------------------------------------------------

@pytest.fixture
def ep(dashboard):
    open_tab(dashboard, "episodes")
    return dashboard


def episode_rows(page):
    return page.locator("#view .a-panel").filter(
        has=page.locator('h2:text-is("Episodes")')).locator("tbody tr:not(.a-expanded)")


def test_one_row_per_episode_with_the_columns_the_spec_lists(ep):
    section = ep.locator("#view .a-panel").filter(has=ep.locator('h2:text-is("Episodes")'))
    headers = [h for h in section.locator("thead th").all_text_contents() if h.strip()]
    assert headers == ["Episode", "Guest", "Role", "Published", "YouTube", "Clips",
                       "Clip views · YT", "Clip views · IG", "Clip views · TT", "All cuts"]
    assert episode_rows(ep).count() == len(load("episode_rollup"))


def test_the_figures_are_the_ones_episode_rollup_returned(ep):
    expected = {e["episode_id"]: e for e in load("episode_rollup")}
    got = ep.evaluate("""() => {
      const section = [...document.querySelectorAll('#view .a-panel')]
        .find((p) => p.querySelector('h2')?.textContent === 'Episodes');
      return [...section.querySelectorAll('tbody tr:not(.a-expanded)')].map((tr) => ({
        id: Number(tr.dataset.episodeId),
        values: [...tr.querySelectorAll('td.num')].map((td) => Number(td.dataset.value)),
      }));
    }""")
    for row in got:
        e = expected[row["id"]]
        assert row["values"] == [e["yt_views"], e["clip_count"], e["clip_views_youtube"],
                                 e["clip_views_instagram"], e["clip_views_tiktok"],
                                 e["total_reach"]]


def test_the_panel_says_the_time_frame_does_not_apply(ep):
    """A panel with no window label, on a page full of windowed panels, reads as
    "the window above" by default."""
    section = ep.locator("#view .a-panel").filter(has=ep.locator('h2:text-is("Episodes")'))
    assert "time frame does not apply" in section.inner_text()


def test_all_cuts_is_named_as_a_sum_of_views_and_not_as_people(ep):
    """The artifacts inherit this figure and a sponsor will ask what it means."""
    section = ep.locator("#view .a-panel").filter(has=ep.locator('h2:text-is("Episodes")'))
    text = section.inner_text()
    assert "SUM OF VIEW COUNTS" in text
    assert "is not people" in text


def test_expanding_an_episode_lists_its_cuts_and_their_split(ep):
    episode_rows(ep).first.locator("button.a-expand").click()
    ep.wait_for_selector("#view tr.a-expanded svg.a-chart")
    expanded = ep.locator("#view tr.a-expanded")
    # `td > .a-tablewrap` is the cuts table; the split chart's twin sits inside
    # a <details> and would otherwise be counted too.
    assert expanded.locator("td > .a-tablewrap tbody tr").count() == 3
    assert expanded.locator("details.a-twin").count() == 1


def test_the_long_cut_is_not_listed_among_its_own_clips(ep):
    episode_rows(ep).first.locator("button.a-expand").click()
    ep.wait_for_selector("#view tr.a-expanded svg.a-chart")
    links = ep.locator("#view tr.a-expanded td > .a-tablewrap tbody a").evaluate_all(
        "els => els.map(e => e.href)")
    assert not any("watch?v=FIXTUREVID01" in href for href in links)


def test_a_row_offers_the_two_artifacts_and_names_their_recipients(ep):
    """There is no generic "export this view". Every artifact goes to a named
    person, and the UI says so rather than merely being true."""
    episode_rows(ep).first.locator("button.a-expand").click()
    ep.wait_for_selector("#view .a-artifacts")
    # One button per format: the guest card is offered as both a PDF and a PNG.
    labels = ep.locator("#view .a-artifacts button").all_text_contents()
    assert labels == ["Episode report", "Guest card · PDF", "Guest card · PNG"]
    recipients = ep.locator("#view .a-recipient").all_text_contents()
    assert recipients == ["to the episode’s sponsor", "to the guest"]


def test_an_artifact_that_does_not_exist_yet_is_disabled_and_says_why(ep):
    """A missing button is a feature nobody knows about; a disabled one that
    says why is a promise with a date on it."""
    episode_rows(ep).first.locator("button.a-expand").click()
    ep.wait_for_selector("#view .a-artifacts")
    for button in ep.locator("#view .a-artifacts button").all():
        if button.is_disabled():
            assert "Not built yet" in button.get_attribute("title")


def test_clips_the_collector_could_not_match_are_listed_separately(ep):
    section = ep.locator("#view .a-panel").filter(
        has=ep.locator('h2:text-is("Unassigned clips")'))
    rows = section.locator("tbody tr")
    assert rows.count() == 1
    assert "The clip the platform quietly recounted" in rows.first.inner_text()


def test_the_unassigned_panel_says_where_an_assignment_is_actually_made(ep):
    """The dashboard does not write. Spec §4 describes assigning by hand here;
    the assignment lives in data/episodes.json and the collector instead."""
    section = ep.locator("#view .a-panel").filter(
        has=ep.locator('h2:text-is("Unassigned clips")'))
    text = section.inner_text()
    assert "data/episodes.json" in text
    assert "only reads" in text


def test_the_unassigned_list_ignores_the_platform_control(browser, stub, analytics_url,
                                                          signin):
    """A clip is unassigned wherever it was posted. Hiding two thirds of the
    list behind a filter makes "everything is matched" look true."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url + "?tab=episodes&p=youtube")
    pg.wait_for_selector('#view[data-state="ready"]')
    section = pg.locator("#view .a-panel").filter(
        has=pg.locator('h2:text-is("Unassigned clips")'))
    assert section.locator("tbody tr").count() == 1      # the TikTok one
    ctx.close()


# --- Audience ---------------------------------------------------------------

@pytest.fixture
def au(dashboard):
    open_tab(dashboard, "audience")
    return dashboard


AUDIENCE_PANELS = ["YouTube · age", "YouTube · gender", "YouTube · country",
                   "Instagram · age", "Instagram · city", "Instagram · country"]


def test_the_six_panels_the_spec_lists(au):
    assert au.locator("#view .a-panel h2").all_text_contents() == AUDIENCE_PANELS


def test_every_audience_panel_names_its_own_window_in_its_subtitle(au):
    """The exact thing that let the old media kit claim India 54%. A demographic
    figure without its window is not a weak claim; it is a different claim."""
    subs = au.locator("#view .a-panel header .a-window").all_text_contents()
    assert len(subs) == 6
    assert all(s.strip() for s in subs)


def test_the_window_is_the_platform_s_not_the_control_above(au):
    """YouTube reports a rolling 90 days and Instagram 30. The frame control
    does not change either, and the panels must show what the data came with."""
    windows = au.locator("#view .a-panel header .a-window").all_text_contents()
    # The fixture's YouTube window is 18 Jun - 15 Sept; Instagram's 17 Aug - 15 Sept.
    assert windows[0] == windows[1] == windows[2]
    assert windows[3] == windows[4] == windows[5]
    assert windows[0] != windows[3]


def test_changing_the_frame_does_not_change_an_audience_window(dashboard):
    open_tab(dashboard, "audience")
    before = dashboard.locator("#view .a-panel header .a-window").all_text_contents()
    dashboard.click('[data-control="frame"]:text-is("7 days")')
    dashboard.wait_for_selector('#view[data-state="ready"]')
    assert dashboard.locator("#view .a-panel header .a-window").all_text_contents() == before


def test_each_panel_is_bars_with_a_table_twin(au):
    for title in AUDIENCE_PANELS:
        section = panel_named(au, title)
        assert section.locator("svg.a-chart rect.a-bar").count() > 0, title
        assert section.locator("details.a-twin").count() == 1, title


def test_the_bar_is_a_share_so_percentage_and_count_kinds_read_alike(au):
    """yt_age arrives as percentages, ig_age as follower counts. Both draw as a
    share of the rows, so neither needs explaining next to the other."""
    for title in ("YouTube · age", "Instagram · age"):
        values = panel_named(au, title).locator("text.a-barval").all_text_contents()
        assert values and all(v.endswith("%") for v in values), title
        assert sum(float(v.rstrip("%")) for v in values) == pytest.approx(100, abs=1), title


def test_the_twin_carries_the_raw_value_under_the_right_unit(au):
    headers = panel_named(au, "YouTube · country").locator(
        "details.a-twin thead th").all_text_contents()
    assert headers == ["Group", "Share", "Views", "Share before", "Change"]
    ig = panel_named(au, "Instagram · country").locator(
        "details.a-twin thead th").all_text_contents()
    assert ig[2] == "Followers"


def test_country_codes_are_spelled_the_way_the_public_pages_spell_them(au):
    labels = panel_named(au, "YouTube · country").locator(
        "details.a-twin tbody td:first-child").all_text_contents()
    assert "Thailand" in labels and "India" in labels
    assert "TH" not in labels


def test_the_change_is_stated_in_percentage_points(au):
    """"India is down 40%" is read as a share by nearly everyone who sees it,
    and a share is exactly what it is not."""
    text = panel_named(au, "YouTube · country").text_content()
    assert "pp" in text
    assert "Biggest shifts" in text


def test_the_biggest_shifts_are_the_ones_the_fixture_encodes(au):
    text = panel_named(au, "YouTube · country").inner_text()
    assert "Thailand" in text and "India" in text
    directions = panel_named(au, "YouTube · country").locator(
        ".a-note .a-delta").evaluate_all("els => els.map(e => e.dataset.dir)")
    assert "up" in directions and "down" in directions


def test_a_kind_with_no_earlier_window_says_so_instead_of_showing_a_rise(au):
    section = panel_named(au, "Instagram · city")
    text = section.inner_text()
    assert "No comparable earlier window" in text
    assert "no comparable earlier window" in         section.locator("header .sub").inner_text().lower()
    assert section.locator(".a-note .a-delta").count() == 0


def test_a_long_tail_is_described_rather_than_silently_dropped(browser, stub,
                                                               analytics_url, signin):
    stub.rpc["demographics_compare"]["yt_country"] += [
        {"dimension": code, "value": 10, "prev_value": 10, "delta": 0,
         "window_start": "2026-06-18", "window_end": "2026-09-15",
         "prev_window_start": "2026-03-20", "prev_window_end": "2026-06-17"}
        for code in ("SG", "MY", "AE", "NZ", "DE", "ID", "PH", "JP", "KR")
    ]
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url + "?tab=audience")
    pg.wait_for_selector('#view[data-state="ready"]')
    section = pg.locator("#view .a-panel").filter(
        has=pg.locator('h2:text-is("YouTube · country")'))
    assert "largest of 14" in section.inner_text()
    ctx.close()


# --- Health -----------------------------------------------------------------

@pytest.fixture
def he(dashboard):
    open_tab(dashboard, "health")
    return dashboard


def test_health_covers_the_pipeline_end_to_end(he):
    assert he.locator("#view .a-panel h2").all_text_contents() == [
        "The collector", "Freshness per platform", "Accounts", "Recent runs", "Row counts"]


def test_the_thresholds_are_written_on_screen_not_implied_by_colour(he):
    """A green dot that means "under two hours" means "fine" to everyone who
    did not write the page, and "fine" is not a measurement."""
    text = panel_named(he, "The collector").inner_text()
    assert "Green under 2 hours, amber under 6, red beyond" in text
    assert "collector runs hourly" in text


def test_every_state_carries_its_word_as_well_as_its_colour(he):
    pills = he.locator("#view .a-pill").evaluate_all(
        "els => els.map(e => ({ state: e.dataset.state, text: e.textContent.trim() }))")
    assert pills
    assert all(p["state"] in ("ok", "warn", "bad") for p in pills)
    assert all(p["text"] for p in pills)


def test_a_fresh_collector_run_reads_green(he):
    assert panel_named(he, "The collector").locator(
        '.a-pill[data-state="ok"]').count() == 1


@pytest.mark.parametrize("minutes,expected", [(25, "ok"), (200, "warn"), (600, "bad")])
def test_the_dot_follows_the_thresholds_it_printed(browser, stub, analytics_url, signin,
                                                   minutes, expected):
    stub.last_run_minutes_ago = minutes
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url + "?tab=health")
    pg.wait_for_selector('#view[data-state="ready"]')
    section = pg.locator("#view .a-panel").filter(
        has=pg.locator('h2:text-is("The collector")'))
    assert section.locator(".a-pill").first.get_attribute("data-state") == expected
    ctx.close()


def test_a_platform_can_be_silent_while_the_run_says_ok(he):
    """The failure this tab exists for. An expired token stops one account
    without stopping the run, and a green header would hide it."""
    section = panel_named(he, "Freshness per platform")
    states = section.locator("tbody .a-pill").evaluate_all(
        "els => els.map(e => e.dataset.state)")
    assert states.count("ok") == 2          # YouTube and Instagram
    assert "ok" not in states[states.index("ok") + 1:] or len(set(states)) > 1
    assert "notices" in section.inner_text()


def test_an_account_that_needs_reconnecting_is_named_with_what_it_costs(he):
    section = panel_named(he, "Accounts")
    assert section.locator('.a-pill:text("Reconnect needed")').count() == 1
    text = section.inner_text()
    assert "TikTok" in text
    assert "every figure that includes it is short" in text


def test_the_accounts_table_shows_token_expiry_and_whether_analytics_work(he):
    headers = panel_named(he, "Accounts").locator("thead th").all_text_contents()
    assert headers == ["Platform", "Account", "State", "Analytics", "Token expires", "Checked"]


def test_a_failed_run_is_listed_with_the_step_that_failed(he):
    text = panel_named(he, "Recent runs").inner_text()
    assert "zernio returned 503" in text
    assert "tiktok token expired" in text


def test_an_unfamiliar_run_status_surfaces_as_amber_rather_than_reading_green(
        browser, stub, analytics_url, signin):
    """collector_runs.status is assumed to be ok/partial/failed. A fourth value
    must not quietly read as healthy."""
    stub.tables["collector_runs"] = [
        {**r, "status": "weird" if i == 0 else r["status"]}
        for i, r in enumerate(stub.tables["collector_runs"])]
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url + "?tab=health")
    pg.wait_for_selector('#view[data-state="ready"]')
    section = pg.locator("#view .a-panel").filter(
        has=pg.locator('h2:text-is("Recent runs")'))
    first = section.locator("tbody .a-pill").first
    assert first.get_attribute("data-state") == "warn"
    assert first.inner_text().strip() == "weird"
    ctx.close()


def test_row_counts_are_exact_and_a_dash_is_not_a_zero(he):
    section = panel_named(he, "Row counts")
    rows = section.locator("tbody tr").count()
    assert rows == 9                       # every table the dashboard reads
    text = section.inner_text()
    assert "4,200" in text                 # post_snapshots
    assert "not the same as zero" in text
    assert "Content-Range" in text


def test_a_table_that_cannot_be_counted_reads_as_unknown(browser, stub, analytics_url,
                                                          signin):
    stub.fail("demographics", status=500, message="nope")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url + "?tab=health")
    pg.wait_for_selector('#view[data-state="ready"]')
    row = pg.locator("#view .a-panel").filter(
        has=pg.locator('h2:text-is("Row counts")')).locator(
        "tbody tr", has_text="demographics")
    assert row.locator("td.none").count() == 1
    ctx.close()


# --- the rules that hold for every tab --------------------------------------

@pytest.mark.parametrize("tab", BUILT)
def test_no_chart_is_ever_drawn_without_its_table_twin(dashboard, tab):
    """The accessibility contract from the spec, and the thing that makes every
    figure copyable. Enforced on what is actually on screen, not on the API."""
    open_tab(dashboard, tab)
    orphans = dashboard.evaluate("""() => {
      return [...document.querySelectorAll('#view svg.a-chart')]
        .filter((svg) => !svg.closest('figure')?.querySelector('details.a-twin'))
        .map((svg) => svg.getAttribute('aria-label'));
    }""")
    assert orphans == []


@pytest.mark.parametrize("tab", BUILT)
def test_every_chart_has_an_accessible_name(dashboard, tab):
    open_tab(dashboard, tab)
    # Zero is allowed — the Posts tab draws no chart until a row is expanded —
    # but a chart without a name is not.
    names = dashboard.locator("#view svg.a-chart").evaluate_all(
        "els => els.map(e => e.getAttribute('aria-label'))")
    assert all(n for n in names)


@pytest.mark.parametrize("tab", BUILT)
def test_every_panel_names_the_window_it_is_describing(dashboard, tab):
    """The exact thing that let the old media kit claim India 54% from a window
    it never printed."""
    open_tab(dashboard, tab)
    missing = dashboard.evaluate("""() => {
      return [...document.querySelectorAll('#view .a-panel')]
        .filter((p) => !p.querySelector('header .a-window'))
        .map((p) => p.querySelector('h2')?.textContent);
    }""")
    assert missing == []


@pytest.mark.parametrize("tab", BUILT)
def test_no_panel_is_ever_blank(dashboard, tab):
    open_tab(dashboard, tab)
    blank = dashboard.evaluate("""() => {
      return [...document.querySelectorAll('#view .a-panel')]
        .filter((p) => p.innerText.trim().split('\\n').length < 2)
        .map((p) => p.querySelector('h2')?.textContent);
    }""")
    assert blank == []


@pytest.mark.parametrize("tab", BUILT)
def test_a_tab_draws_without_a_console_error(browser, base_url, stub, analytics_url,
                                             signin, tab):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # "Failed to load resource" is filtered and replaced by the response watcher
    # below, which can tell a same-origin script from Google Fonts having a bad
    # minute. The question here is whether the dashboard's own code errors.
    pg.on("console", lambda m: errors.append(m.text)
          if m.type == "error" and "Failed to load resource" not in m.text else None)

    def watch(response):
        same_origin = response.url.startswith(analytics_url.rsplit("/analytics/", 1)[0])
        if response.status >= 400 and same_origin:
            errors.append(f"{response.status} {response.url}")

    pg.on("response", watch)
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url + f"?tab={tab}")
    pg.wait_for_selector('#view[data-state="ready"]')
    pg.wait_for_timeout(500)
    ctx.close()
    assert errors == []


@pytest.mark.parametrize("tab", BUILT)
def test_no_horizontal_overflow_on_a_phone(phone, tab):
    open_tab(phone, tab)
    assert phone.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


def test_one_dead_endpoint_leaves_the_rest_of_the_tab_standing(browser, base_url, stub,
                                                               analytics_url, signin):
    """rollup_followers down. The follower panel says so; the views panel and
    the headline figures still draw."""
    stub.fail("rollup_followers", status=503, message="down")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url)
    pg.wait_for_selector('#view[data-state="ready"]')

    assert pg.locator("#view .a-error").count() >= 1
    assert "70K" in pg.locator("#view .a-panel", has_text="How are we doing").inner_text()
    # >= 1, not == 1: since Plan 4 the views panel is one small chart per
    # platform. What this line is here to say is that the panel still drew.
    assert pg.locator("#view .a-panel", has_text="Views over time")\
             .locator("svg.a-chart").count() >= 1
    ctx.close()


def test_an_empty_window_gets_a_named_empty_state_not_a_blank_panel(browser, stub,
                                                                    analytics_url, signin):
    for name in ("rollup_views", "rollup_followers", "rollup_engagement", "post_deltas"):
        stub.rpc[name] = []
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url)
    pg.wait_for_selector('#view[data-state="ready"]')

    empties = pg.locator("#view .a-empty").all_inner_texts()
    assert empties, "an empty window drew nothing at all"
    assert all(t.strip() for t in empties)
    assert pg.locator("#view .a-error").count() == 0, "empty is not an error"
    ctx.close()
