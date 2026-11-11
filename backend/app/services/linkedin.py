"""LinkedIn job scraping with Selenium.

Scrapes the public guest job-search endpoint, which needs no login. The
driver is held in a context manager so a failed scrape cannot leave an
orphaned Chrome process behind.
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from contextlib import contextmanager
from typing import Any, Iterator

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..config import get_settings

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.linkedin.com/jobs/search"
CARD_SELECTOR = "div.base-card"
DESCRIPTION_SELECTOR = "div.show-more-less-html__markup, div.description__text"


class ScraperError(RuntimeError):
    """The scrape could not be completed."""


@contextmanager
def _driver(headless: bool = True) -> Iterator[webdriver.Chrome]:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    try:
        from webdriver_manager.chrome import ChromeDriverManager

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except WebDriverException as exc:
        raise ScraperError(
            "Could not start Chrome. Install Google Chrome, or set "
            f"SCRAPER_HEADLESS=0 to debug. Underlying error: {exc}"
        ) from exc

    try:
        yield driver
    finally:
        driver.quit()


class LinkedInScraper:
    """Collects public job postings for a title and location."""

    def __init__(self, headless: bool | None = None) -> None:
        settings = get_settings()
        self.headless = settings.scraper_headless if headless is None else headless

    def search(self, title: str, location: str = "", limit: int = 25) -> list[dict[str, Any]]:
        limit = max(1, min(limit, get_settings().scraper_max_jobs * 4))
        url = self._build_url(title, location)

        with _driver(self.headless) as driver:
            try:
                driver.get(url)
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SELECTOR))
                )
            except TimeoutException:
                # The wait can expire while the page is still settling, so
                # look once more before concluding anything.
                if not driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR):
                    body = ""
                    try:
                        body = driver.find_element(By.TAG_NAME, "body").text[:400].lower()
                    except WebDriverException:
                        pass
                    if "sign in" in body and "jobs" not in body:
                        raise ScraperError(
                            "LinkedIn served a sign-in wall instead of results. "
                            "It does this to datacentre IPs and sometimes to "
                            "headless browsers; try SCRAPER_HEADLESS=0."
                        )
                    log.info("No job cards for %r", title)
                    return []
            except WebDriverException as exc:
                raise ScraperError(f"Could not load LinkedIn: {exc}") from exc

            self._scroll_until(driver, limit)
            cards = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR)[:limit]
            postings = [p for p in (self._parse_card(c) for c in cards) if p]
            # The results list carries no description, so without this the
            # postings reach the matcher with no skills and every one of
            # them scores zero.
            self._fetch_descriptions(driver, postings)
            return postings

    @staticmethod
    def _fetch_descriptions(driver: webdriver.Chrome, postings: list[dict[str, Any]]) -> None:
        """Open each posting and pull its full description."""
        for posting in postings:
            url = posting.get("url")
            if not url:
                continue
            try:
                driver.get(url)
                WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, DESCRIPTION_SELECTOR))
                )
                element = driver.find_element(By.CSS_SELECTOR, DESCRIPTION_SELECTOR)
                text = element.text.strip()
                if text:
                    posting["description"] = text
            except (TimeoutException, NoSuchElementException):
                log.info("No description found at %s", url)
            except WebDriverException as exc:
                log.warning("Failed to open %s: %s", url, exc)

    @staticmethod
    def _build_url(title: str, location: str) -> str:
        query = {"keywords": title.strip(), "f_TPR": "r604800"}
        if location.strip():
            query["location"] = location.strip()
        return f"{SEARCH_URL}?{urllib.parse.urlencode(query)}"

    @staticmethod
    def _scroll_until(driver: webdriver.Chrome, target: int) -> None:
        """Scroll until enough cards are loaded, or the page stops growing."""
        seen = 0
        for _ in range(12):
            cards = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR)
            if len(cards) >= target or len(cards) == seen:
                break
            seen = len(cards)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)

    @staticmethod
    def _parse_card(card: Any) -> dict[str, Any] | None:
        def text_of(selector: str) -> str | None:
            try:
                value = card.find_element(By.CSS_SELECTOR, selector).text.strip()
                return value or None
            except NoSuchElementException:
                return None

        title = text_of("h3.base-search-card__title")
        if not title:
            return None

        url = None
        try:
            href = card.find_element(By.CSS_SELECTOR, "a.base-card__full-link")
            url = (href.get_attribute("href") or "").split("?")[0] or None
        except NoSuchElementException:
            pass

        return {
            "title": title,
            "company": text_of("h4.base-search-card__subtitle"),
            "location": text_of("span.job-search-card__location"),
            "url": url,
            "description": text_of("p.job-search-card__snippet"),
        }
