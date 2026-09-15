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

BUILT = ["overview", "posts"]


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


def test_views_are_drawn_as_stacked_columns_and_followers_as_lines(ov):
    """Followers are a stock. Bars invite the reader to add them up."""
    kinds = ov.evaluate("""() => {
      const out = {};
      for (const p of document.querySelectorAll('#view .a-panel')) {
        const title = p.querySelector('h2')?.textContent ?? '';
        const svg = p.querySelector('svg.a-chart');
        if (svg) out[title] = { bars: svg.querySelectorAll('rect.a-bar').length,
                                lines: svg.querySelectorAll('path.a-line').length };
      }
      return out;
    }""")
    assert kinds["Views over time"]["bars"] > 0
    assert kinds["Views over time"]["lines"] == 0
    assert kinds["Follower growth"]["lines"] > 0
    assert kinds["Follower growth"]["bars"] == 0


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
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
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
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url)
    pg.wait_for_selector('#view[data-state="ready"]')

    assert pg.locator("#view .a-error").count() >= 1
    assert "70K" in pg.locator("#view .a-panel", has_text="How are we doing").inner_text()
    assert pg.locator("#view .a-panel", has_text="Views over time")\
             .locator("svg.a-chart").count() == 1
    ctx.close()


def test_an_empty_window_gets_a_named_empty_state_not_a_blank_panel(browser, stub,
                                                                    analytics_url, signin):
    for name in ("rollup_views", "rollup_followers", "rollup_engagement", "post_deltas"):
        stub.rpc[name] = []
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
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
