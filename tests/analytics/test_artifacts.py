"""The artifact framework: the registry, the filenames, the source note, CSV
and XLSX.

The thing these tests are really protecting is the spec's rule that there is no
generic "export this view". Every artifact has a recipient and a reason, both of
them on screen next to the button, and every artifact carries the platforms, the
window and the collector run it was built from.
"""
import csv as csvmod
import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"

THE_FIVE = ["episode-report", "posts-table", "monthly-review", "guest-card",
            "numbers-today"]


def js(page, body):
    return page.evaluate("""async (src) => {
      const artifacts = await import('/js/analytics/artifacts/index.js');
      const csv = await import('/js/analytics/artifacts/csv.js');
      return await (new Function('artifacts', 'csv', `return (async () => { ${src} })()`))(
        artifacts, csv);
    }""", body)


@pytest.fixture
def a(dashboard):
    return dashboard


# --- the registry -----------------------------------------------------------

def test_the_five_artifacts_and_only_the_five(a):
    """Decided 2026-09-15. A sixth is an edit to a working dashboard after Sunny
    has seen these, and it needs a recipient before it needs a design."""
    assert js(a, "return artifacts.ARTIFACTS.map((x) => x.id);") == THE_FIVE


def test_every_artifact_declares_a_recipient_and_a_reason(a):
    rows = js(a, "return artifacts.ARTIFACTS;")
    for row in rows:
        assert row["recipient"] and row["recipient"] != "whoever clicked", row["id"]
        assert row["why"] and row["why"].endswith("."), row["id"]
        assert row["formats"], row["id"]
        assert row["scope"] in ("episode", "posts", "month", "date"), row["id"]


def test_the_formats_are_the_ones_the_spec_decided(a):
    rows = {r["id"]: r["formats"] for r in js(a, "return artifacts.ARTIFACTS;")}
    assert rows == {
        "episode-report": ["pdf"],
        "posts-table": ["csv", "xlsx"],
        "monthly-review": ["pdf", "xlsx"],
        "guest-card": ["pdf", "png"],
        "numbers-today": ["pdf"],
    }


def test_registering_an_artifact_that_does_not_exist_fails_loudly(a):
    got = js(a, """
      try { artifacts.register('not-a-thing', () => {}); return 'no error'; }
      catch (err) { return err.message; }
    """)
    assert "no artifact called" in got


def test_running_an_unbuilt_artifact_returns_a_reason_rather_than_throwing(a):
    got = js(a, "return await artifacts.run('monthly-review', {});")
    assert got["ok"] is False
    assert "not built yet" in got["reason"]


def test_a_builder_that_throws_becomes_a_reason_not_an_unhandled_rejection(a):
    got = js(a, """
      artifacts.register('numbers-today', () => { throw new Error('the printer is on fire'); });
      return await artifacts.run('numbers-today', {});
    """)
    assert got == {"ok": False, "reason": "the printer is on fire"}


# --- filenames --------------------------------------------------------------

def test_a_filename_carries_artifact_subject_and_date(a):
    got = js(a, """
      return artifacts.filename('episode-report', 's2e10', 'pdf',
                                new Date('2026-09-15T10:00:00Z'));
    """)
    assert got == "tsn-episode-report-s2e10-2026-09-15.pdf"


def test_the_date_in_a_filename_is_bangkok_not_utc(a):
    """23:30 UTC on the 14th is 06:30 on the 15th in Bangkok, and the file is
    named for the day the person making it is living in."""
    got = js(a, """
      return artifacts.filename('guest-card', 's2e9', 'png',
                                new Date('2026-09-14T23:30:00Z'));
    """)
    assert got.endswith("2026-09-15.png")


def test_a_subject_with_punctuation_or_thai_still_makes_a_safe_filename(a):
    got = js(a, """
      return [
        artifacts.filename('guest-card', 'Testy McFixture (Part 2)', 'pdf',
                           new Date('2026-09-15T10:00:00Z')),
        artifacts.filename('monthly-review', '', 'xlsx', new Date('2026-09-15T10:00:00Z')),
      ];
    """)
    assert got[0] == "tsn-guest-card-testy-mcfixture-part-2-2026-09-15.pdf"
    assert got[1] == "tsn-monthly-review-2026-09-15.xlsx"
    for name in got:
        assert not set(name) & set('\\/:*?"<>|')


def test_an_episode_slug_is_the_one_a_sponsor_would_recognise(a):
    got = js(a, "return artifacts.episodeSlug({ season: 2, number: '10' });")
    assert got == "s2e10"


# --- the source note --------------------------------------------------------

