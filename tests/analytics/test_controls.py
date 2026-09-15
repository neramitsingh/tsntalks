"""The controls row: frame, granularity, platform, compare, and the URL.

A view you cannot link is a view you cannot send to Sunny, so the whole of the
control state lives in the query string and survives a reload. The granularity
rules are the other half: hourly readings only exist where hourly snapshots do.
"""
from urllib.parse import parse_qs, urlsplit

import pytest



def query(page):
    return {k: v[0] for k, v in parse_qs(urlsplit(page.url).query).items()}


def pressed(page, control):
    return page.locator(f'[data-control="{control}"][aria-pressed="true"]').inner_text().strip()


def test_the_controls_row_carries_all_four_controls(dashboard):
    # text_contents, not inner_text: the labels are uppercased in CSS and the
    # source case is what the markup actually says.
    labels = dashboard.locator(".a-controls .a-group > .label").all_text_contents()
    assert [t.strip() for t in labels] == ["Frame", "By", "Platform"]
    assert dashboard.is_visible("#compare")
    assert dashboard.locator('[data-control="frame"]').count() == 6


def test_the_default_is_thirty_days_daily_all_platforms_no_compare(dashboard):
    assert pressed(dashboard, "frame") == "30 days"
    assert pressed(dashboard, "granularity") == "Daily"
    assert pressed(dashboard, "platform") == "All"
    assert not dashboard.is_checked("#compare")
    # Defaults are omitted from the URL, so a plain link stays short.
    assert query(dashboard) == {}


@pytest.mark.parametrize("frame,granularity", [
    ("7 days", "Daily"),
    ("90 days", "Weekly"),
    ("12 months", "Monthly"),
    ("All", "Monthly"),
])
def test_each_frame_picks_its_own_default_granularity(dashboard, frame, granularity):
    dashboard.click(f'[data-control="frame"]:text-is("{frame}")')
    assert pressed(dashboard, "granularity") == granularity


def test_hourly_is_offered_only_for_seven_days_or_less(dashboard):
    hourly = dashboard.locator('[data-control="granularity"]:text-is("Hourly")')

    dashboard.click('[data-control="frame"]:text-is("7 days")')
    assert not hourly.is_disabled()

    dashboard.click('[data-control="frame"]:text-is("30 days")')
    assert hourly.is_disabled()
    assert "7 days or less" in hourly.get_attribute("title")


def test_leaving_a_short_frame_moves_granularity_off_an_option_that_vanished(dashboard):
    """Hourly over 30 days would be a chart of 720 marks read from snapshots
    that have been thinned to one a day. It cannot silently stay selected."""
    dashboard.click('[data-control="frame"]:text-is("7 days")')
    dashboard.click('[data-control="granularity"]:text-is("Hourly")')
    assert pressed(dashboard, "granularity") == "Hourly"

    dashboard.click('[data-control="frame"]:text-is("90 days")')
    assert pressed(dashboard, "granularity") == "Weekly"


def test_every_control_lands_in_the_url(dashboard):
    dashboard.click('[data-control="frame"]:text-is("90 days")')
    dashboard.click('[data-control="granularity"]:text-is("Monthly")')
    dashboard.click('[data-control="platform"]:text-is("TikTok")')
    dashboard.check("#compare")

    assert query(dashboard) == {"frame": "90d", "g": "month", "p": "tiktok", "cmp": "1"}


def test_control_state_survives_a_reload(dashboard):
    dashboard.click('[data-control="frame"]:text-is("12 months")')
    dashboard.click('[data-control="platform"]:text-is("Instagram")')
    dashboard.check("#compare")
    before = dashboard.url

    dashboard.reload()
    dashboard.wait_for_selector("#shell:not([hidden])")

    assert dashboard.url == before
    assert pressed(dashboard, "frame") == "12 months"
    assert pressed(dashboard, "platform") == "Instagram"
    assert pressed(dashboard, "granularity") == "Monthly"
    assert dashboard.is_checked("#compare")


