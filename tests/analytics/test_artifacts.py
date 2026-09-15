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


def test_all_five_artifacts_are_built(a):
    """The definition of done for the five. Until Task 17 the unbuilt ones
    returned "not built yet"; none of them do now."""
    built = js(a, "return artifacts.ARTIFACTS.map((x) => [x.id, artifacts.has(x.id)]);")
    assert built == [[id_, True] for id_ in THE_FIVE]


def test_an_unknown_artifact_id_is_refused_by_name(a):
    got = js(a, "return await artifacts.run('nope', {});")
    assert got == {"ok": False, "reason": 'No artifact called "nope".'}


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
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
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
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
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
    ctx = browser.new_context(viewport={"width": 1240, "height": 1600},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
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
    # text_content, not inner_text: artifact headings are set in the show's
    # capitals by CSS (Antonio, as on the site); the content is the name.
    assert pg.text_content("#sheet h1").strip() == "Testy McFixture"
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

def test_the_artifact_page_is_set_in_the_show_type_where_the_dashboard_is_not(report):
    """The artifacts are the brand leaving the building, so they carry the
    show's own display face — Antonio since 15 Sep 2026 (it was Bodoni Moda
    under the first direction, which the worker built against)."""
    pg, _ = report
    family = pg.evaluate("getComputedStyle(document.querySelector('#sheet h1')).fontFamily")
    assert "Antonio" in family
    assert "Bodoni" not in family


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


# --- the posts table, downloaded for real -----------------------------------

def export_posts(dashboard, scratch, fmt, *, search=None, sort=None):
    """Drive the Posts tab and click its export, catching the real download."""
    dashboard.click("#tab-posts")
    dashboard.wait_for_selector('#view[data-tab="posts"][data-state="ready"]')
    if sort:
        dashboard.click(f'#view thead th button.a-sort:has-text("{sort}")')
    if search is not None:
        dashboard.fill("#posts-search", search)
        dashboard.wait_for_function(
            "document.getElementById('posts-count').textContent.includes(' of ')")

    with dashboard.expect_download() as caught:
        dashboard.click(f'#view .a-artifacts button[data-format="{fmt}"]')
    download = caught.value
    path = scratch / download.suggested_filename
    download.save_as(path)
    return download.suggested_filename, path


def test_the_csv_is_named_for_the_artifact_its_scope_and_the_date(dashboard, scratch):
    name, _ = export_posts(dashboard, scratch, "csv")
    assert name.startswith("tsn-posts-table-all-platforms-")
    assert name.endswith(".csv")


def test_a_filtered_export_says_so_in_its_filename(dashboard, scratch):
    name, _ = export_posts(dashboard, scratch, "csv", search="Placeholder")
    assert "filtered" in name


def test_the_csv_is_the_rows_that_were_on_screen_in_the_order_they_were_in(
        dashboard, scratch):
    """Same rows, same order. A fresh unsorted query would be technically the
    same data and practically the wrong file."""
    _, path = export_posts(dashboard, scratch, "csv", sort="Likes")
    on_screen = dashboard.locator(
        "#view table.a-sortable tbody tr:not(.a-expanded)").evaluate_all(
        "els => els.map(e => e.dataset.postId)")

    rows = list(csvmod.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    assert [r["Post ID"] for r in rows] == on_screen


def test_a_filtered_csv_carries_only_the_filtered_rows(dashboard, scratch):
    _, path = export_posts(dashboard, scratch, "csv", search="Placeholder")
    rows = list(csvmod.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    assert len(rows) == 3
    assert all("Placeholder" in r["Title"] or "FIXCLIP02" in r["Post ID"] for r in rows)


def test_the_csv_carries_the_full_title_not_the_clipped_one(dashboard, scratch):
    _, path = export_posts(dashboard, scratch, "csv")
    rows = list(csvmod.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    titles = {r["Post ID"]: r["Title"] for r in rows}
    assert titles["yt:FIXTUREVID01"] == \
        "TSN Talks S2 E10: Testy McFixture, Founder & CEO, Example Co"
    assert "…" not in "".join(titles.values())


def test_the_csv_carries_raw_numbers_not_the_screen_s_rounding(dashboard, scratch):
    _, path = export_posts(dashboard, scratch, "csv")
    rows = {r["Post ID"]: r for r in
            csvmod.DictReader(path.read_text(encoding="utf-8-sig").splitlines())}
    assert rows["ig:FIXCLIP01"]["Views"] == "18000"
    assert rows["ig:FIXCLIP01"]["Engagement rate (fraction)"] == "0.088333"
    assert "Engagement rate (fraction)" in rows["ig:FIXCLIP01"]


def test_a_reach_that_is_not_reported_is_an_empty_cell_not_a_zero(dashboard, scratch):
    _, path = export_posts(dashboard, scratch, "csv")
    rows = {r["Post ID"]: r for r in
            csvmod.DictReader(path.read_text(encoding="utf-8-sig").splitlines())}
    assert rows["yt:FIXTUREVID01"]["Reach"] == ""
    assert rows["ig:FIXCLIP01"]["Reach"] == "11160"


def test_the_workbook_has_the_rows_and_a_sheet_saying_where_they_came_from(
        xlsx, scratch):
    openpyxl = pytest.importorskip(
        "openpyxl", reason="pip install -r tests/requirements.txt to run this one")
    name, path = export_posts(xlsx, scratch, "xlsx", search="Placeholder")
    assert name.endswith(".xlsx")

    book = openpyxl.load_workbook(path)
    assert book.sheetnames == ["Posts", "About"]

    posts = book["Posts"]
    headers = [c.value for c in posts[1]]
    assert headers[:4] == ["Platform", "Post ID", "Published", "Title"]
    assert posts.max_row == 4                      # three rows plus the header

    # Numbers are numbers, so the column can be summed. That is the only reason
    # anybody asked for XLSX rather than CSV.
    views = headers.index("Views") + 1
    assert all(isinstance(posts.cell(row=r, column=views).value, int)
               for r in range(2, posts.max_row + 1))

    about = {r[0].value: r[1].value for r in book["About"].iter_rows(min_row=2)}
    assert about["Title filter"] == "Placeholder"
    assert about["Rows"] == 3
    assert "descending" in about["Sorted by"]
    assert "collector run" in about["Source"]


def test_the_workbook_keeps_dates_as_dates(xlsx, scratch):
    openpyxl = pytest.importorskip(
        "openpyxl", reason="pip install -r tests/requirements.txt to run this one")
    import datetime as dt
    _, path = export_posts(xlsx, scratch, "xlsx")
    book = openpyxl.load_workbook(path)
    posts = book["Posts"]
    column = [c.value for c in posts[1]].index("Published") + 1
    assert isinstance(posts.cell(row=2, column=column).value, dt.datetime)


def test_exporting_an_empty_table_says_what_to_do_about_it(dashboard):
    dashboard.click("#tab-posts")
    dashboard.wait_for_selector('#view[data-tab="posts"][data-state="ready"]')
    dashboard.fill("#posts-search", "zzzz-no-such-post")
    dashboard.wait_for_selector("#view .a-empty")
    dashboard.click('#view .a-artifacts button[data-format="csv"]')
    dashboard.wait_for_selector("#view .a-artifact .a-error")
    message = dashboard.inner_text("#view .a-artifact .a-error")
    assert "no rows to export" in message
    assert "clear the filter" in message


# --- the monthly review -----------------------------------------------------

@pytest.fixture
def review(browser, stub, base_url, signin, halve_previous):
    """September against August, with August made half the size so the two
    months are actually different numbers."""
    # Mid-August: September's window starts 2026-08-31T17:00Z (Bangkok
    # midnight on the 1st) and August's starts a month earlier, so this cutoff
    # falls between the two and only August is halved.
    stub.rpc_hook = halve_previous("2026-08-15")
    pg, ctx, errors = open_artifact(browser, stub, base_url, signin,
                                    "monthly-review.html", "?month=2026-09")
    pg.wait_for_selector("#sheet footer.colophon")
    yield pg, errors
    ctx.close()


def test_the_monthly_review_draws_without_throwing(review):
    pg, errors = review
    assert errors == []
    assert pg.text_content("#sheet h1").strip() == "September 2026"
    # The eyebrow is uppercased in CSS; the markup says "Against August 2026".
    assert "AGAINST AUGUST 2026" in pg.inner_text("#sheet").upper()


def test_the_review_leads_with_the_four_figures_and_their_change(review):
    pg, _ = review
    labels = pg.locator("#sheet .figs .fig .k").all_text_contents()
    assert labels == ["Views", "Net followers", "Posts published", "Engagement rate"]
    subs = pg.locator("#sheet .figs .fig .sub").all_text_contents()
    # August was halved, so every figure roughly doubled.
    assert all("August 2026" in s for s in subs)
    assert any("+100.0%" in s for s in subs)


def test_a_change_on_paper_carries_an_arrow_and_a_sign_not_a_colour(review):
    """There is no hover on paper, and a monochrome print has no colour worth
    relying on."""
    pg, _ = review
    subs = " ".join(pg.locator("#sheet .figs .fig .sub").all_text_contents())
    assert "▲" in subs or "▼" in subs
    assert "%" in subs


def test_the_three_platform_comparisons_are_charts_with_their_tables(review):
    pg, _ = review
    headings = pg.locator("#sheet h2").all_text_contents()
    assert headings[:3] == ["Views by platform", "Net followers by platform",
                            "Posts published"]
    assert pg.locator("#sheet svg.a-chart").count() == 3
    assert pg.locator("#sheet details.a-twin").count() == 3


def test_every_table_twin_is_open_on_paper(review):
    """A collapsed <details> in a PDF is a table nobody can reach, and "every
    chart has a table" is the contract."""
    pg, _ = review
    assert pg.locator("#sheet details.a-twin").count() == \
        pg.locator("#sheet details.a-twin[open]").count()


def test_a_comparison_table_names_both_months_and_the_change(review):
    pg, _ = review
    headers = pg.locator("#sheet details.a-twin").first.locator("thead th").all_text_contents()
    assert headers == ["Platform", "September 2026", "August 2026", "Change"]


def test_the_follower_panel_says_it_is_a_net_change_not_a_count(review):
    """A follower count printed beside a month name reads as a monthly figure
    when it is a lifetime one."""
    pg, _ = review
    text = pg.inner_text("#sheet")
    assert "Gained minus lost inside the month" in text
    assert "Not the follower count" in text


def test_the_review_lists_the_five_posts_that_carried_the_month(review):
    pg, _ = review
    section = pg.locator("#sheet section", has_text="The five posts that carried")
    rows = section.locator("tbody tr")
    assert rows.count() == 5
    gained = section.locator("tbody tr td:nth-child(4)").all_inner_texts()
    numbers = [int(g.replace(",", "")) for g in gained]
    assert numbers == sorted(numbers, reverse=True)


def test_the_audience_shift_is_in_points_and_says_it_is_the_channel(review):
    pg, _ = review
    section = pg.locator("#sheet section", has_text="Where the audience is")
    headers = section.locator("thead th").all_text_contents()
    assert headers == ["Country", "Share", "Share before", "Shift", "Views"]
    assert "pp" in section.inner_text()
    assert "rolling 90-day window for the CHANNEL" in pg.inner_text("#sheet footer.colophon")


def test_the_review_carries_its_source_note_and_filename(review):
    pg, _ = review
    assert "collector run" in pg.inner_text("#sheet footer.colophon")
    assert pg.title() == "tsn-monthly-review-2026-09-" + \
        __import__("datetime").datetime.now().astimezone().strftime("%Y-%m-%d")


def test_a_month_that_has_not_happened_is_refused_by_name(browser, stub, base_url, signin):
    pg, ctx, _ = open_artifact(browser, stub, base_url, signin,
                               "monthly-review.html", "?month=2099-01")
    assert "has not happened yet" in pg.inner_text("#sheet")
    ctx.close()


def test_a_month_that_is_not_a_month_says_so(browser, stub, base_url, signin):
    pg, ctx, _ = open_artifact(browser, stub, base_url, signin,
                               "monthly-review.html", "?month=last-tuesday")
    assert "is not a month" in pg.inner_text("#sheet")
    ctx.close()


def test_the_workbook_carries_the_tables_under_the_charts(dashboard, scratch, stub):
    openpyxl = pytest.importorskip(
        "openpyxl", reason="pip install -r tests/requirements.txt to run this one")
    if not sheetjs_available(dashboard):
        pytest.skip("SheetJS is not available offline")

    with dashboard.expect_download() as caught:
        dashboard.click('#view .a-artifacts button[data-artifact="monthly-review"]'
                        '[data-format="xlsx"]')
    download = caught.value
    path = scratch / download.suggested_filename
    download.save_as(path)

    assert download.suggested_filename.startswith("tsn-monthly-review-")
    book = openpyxl.load_workbook(path)
    assert book.sheetnames == ["Summary", "Views", "Followers", "Posts published",
                               "Top posts", "Audience", "About"]
    views = book["Views"]
    assert [c.value for c in views[1]][0] == "Platform"
    assert views.max_row == 4                      # three platforms plus the header

    about = {}
    for row in book["About"].iter_rows(min_row=2):
        about.setdefault(row[0].value, []).append(row[1].value)
    assert any("net change" in v.lower() for v in about["Note"])
    assert "collector run" in about["Source"][0]


def test_the_pdf_and_the_workbook_agree(dashboard, scratch, stub, browser, base_url,
                                        signin):
    """Both come out of monthly-review-data.js, so printing the review and
    opening the spreadsheet beside it cannot show two answers."""
    openpyxl = pytest.importorskip(
        "openpyxl", reason="pip install -r tests/requirements.txt to run this one")
    if not sheetjs_available(dashboard):
        pytest.skip("SheetJS is not available offline")

    with dashboard.expect_download() as caught:
        dashboard.click('#view .a-artifacts button[data-artifact="monthly-review"]'
                        '[data-format="xlsx"]')
    path = scratch / caught.value.suggested_filename
    caught.value.save_as(path)
    sheet = openpyxl.load_workbook(path)["Views"]
    from_workbook = {sheet.cell(row=r, column=1).value: sheet.cell(row=r, column=2).value
                     for r in range(2, sheet.max_row + 1)}

    month = caught.value.suggested_filename.split("tsn-monthly-review-")[1][:7]
    pg, ctx, _ = open_artifact(browser, stub, base_url, signin,
                               "monthly-review.html", f"?month={month}")
    pg.wait_for_selector("#sheet footer.colophon")
    from_page = pg.locator("#sheet details.a-twin").first.evaluate(
        """(el) => Object.fromEntries([...el.querySelectorAll('tbody tr')].map(
             (tr) => [tr.children[0].textContent,
                      Number(tr.children[1].textContent.replace(/,/g, ''))]))""")
    ctx.close()

    assert from_page == from_workbook


# --- the guest card ---------------------------------------------------------

@pytest.fixture
def card(browser, stub, base_url, signin):
    pg, ctx, errors = open_artifact(browser, stub, base_url, signin,
                                    "guest-card.html", "?episode=1")
    pg.wait_for_selector("#sheet footer.colophon")
    yield pg, errors
    ctx.close()


def test_the_guest_card_draws_without_throwing(card):
    pg, errors = card
    assert errors == []
    assert pg.text_content("#sheet h1").strip() == "Testy McFixture"


def test_the_card_says_watched_n_times_and_never_n_people(card):
    """The spec's wording is "reached N people". The number is a sum of view
    counts across the cuts, so "people" would be a claim the data does not make
    -- on the one artifact a guest is most likely to screenshot and post."""
    pg, _ = card
    text = pg.inner_text("#sheet .card-square")
    assert "47,000" in text
    assert "times, across the episode and every clip" in text
    assert "people" not in text.lower()


def test_the_colophon_explains_what_the_number_is_not(card):
    pg, _ = card
    note = pg.inner_text("#sheet footer.colophon")
    assert "not a count of people" in note


def test_the_card_carries_the_platform_split_with_its_numbers(card):
    pg, _ = card
    legend = pg.locator("#sheet .band-legend").inner_text()
    for platform in ("YouTube", "Instagram", "TikTok"):
        assert platform in legend
    assert "18,000" in legend and "%" in legend


def test_the_card_names_the_clip_that_travelled_furthest(card):
    pg, _ = card
    text = pg.inner_text("#sheet .clip-row")
    assert "Travelled furthest" in text or "TRAVELLED FURTHEST" in text.upper()
    assert "Instagram" in text.title() or "INSTAGRAM" in text.upper()
    assert "18,000" in text


def test_the_card_carries_a_share_link_to_the_episode(card):
    pg, _ = card
    link = pg.locator("#sheet .card-square a").last
    assert link.get_attribute("href") == \
        "https://www.youtube.com/watch?v=FIXTUREVID01"


def test_an_episode_with_no_clips_still_makes_a_card(browser, stub, base_url, signin):
    stub.rpc["post_deltas"] = [r for r in stub.rpc["post_deltas"]
                               if r["post_id"] == "yt:FIXTUREVID01"]
    pg, ctx, errors = open_artifact(browser, stub, base_url, signin,
                                    "guest-card.html", "?episode=1")
    pg.wait_for_selector("#sheet footer.colophon")
    assert errors == []
    assert "No clips have been matched" in pg.inner_text("#sheet")
    ctx.close()


# --- the PNG ----------------------------------------------------------------

def png_size(data):
    """Width and height out of the PNG's IHDR chunk."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    assert data[12:16] == b"IHDR"
    return (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"))


def test_the_png_comes_out_at_the_declared_dimensions(card, scratch):
    """1080 square: LINE's share image and an Instagram feed post are both that,
    so one file serves both."""
    pg, _ = card
    with pg.expect_download() as caught:
        pg.click("[data-png]")
    path = scratch / caught.value.suggested_filename
    caught.value.save_as(path)

    assert caught.value.suggested_filename == \
        "tsn-guest-card-s2e10-" + _today() + ".png"
    assert png_size(path.read_bytes()) == (1080, 1080)


def test_the_png_button_states_the_size_it_will_produce(card):
    pg, _ = card
    assert "1080×1080" in pg.inner_text("[data-png]")


def test_the_dashboard_png_button_produces_the_file_without_a_second_click(
        browser, stub, base_url, signin, scratch):
    """The dashboard's PNG button opens the card's own tab, because the canvas
    needs that page's fonts. It must not then ask for another click."""
    ctx = browser.new_context(viewport={"width": 1240, "height": 1600},
                              accept_downloads=True)
    ctx.set_default_timeout(90_000)
    pg = ctx.new_page()
    stub.install(pg)
    signin(pg)
    with pg.expect_download() as caught:
        pg.goto(f"{base_url}/analytics/artifacts/guest-card.html"
                "?episode=1&download=png")
    assert caught.value.suggested_filename.endswith(".png")
    ctx.close()


def test_the_png_is_the_brand_dark_where_the_pdf_is_ink_on_paper(card, scratch):
    """PRODUCT.md puts cream grounds on the anti-reference list for screen
    surfaces, and a PDF on a dark ground is unreadable on a train. Same numbers,
    the ground each medium actually wants."""
    pg, _ = card
    corner = pg.evaluate("""async () => {
      const png = await import('/js/analytics/artifacts/png.js');
      const blob = await png.renderGuestCard({
        episode: { season: 2, number: '10', guest: 'Testy McFixture', role: 'Founder',
                   totalReach: 47000, ytViews: 12000,
                   clipViews: { youtube: 3000, instagram: 18000, tiktok: 14000 } },
        shareUrl: 'https://example.test/x',
      });
      const bitmap = await createImageBitmap(blob);
      const canvas = new OffscreenCanvas(1, 1);
      const ctx = canvas.getContext('2d');
      ctx.drawImage(bitmap, -540, -900, bitmap.width, bitmap.height);
      const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
      return [r, g, b];
    }""")
    # --bg is #0D0706.
    assert corner == [13, 7, 6]


def test_a_very_long_guest_name_is_shrunk_rather_than_clipped(card):
    """A card that clips the guest's own name is not a card you send the guest."""
    pg, _ = card
    sizes = pg.evaluate("""async () => {
      const png = await import('/js/analytics/artifacts/png.js');
      const out = [];
      for (const guest of ['Sam Lee',
                           'Mr. Deepak Sajnani of the Thai-Sindhi Association']) {
        const blob = await png.renderGuestCard({
          episode: { season: 2, number: '10', guest, role: '', totalReach: 47000,
                     ytViews: 12000,
                     clipViews: { youtube: 0, instagram: 18000, tiktok: 14000 } },
          shareUrl: 'https://example.test/x',
        });
        out.push(blob.size);
      }
      return out;
    }""")
    assert all(size > 0 for size in sizes)


def _today():
    import datetime as dt
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).strftime("%Y-%m-%d")


# --- the numbers, frozen at a date ------------------------------------------

@pytest.fixture
def frozen(browser, stub, base_url, signin):
    pg, ctx, errors = open_artifact(browser, stub, base_url, signin,
                                    "numbers-today.html", "?date=2026-09-15")
    pg.wait_for_selector("#sheet footer.colophon")
    yield pg, errors
    ctx.close()


def test_the_frozen_page_draws_without_throwing(frozen):
    pg, errors = frozen
    assert errors == []
    assert pg.locator("#sheet section").count() >= 5


def test_it_is_laid_out_like_the_public_live_page(frozen):
    """One number, the platform split, when the hits happened, who is watching,
    what is playing. The same order the site uses."""
    pg, _ = frozen
    assert pg.locator("#sheet h2").all_text_contents() == [
        "By platform", "When the hits happened", "Who is watching", "Playing now"]
    assert pg.locator("#sheet .hero-number").count() == 1
    assert pg.locator("#sheet .band").count() == 1


def test_a_lifetime_total_sits_next_to_a_ninety_day_momentum_figure(frozen):
    """PRODUCT.md principle 3. A cumulative-only total with no window is on the
    anti-reference list."""
    pg, _ = frozen
    labels = pg.locator("#sheet .figs .fig .k").all_text_contents()
    assert labels == ["Views, all time", "Views, last 90 days", "Followers", "Posts"]
    text = pg.locator("#sheet .card").inner_text()
    assert "156,100" in text          # lifetime, summed from post_deltas
    assert "69,900" in text           # the last 90 days


def test_the_hero_picks_its_own_unit_rather_than_always_saying_millions(frozen):
    """The live page hard-codes M, which reads as "0.16M" for a season that has
    not got there yet -- and a deck assembled early is exactly when that
    happens."""
    pg, _ = frozen
    assert pg.inner_text("#sheet .hero-number").strip() == "156K"


def test_every_figure_says_the_date_it_is_as_at(frozen):
    """A live page screenshotted in October and captioned "September" is the
    hand-typed claim this project exists to replace."""
    pg, _ = frozen
    # The eyebrow is uppercased in CSS.
    assert "AS AT 15 SEPT 2026" in pg.inner_text("#sheet").upper()
    note = pg.inner_text("#sheet footer.colophon")
    assert "as at 15 Sept 2026" in note
    assert "It is not a live page and it does not update" in note


def test_the_reporting_delay_is_stated(frozen):
    pg, _ = frozen
    assert "delay of up to 48 hours" in pg.inner_text("#sheet footer.colophon")


def test_the_platform_table_carries_share_momentum_followers_and_best_post(frozen):
    pg, _ = frozen
    section = pg.locator("#sheet section", has_text="By platform")
    headers = section.locator("thead th").all_text_contents()
    assert headers == ["Platform", "Views", "Share", "Last 90 days", "Followers",
                       "Posts", "Best post"]
    shares = section.locator("tbody td:nth-child(3)").all_inner_texts()
    assert sum(int(s.rstrip("%")) for s in shares) == pytest.approx(100, abs=1)


def test_the_months_are_counted_by_publication_not_by_viewing(frozen):
    """The shape the live page uses: a clip from November that is still being
    watched counts in November."""
    pg, _ = frozen
    section = pg.locator("#sheet section", has_text="When the hits happened")
    assert "the month the post was published" in section.inner_text()
    totals = section.locator("tbody td:nth-child(5)").all_inner_texts()
    assert sum(int(t.replace(",", "")) for t in totals) == 156100


def test_the_audience_window_is_youtube_s_and_says_so(frozen):
    pg, _ = frozen
    section = pg.locator("#sheet section", has_text="Who is watching")
    text = section.inner_text()
    assert "This window is YouTube’s, not the date above" in text
    assert "18 Jun" in text


def test_a_date_in_the_future_is_clamped_to_now_rather_than_invented(browser, stub,
                                                                     base_url, signin):
    pg, ctx, errors = open_artifact(browser, stub, base_url, signin,
                                    "numbers-today.html", "?date=2099-01-01")
    pg.wait_for_selector("#sheet footer.colophon")
    assert errors == []
    assert "2099" not in pg.inner_text("#sheet")
    ctx.close()


def test_a_date_that_is_not_a_date_says_what_to_use(browser, stub, base_url, signin):
    pg, ctx, _ = open_artifact(browser, stub, base_url, signin,
                               "numbers-today.html", "?date=yesterday")
    assert "Use YYYY-MM-DD" in pg.inner_text("#sheet")
    ctx.close()


def test_the_filename_carries_the_date_it_was_frozen_at(frozen):
    pg, _ = frozen
    assert pg.title().startswith("tsn-numbers-2026-09-15-")


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
        "els => els.map(e => [e.dataset.artifact, e.dataset.format])")
    # One button per format, not a dropdown that has to be opened to discover
    # that XLSX exists.
    assert ids == [["monthly-review", "pdf"], ["monthly-review", "xlsx"],
                   ["numbers-today", "pdf"]]


def test_the_posts_tab_offers_its_spreadsheet_below_the_table(dashboard):
    dashboard.click("#tab-posts")
    dashboard.wait_for_selector('#view[data-tab="posts"][data-state="ready"]')
    ids = dashboard.locator("#view .a-artifacts button").evaluate_all(
        "els => els.map(e => [e.dataset.artifact, e.dataset.format])")
    assert ids == [["posts-table", "csv"], ["posts-table", "xlsx"]]
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