def test_every_artifact_can_say_where_its_numbers_came_from(a):
    note = js(a, """
      return await artifacts.sourceNote({
        platforms: 'all',
        from: new Date('2026-09-08T17:00:00Z'),
        to: new Date('2026-09-15T17:00:00Z'),
      });
    """)
    assert "YouTube, Instagram and TikTok" in note
    assert "9–15 Sept 2026" in note
    assert "Bangkok" in note
    assert "collector run" in note
    assert "Nothing on this page was typed by hand" in note


def test_a_lifetime_artifact_says_so_instead_of_naming_a_window(a):
    note = js(a, "return await artifacts.sourceNote({ lifetime: true });")
    assert "Lifetime totals, not a window." in note
    assert "Window:" not in note


def test_the_source_note_names_a_single_platform_when_that_is_the_scope(a):
    note = js(a, """
      return await artifacts.sourceNote({ platforms: 'tiktok',
        from: new Date('2026-09-08T17:00:00Z'), to: new Date('2026-09-15T17:00:00Z') });
    """)
    assert "Source: TikTok," in note


def test_a_missing_collector_run_is_admitted_rather_than_glossed(browser, stub,
                                                                 analytics_url, signin):
    stub.tables["collector_runs"] = []
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    pg.goto(analytics_url)
    pg.wait_for_selector('#view[data-state="ready"]')
    note = js(pg, "return await artifacts.sourceNote({ lifetime: true });")
    assert "may be stale" in note
    ctx.close()


# --- CSV --------------------------------------------------------------------

CSV_SETUP = """
const columns = [
  { key: 'title', name: 'Post' },
  { key: 'views', name: 'Views' },
  { key: 'rate', name: 'Engagement', raw: (r) => r.rate },
];
const rows = [
  { title: 'Plain', views: 1200, rate: 0.0625 },
  { title: 'Has, a comma', views: 900, rate: null },
  { title: 'Has "quotes"', views: 0, rate: 0.5 },
  { title: 'Has\\na newline', views: 15350, rate: 0.041 },
];
"""


def test_csv_quotes_the_three_things_an_instagram_caption_contains(a):
    text = js(a, CSV_SETUP + "return csv.toCsv(columns, rows, { bom: false });")
    parsed = list(csvmod.reader(io.StringIO(text)))
    assert parsed[0] == ["Post", "Views", "Engagement"]
    assert parsed[1] == ["Plain", "1200", "0.0625"]
    assert parsed[2][0] == "Has, a comma"
    assert parsed[3][0] == 'Has "quotes"'
    assert parsed[4][0] == "Has\na newline"


def test_csv_round_trips_through_a_real_csv_reader(a):
    text = js(a, CSV_SETUP + "return csv.toCsv(columns, rows, { bom: false });")
    parsed = list(csvmod.DictReader(io.StringIO(text)))
    assert len(parsed) == 4
    assert parsed[0]["Views"] == "1200"
    assert parsed[1]["Engagement"] == ""      # null is empty, not the string "null"


def test_csv_carries_a_byte_order_mark_so_excel_opens_thai_correctly(a):
    text = js(a, CSV_SETUP + "return csv.toCsv(columns, rows);")
    assert text.startswith("﻿")
    # utf-8-sig is how Python reads the same file back.
    decoded = text.encode("utf-8").decode("utf-8-sig")
    assert decoded.startswith("Post,Views,Engagement")


def test_csv_uses_crlf_because_that_is_what_excel_expects(a):
    text = js(a, CSV_SETUP + "return csv.toCsv(columns, rows, { bom: false });")
    assert "\r\n" in text
    assert text.endswith("\r\n")


def test_a_spreadsheet_gets_the_number_not_the_rounded_display_string(a):
    """"69.9K" is the wrong answer in a column somebody is going to sum."""
    text = js(a, """
      const columns = [{ key: 'views', name: 'Views',
                         format: (v) => '69.9K', raw: (r) => r.views }];
      return csv.toCsv(columns, [{ views: 69900 }], { bom: false });
    """)
    assert "69900" in text
    assert "69.9K" not in text


# --- XLSX -------------------------------------------------------------------

def sheetjs_available(page):
    return page.evaluate("""async () => {
      try {
        const csv = await import('/js/analytics/artifacts/csv.js');
        await csv.loadSheetJs();
        return true;
      } catch { return false; }
    }""")


@pytest.fixture
def scratch():
    """A writable directory. pytest's own tmp root is not writable on this box."""
    path = Path(__file__).parent / "stubs" / "vendor" / "scratch"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def xlsx(a):
    if not sheetjs_available(a):
        pytest.skip("SheetJS is not available: no network and nothing cached in "
                    "tests/analytics/stubs/vendor/. Run once online to cache it.")
    return a


