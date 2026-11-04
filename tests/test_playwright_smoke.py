import os

from playwright.sync_api import Page, expect


BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:8050")


def test_website_loads_home_page(page: Page):
    response = page.goto(BASE_URL, wait_until="domcontentloaded")

    assert response is not None
    assert response.status == 200
    expect(page).to_have_title("Sea Anemone")
    expect(page.get_by_role("heading", name="Welcome to sea anemone")).to_be_visible()
    expect(page.get_by_role("button", name="1. Load Data")).to_be_visible()