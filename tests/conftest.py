"""One browser for the whole suite.

Playwright's sync API cannot have two live instances in one process — the second
`sync_playwright()` finds the first one's event loop already running and refuses.
tests/site and tests/analytics are separate packages with separate servers and
separate stubs, but they have to share this.

Everything else stays in each package's own conftest.
"""
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()