def test_an_exported_workbook_opens_as_a_real_workbook(xlsx, scratch):
    """Written by the real SheetJS -- the stub serves the actual pinned library,
    verified against the same SRI hash the page uses -- and read back by
    openpyxl, which is what Sunny's Excel is standing in for."""
    openpyxl = pytest.importorskip(
        "openpyxl", reason="pip install -r tests/requirements.txt to run this one")
    data = xlsx.evaluate("""async () => {
      const csv = await import('/js/analytics/artifacts/csv.js');
      const XLSX = await csv.loadSheetJs();
      const book = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet(
        [['Post', 'Views'], ['Testy McFixture', 12000], ['Sample Kaur', 7700]]), 'Posts');
      XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet(
        [['Platform', 'Followers'], ['YouTube', 4080]]), 'Followers');
      const out = XLSX.write(book, { bookType: 'xlsx', type: 'array' });
      return Array.from(new Uint8Array(out));
    }""")
    path = scratch / "book.xlsx"
    path.write_bytes(bytes(data))

    book = openpyxl.load_workbook(path)
    assert book.sheetnames == ["Posts", "Followers"]
    sheet = book["Posts"]
    assert [c.value for c in sheet[1]] == ["Post", "Views"]
    assert sheet["B2"].value == 12000
    # A number, not a string that looks like one: a sheet of strings cannot be
    # summed, which is the only reason anybody asked for XLSX.
    assert isinstance(sheet["B2"].value, int)


def test_a_sheet_name_is_trimmed_to_what_excel_will_accept(a):
    got = js(a, """
      return [
        csv.sheetName('Posts'),
        csv.sheetName('A name that is far too long for Excel to accept at all'),
        csv.sheetName('Bad: name/with\\\\chars?[]*'),
        csv.sheetName(''),
      ];
    """)
    assert got[0] == "Posts"
    assert len(got[1]) <= 31
    assert not set(got[2]) & set(':\\/?*[]')
    assert got[3] == "Sheet1"


