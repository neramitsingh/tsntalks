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
