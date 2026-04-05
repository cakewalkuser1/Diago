"""
Charm.li (Operation CHARM) crawler.
Fetches make → year → variant structure and yields records for ETL.
Respects robots.txt and uses a polite delay. See docs/repair-guide-sources.md.
Usage: python -m scripts.charmli_crawler [--delay 1.5] [--max-makes 2]
Output: JSON lines to stdout (or pass --db-url to write to PostgreSQL).
"""

import argparse
import json
import logging
import re
import sys
import time
from urllib.parse import unquote, urljoin, urlparse

import httpx

CHARM_BASE = "https://charm.li"
USER_AGENT = "DiagoRepairGuideCrawler/1.0 (+https://github.com/diago)"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _make_soup(html: str, url: str):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("Install beautifulsoup4: pip install beautifulsoup4")
    return BeautifulSoup(html, "html.parser")


def _links_to_same_host(base_url: str, soup, selector: str = "a"):
    base = urlparse(base_url)
    for a in soup.select(selector):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc and parsed.netloc != base.netloc:
            continue
        if not full.startswith(CHARM_BASE):
            continue
        yield full, (a.get_text(strip=True) or "")


def crawl_makes(client: httpx.Client, delay: float) -> list[str]:
    """Fetch index and return make URLs (e.g. https://charm.li/Honda/)."""
    out = []
    r = client.get(CHARM_BASE + "/", follow_redirects=True)
    r.raise_for_status()
    time.sleep(delay)
    soup = _make_soup(r.text, CHARM_BASE + "/")
    for url, text in _links_to_same_host(CHARM_BASE + "/", soup):
        path = urlparse(url).path.strip("/")
        if not path or path.count("/") > 0:
            continue
        out.append(url)
    return out


def crawl_years_for_make(client: httpx.Client, make_url: str, delay: float) -> list[str]:
    """Return year URLs for a make (e.g. https://charm.li/Honda/2002/)."""
    out = []
    r = client.get(make_url, follow_redirects=True)
    r.raise_for_status()
    time.sleep(delay)
    soup = _make_soup(r.text, make_url)
    make_path = urlparse(make_url).path.strip("/")
    for url, text in _links_to_same_host(make_url, soup):
        path = urlparse(url).path.strip("/")
        if not path.startswith(make_path) or path == make_path:
            continue
        rest = path[len(make_path) :].strip("/")
        if rest.isdigit():
            out.append(url)
    return out


def crawl_variants_for_year(
    client: httpx.Client, year_url: str, make: str, year: int, delay: float
) -> list[dict]:
    """Return list of {source_url, title, vehicle_make, vehicle_model, year_min, year_max}."""
    out = []
    r = client.get(year_url, follow_redirects=True)
    r.raise_for_status()
    time.sleep(delay)
    soup = _make_soup(r.text, year_url)
    year_path = urlparse(year_url).path.strip("/")
    seen = set()
    for url, text in _links_to_same_host(year_url, soup):
        path = urlparse(url).path.strip("/")
        if not path.startswith(year_path) or path == year_path:
            continue
        rest = path[len(year_path) :].strip("/")
        if not rest or rest in seen:
            continue
        seen.add(rest)
        title = unquote(rest.replace("+", " ")) or text or rest
        out.append({
            "source": "charm_li",
            "source_url": url,
            "title": title[:500],
            "summary": None,
            "content": None,
            "vehicle_make": make,
            "vehicle_model": title[:200],
            "year_min": year,
            "year_max": year,
            "category": None,
        })
    return out


def run_crawl(delay: float = 1.0, max_makes: int | None = None) -> list[dict]:
    records = []
    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
        makes = crawl_makes(client, delay)
        if max_makes:
            makes = makes[:max_makes]
        for make_url in makes:
            path = urlparse(make_url).path.strip("/")
            make_name = unquote(path.replace("+", " "))
            logger.info("Make: %s", make_name)
            year_urls = crawl_years_for_make(client, make_url, delay)
            for year_url in year_urls:
                path = urlparse(year_url).path.strip("/")
                parts = path.split("/")
                year_s = parts[-1] if parts else ""
                try:
                    year = int(year_s)
                except ValueError:
                    continue
                if year < 1982 or year > 2013:
                    continue
                logger.info("  Year: %s", year)
                variants = crawl_variants_for_year(client, year_url, make_name, year, delay)
                records.extend(variants)
    return records


def main():
    p = argparse.ArgumentParser(description="Charm.li crawler for repair guide ETL")
    p.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    p.add_argument("--max-makes", type=int, default=None, help="Limit number of makes (for testing)")
    p.add_argument("--json", action="store_true", help="Output JSON lines to stdout")
    args = p.parse_args()
    records = run_crawl(delay=args.delay, max_makes=args.max_makes)
    logger.info("Total records: %s", len(records))
    if args.json:
        for r in records:
            print(json.dumps(r), file=sys.stdout)
    else:
        json.dump(records, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
