# Repair guide sources: CarDiagn.com and charm.li

## Legal and ToS

- **CarDiagn.com:** Check https://cardiagn.com/robots.txt and the site’s Terms of Service before crawling. Republishing their repair guides may be restricted or require permission. Prefer an official API or data license if offered.
- **charm.li (Operation CHARM):** See https://charm.li/about.html. They publish a full torrent and encourage archival; crawling for metadata and links for “open in browser” use is consistent with their public, non-monetized stance. Still respect robots.txt and polite rate limits.

---

## CarDiagn.com

- **Status:** Site did not load in a simple HTTP fetch (timeout); likely JS-heavy or behind anti-bot measures.
- **Suggested approach:**
  1. Use a headless browser (Playwright or Puppeteer) to open the homepage and key URLs; dump HTML or screenshot to infer structure.
  2. Document: URL patterns (e.g. `/guide/...`, `/repair/...`), main containers, and how guides are listed (index, sitemap, search).
  3. Define CSS/XPath selectors for: guide title, body/steps, vehicle make/model/year if present, categories/tags.
- **Deliverable:** When available, add URL scheme and selectors below.

### URL scheme (to be filled after inspection)

- Index/sitemap: _TBD_
- Guide detail: _TBD_

### Selectors (to be filled after inspection)

- Guide title: _TBD_
- Guide body / steps: _TBD_
- Vehicle make/model/year: _TBD_
- Category/tags: _TBD_

---

## charm.li (Operation CHARM)

- **Base URL:** https://charm.li/
- **Structure:** Static HTML. No API; crawl only.

### URL scheme

- **Index (makes):** `https://charm.li/` — list of makes as links, e.g. `https://charm.li/Honda/`, `https://charm.li/Toyota/`.
- **Years for a make:** `https://charm.li/{Make}/` — e.g. `https://charm.li/Honda/2002/`. Make is URL-encoded (e.g. `Mercedes%20Benz`, `Dodge%20and%20Ram`).
- **Models/variants for make+year:** `https://charm.li/{Make}/{Year}/` — list of model/engine variant links, e.g. `Accord EX Coupe V6-3.0L`, `Accord LX Sedan L4-2254cc 2.3L SOHC (VTEC) MFI`. Each link goes to a manual section or index.
- **Manual section/page:** `https://charm.li/{Make}/{Year}/{ModelOrVariant}/` — content may be further links (sections) or images/PDFs. No single “body” selector; treat as link-only metadata unless extracting text from linked resources.

### Selectors (infer from static HTML)

- On index: links in main content that point to `charm.li/{Make}/` (make slugs).
- On make page: links to `charm.li/{Make}/{Year}/` (year numbers).
- On year page: headings (e.g. model/variant name) and links to `charm.li/{Make}/{Year}/{Variant}/`.
- No strong “guide body” selector; store `source_url`, make, year, variant label, and link for “open in browser.”

### Crawler behavior

- Start at `https://charm.li/`; follow make → year → variant links.
- Respect robots.txt; use a polite delay (e.g. 1–2 s between requests).
- Extract: make, year, model/variant text, `source_url`. Optionally store section headings and URLs for deeper indexing.
