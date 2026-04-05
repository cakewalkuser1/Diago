"""
CarDiagn.com crawler stub.
Site times out on simple HTTP; use Playwright when structure is documented.
See docs/repair-guide-sources.md. Set CARDIAGN_START_URL and REPAIR_GUIDES_DB_URL for ETL.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# When CarDiagn structure is known, add selectors and fetch with Playwright.
# Example output record: {"source": "cardiagn", "source_url": "...", "title": "...", ...}


def run_crawl(delay: float = 1.5, max_pages: int | None = None) -> list[dict]:
    """Return list of repair guide records. Implement when site structure is documented."""
    start = os.environ.get("CARDIAGN_START_URL", "https://cardiagn.com/")
    logger.info("CarDiagn crawler: structure not yet documented. Start URL: %s", start)
    logger.info("Use Playwright to inspect %s and update docs/repair-guide-sources.md", start)
    return []


def main():
    records = run_crawl()
    if "--json" in sys.argv:
        for r in records:
            print(json.dumps(r), file=sys.stdout)
    else:
        json.dump(records, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