def test_a_linked_view_opens_on_the_same_controls(page, stub, analytics_url, signin):
    signin(page)
    page.goto(analytics_url + "?tab=posts&frame=custom&from=2026-09-09&to=2026-09-15&g=hour&p=youtube&cmp=1")
    page.wait_for_selector("#shell:not([hidden])")

    assert pressed(page, "frame") == "Custom"
    assert pressed(page, "granularity") == "Hourly"
    assert pressed(page, "platform") == "YouTube"
    assert page.is_checked("#compare")
    assert page.input_value('[data-control="from"]') == "2026-09-09"
    assert page.input_value('[data-control="to"]') == "2026-09-15"
    assert page.get_attribute("#tab-posts", "aria-selected") == "true"


def test_a_hand_edited_url_falls_back_instead_of_white_screening(page, stub, analytics_url, signin):
    signin(page)
    page.goto(analytics_url + "?tab=nonsense&frame=fortnight&g=decade&p=myspace&cmp=yes")
    page.wait_for_selector("#shell:not([hidden])")

    assert pressed(page, "frame") == "30 days"
    assert pressed(page, "granularity") == "Daily"
    assert pressed(page, "platform") == "All"
    assert not page.is_checked("#compare")
    assert page.get_attribute("#tab-overview", "aria-selected") == "true"


def test_a_custom_frame_with_no_dates_is_not_a_custom_frame(page, stub, analytics_url, signin):
    signin(page)
    page.goto(analytics_url + "?frame=custom")
    page.wait_for_selector("#shell:not([hidden])")
    assert pressed(page, "frame") == "30 days"


def test_the_custom_date_inputs_appear_only_for_a_custom_frame(dashboard):
    assert dashboard.locator(".a-custom").is_hidden()
    dashboard.click('[data-control="frame"]:text-is("Custom")')
    assert dashboard.locator(".a-custom").is_visible()
    # Picking custom without dates offers a sensible window rather than nothing.
    assert dashboard.input_value('[data-control="from"]')
    assert dashboard.input_value('[data-control="to"]')


def test_a_custom_span_of_a_week_re_enables_hourly(dashboard):
    dashboard.click('[data-control="frame"]:text-is("Custom")')
    dashboard.fill('[data-control="from"]', "2026-09-09")
    dashboard.fill('[data-control="to"]', "2026-09-15")
    dashboard.wait_for_timeout(100)
    assert not dashboard.locator('[data-control="granularity"]:text-is("Hourly")').is_disabled()


# --- the tab strip ----------------------------------------------------------

def test_the_tab_strip_selects_a_view_and_records_it(dashboard):
    dashboard.click("#tab-audience")
    assert dashboard.get_attribute("#tab-audience", "aria-selected") == "true"
    assert dashboard.get_attribute("#tab-overview", "aria-selected") == "false"
    assert query(dashboard)["tab"] == "audience"


def test_the_tab_strip_is_a_tablist_and_answers_to_arrow_keys(dashboard):
    assert dashboard.get_attribute("#tabs", "role") == "tablist"
    dashboard.click("#tab-overview")
    dashboard.press("#tab-overview", "ArrowRight")
    assert dashboard.get_attribute("#tab-growth", "aria-selected") == "true"
    dashboard.press("#tab-growth", "End")
    assert dashboard.get_attribute("#tab-health", "aria-selected") == "true"


def test_the_view_area_is_never_blank_and_unexplained(dashboard):
    """Tabs 6 to 11 fill these in. Until then each one names itself and says it
    is not built, rather than leaving an empty <main>."""
    for tab in ("overview", "growth", "posts", "episodes", "audience", "health"):
        dashboard.click(f"#tab-{tab}")
        assert dashboard.inner_text("#view").strip()


# --- the ship bar -----------------------------------------------------------

def test_no_horizontal_overflow_on_desktop_or_phone(dashboard, phone):
    for pg in (dashboard, phone):
        assert pg.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


def test_the_controls_row_wraps_rather_than_scrolling_on_a_phone(phone):
    assert phone.is_visible(".a-controls")
    assert phone.evaluate(
        "document.querySelector('.a-controls').scrollWidth"
        " <= document.querySelector('.a-controls').clientWidth + 1")