def test_a_missing_spreadsheet_library_says_csv_still_works(browser, stub, analytics_url,
                                                            signin):
    """CSV is written by hand and needs nothing. Only XLSX needs the network,
    and the message should say which half is still available."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    stub.install(pg)
    pg.route("**/xlsx.full.min.js", lambda r: r.abort())
    signin(pg)
    pg.goto(analytics_url)
    pg.wait_for_selector('#view[data-state="ready"]')
    got = pg.evaluate("""async () => {
      const csv = await import('/js/analytics/artifacts/csv.js');
      try { await csv.loadSheetJs(); return 'loaded'; } catch (err) { return err.message; }
    }""")
    assert "CSV still works" in got
    ctx.close()


# --- the pages themselves ---------------------------------------------------

def open_artifact(browser, stub, base_url, signin, page_name, query=""):
    ctx = browser.new_context(viewport={"width": 1240, "height": 1600})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text)
          if m.type == "error" and "Failed to load resource" not in m.text else None)

    def watch(response):
        """A failed IMAGE is expected: YouTube genuinely 404s maxresdefault for a
        video that never had one, and the still chain falls back. A failed
        script or stylesheet is not."""
        if response.status >= 400 and response.request.resource_type != "image":
            errors.append(f"{response.status} {response.url}")

    pg.on("response", watch)
    stub.install(pg)
    signin(pg)
    pg.goto(f"{base_url}/analytics/artifacts/{page_name}{query}")
    pg.wait_for_selector("#sheet section, #sheet .problem, #status.problem")
    return pg, ctx, errors


@pytest.fixture
def report(browser, stub, base_url, signin):
    pg, ctx, errors = open_artifact(browser, stub, base_url, signin,
                                    "episode-report.html", "?episode=1")
    pg.wait_for_selector("#sheet footer.colophon")
    yield pg, errors
    ctx.close()


def test_the_episode_report_draws_from_the_fixtures_without_throwing(report):
    pg, errors = report
    assert errors == []
    assert pg.locator("#sheet img").count() == 1, "the still slot is empty"
    assert pg.locator("#sheet section").count() >= 4


def test_the_report_leads_with_the_guest_and_the_date(report):
    pg, _ = report
    assert pg.inner_text("#sheet h1").strip() == "Testy McFixture"
    text = pg.inner_text("#sheet")
    assert "Founder & CEO, Example Co" in text
    # Uppercased in CSS; the markup says "Season 2 · Episode 10".
    assert "SEASON 2" in text.upper() and "EPISODE 10" in text.upper()
    assert "Published 20 Aug 2026, Bangkok" in text


def test_the_report_gives_lifetime_views_and_seven_and_thirty_day_views(report):
    pg, _ = report
    labels = pg.locator("#sheet .figs .fig .k").all_text_contents()
    assert labels == ["Views, lifetime", "At 7 days", "At 30 days"]
    assert "12,000" in pg.locator("#sheet .figs").inner_text()


def test_a_figure_the_archive_cannot_reach_says_not_measured_not_zero(report):
    """The snapshot archive starts 14 September 2026; this episode aired in
    August. A 0 there would tell a sponsor the episode did nothing in week one."""
    pg, _ = report
    text = pg.locator("#sheet .figs").inner_text()
    assert "not measured" in text
    assert "No snapshot from the episode" in text


def test_the_report_lists_every_clip_with_its_platform_and_views(report):
    pg, _ = report
    rows = pg.locator("#sheet table").first.locator("tbody tr")
    assert rows.count() == 3                     # a Short, a Reel and a TikTok
    text = pg.inner_text("#sheet")
    assert "YouTube" in text and "Instagram" in text and "TikTok" in text
    # Sorted by views, biggest first: the Reel at 18,000.
    assert "18,000" in rows.first.inner_text()


def test_the_report_says_what_reach_means_and_what_a_dash_means(report):
    pg, _ = report
    assert "Reach is reported by Instagram only" in pg.inner_text("#sheet")


def test_the_total_across_all_cuts_is_on_the_page_with_its_caveat(report):
    """The sentence a sponsor will ask about, on the page rather than in a
    covering email that gets deleted."""
    pg, _ = report
    text = pg.inner_text("#sheet")
    assert "47,000" in text
    assert "SUM OF VIEW COUNTS" in text
    assert "not a count of people" in text


def test_the_split_across_platforms_is_written_as_numbers_not_only_a_bar(report):
    """A monochrome print turns three saturated swatches into three greys."""
    pg, _ = report
    legend = pg.locator("#sheet .band-legend").inner_text()
    assert "%" in legend
    assert "12,000" in legend
    assert pg.locator("#sheet .band i").count() >= 3


def test_the_audience_block_says_it_is_the_channel_not_the_episode(report):
    """The single most likely way this page could mislead a sponsor."""
    pg, _ = report
    text = pg.inner_text("#sheet")
    assert "for the CHANNEL, not per episode" in text
    assert "Window: 18 Jun" in text


def test_the_report_carries_its_source_note(report):
    pg, _ = report
    note = pg.inner_text("#sheet footer.colophon")
    assert "YouTube, Instagram and TikTok" in note
    assert "collector run" in note
    assert "snapshot archive, which begins 14 September 2026" in note


def test_the_pdf_filename_is_offered_and_is_the_document_title(report):
    pg, _ = report
    assert "tsn-episode-report-s2e10-" in pg.inner_text("#toolbar")
    assert pg.title().startswith("tsn-episode-report-s2e10-")


def test_a_link_without_an_episode_says_so_rather_than_drawing_a_blank_page(
        browser, stub, base_url, signin):
    pg, ctx, _ = open_artifact(browser, stub, base_url, signin, "episode-report.html")
    assert "No episode was named in the link" in pg.inner_text("#sheet")
    ctx.close()


def test_an_episode_that_does_not_exist_says_which_one(browser, stub, base_url, signin):
    pg, ctx, _ = open_artifact(browser, stub, base_url, signin,
                               "episode-report.html", "?episode=999")
    assert "There is no episode 999" in pg.inner_text("#sheet")
    ctx.close()


def test_an_artifact_page_opened_without_a_session_says_to_sign_in(browser, stub,
                                                                   base_url):
    ctx = browser.new_context(viewport={"width": 1240, "height": 1600})
    pg = ctx.new_page()
    stub.install(pg)
    pg.goto(f"{base_url}/analytics/artifacts/episode-report.html?episode=1")
    pg.wait_for_selector("#status.problem")
    assert "Not signed in" in pg.inner_text("#status")
    ctx.close()


# --- the print stylesheet ---------------------------------------------------

def test_the_artifact_page_is_bodoni_where_the_dashboard_is_not(report):
    pg, _ = report
    family = pg.evaluate("getComputedStyle(document.querySelector('#sheet h1')).fontFamily")
    assert "Bodoni Moda" in family


def test_the_print_stylesheet_applies_at_media_print(report):
    """Checked through the real media emulation, not by reading the CSS."""
    pg, _ = report
    before = pg.evaluate(
        "getComputedStyle(document.getElementById('toolbar')).display")
    pg.emulate_media(media="print")
    after = pg.evaluate(
        "getComputedStyle(document.getElementById('toolbar')).display")
    sheet = pg.evaluate("getComputedStyle(document.getElementById('sheet')).boxShadow")
    pg.emulate_media(media="screen")
    assert before != "none"
    assert after == "none", "the toolbar would print on the sponsor's copy"
    assert sheet == "none", "the on-screen page shadow would print as a grey band"


def test_nothing_on_the_report_is_allowed_to_break_across_a_page(report):
    pg, _ = report
    pg.emulate_media(media="print")
    breaks = pg.evaluate("""() => [...document.querySelectorAll('#sheet table, #sheet .card')]
        .map((e) => getComputedStyle(e).breakInside)""")
    pg.emulate_media(media="screen")
    assert breaks
    assert all(b == "avoid" for b in breaks)


def test_the_printed_page_is_ink_on_paper_not_cream_on_black(report):
    """#0D0706 across A4 is four millilitres of ink and a sponsor who cannot
    read it on the train."""
    pg, _ = report
    pg.emulate_media(media="print")
    colours = pg.evaluate("""() => {
      const s = getComputedStyle(document.body);
      return { bg: s.backgroundColor, fg: s.color };
    }""")
    pg.emulate_media(media="screen")
    assert colours["bg"] == "rgb(255, 255, 255)"
    assert colours["fg"] == "rgb(26, 20, 17)"


def test_an_external_link_prints_its_url(report):
    """A PDF that says "watch the episode" with no URL is a dead end on paper."""
    css = (SITE / "css" / "artifacts.css").read_text(encoding="utf-8")
    assert 'a[href^="http"]::after' in css
    assert "attr(href)" in css


# --- the UI -----------------------------------------------------------------

def test_the_recipient_and_the_reason_are_on_screen_next_to_the_button(dashboard):
    """Not a tooltip. The difference between this and a generic export menu is
    exactly that sentence, and it has to be visible."""
    dashboard.wait_for_selector("#view .a-artifacts")
    rows = dashboard.locator("#view .a-artifact").evaluate_all("""els => els.map((e) => ({
      button: e.querySelector('button').textContent,
      recipient: e.querySelector('.a-recipient')?.textContent,
      why: e.querySelector('.a-why')?.textContent,
    }))""")
    assert rows
    for row in rows:
        assert row["recipient"].startswith("to ")
        assert len(row["why"]) > 20


def test_the_overview_offers_the_two_artifacts_that_are_not_row_scoped(dashboard):
    dashboard.wait_for_selector("#view .a-artifacts")
    ids = dashboard.locator("#view .a-artifacts button").evaluate_all(
        "els => els.map(e => e.dataset.artifact)")
    assert ids == ["monthly-review", "numbers-today"]


def test_the_posts_tab_offers_its_spreadsheet_below_the_table(dashboard):
    dashboard.click("#tab-posts")
    dashboard.wait_for_selector('#view[data-tab="posts"][data-state="ready"]')
    ids = dashboard.locator("#view .a-artifacts button").evaluate_all(
        "els => els.map(e => e.dataset.artifact)")
    assert ids == ["posts-table"]
    order = dashboard.evaluate("""() => {
      const table = document.querySelector('#view table.a-sortable');
      const bar = document.querySelector('#view .a-artifacts');
      return table.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING ? 'after' : 'before';
    }""")
    assert order == "after"


GENERIC = {"export", "export this view", "download", "download csv",
           "download xlsx", "save as", "export data"}


def test_no_button_anywhere_is_a_generic_export(dashboard):
    """The spec's rule, checked against the buttons rather than the prose --
    the prose explains the rule and therefore quotes it."""
    for tab in ("overview", "growth", "posts", "episodes", "audience", "health"):
        dashboard.click(f"#tab-{tab}")
        dashboard.wait_for_selector(f'#view[data-tab="{tab}"][data-state="ready"]')
        if tab == "episodes":
            dashboard.locator("#view button.a-expand").first.click()
            dashboard.wait_for_selector("#view .a-artifacts")
        labels = dashboard.locator("#view button").evaluate_all(
            "els => els.map(e => e.textContent.trim().toLowerCase())")
        assert not (set(labels) & GENERIC), (tab, labels)
        # And every artifact button that does exist names who it is for.
        orphans = dashboard.locator("#view .a-artifacts button").evaluate_all(
            """els => els.filter((e) =>
                 !e.closest('.a-artifact')?.querySelector('.a-recipient'))
               .map((e) => e.textContent)""")
        assert orphans == [], tab
