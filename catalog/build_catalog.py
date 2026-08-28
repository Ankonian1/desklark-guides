#!/usr/bin/env python3
"""Generate the DeskLark Studio catalog lookbook page (index.html) from the
22 printable/spreadsheet products' own package.json files, so the page can
never drift out of sync with the product data itself (price, one-line
description) the way a hand-maintained page eventually would.

What's hardcoded here (and why it has to be, since no other file states it):
  - FAMILIES: which family/season section each product belongs to, in what
    order. This is an editorial grouping decision, not derivable from
    package.json.
  - DISPLAY_NAME: a short catalog-card title per product. Etsy's own listing
    titles (package.json "title") are long, keyword-stuffed SEO strings
    (~150-200 chars, e.g. "Airbnb Host P&L Tracker Excel Template | Multi
    Property Short Term Rental Spreadsheet | ..."), appropriate for Etsy
    search but wrong for a visual lookbook card. Each DISPLAY_NAME is the
    clean product name already used elsewhere for the same product
    (metrics.md's stats table, build/marketing/pinterest/pins-queue.json's
    pin titles) -- not a new name invented for this page.
  - SEASON_TAG: a short badge derived from each package.json's own
    "seasonal_window" field (paraphrased down to a few words for card
    display; the full sourced/verified text is preserved untouched in
    package.json and this script's own comments below, not overwritten).
  - LIVE_LISTINGS: the 8 real Etsy listing URLs, copied from metrics.md's
    live-listing table (confirmed via `node build/etsy/pull-stats.js`) and
    cross-checked against build/marketing/pinterest/pins-queue.json's
    "listing_url" values for the same 8 slugs -- both sources agree. Every
    other product (14) renders as an inert "Coming soon" card instead of a
    live `<a href>` (no href = never a broken/placeholder link once
    deployed; matches the same-slug promo cards' `.promo-card--soon`
    convention used across build/web-content/*/index.html and
    build/web-tools/*/index.html) and its JSON-LD Offer omits the "url"
    field entirely rather than asserting a fake one (schema.org doesn't
    require it).

Everything else on the page (price, one-line description, product_type) is
read live from build/listing-packages/<slug>/package.json's own "price" and
"subtitle" fields -- if a price changes or a subtitle is rewritten, re-run
this script and the page updates with it.

Usage: python3 build_catalog.py   (writes index.html in this directory)
Run resize_heroes.py first (or after) to (re)generate images/<slug>.webp --
this script does not touch images, only markup.
"""
import json
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parent
BUILD_DIR = CATALOG_DIR.parent.parent  # .../build
LISTING_PACKAGES_DIR = BUILD_DIR / "listing-packages"

SITE_URL = "https://guides.desklark.com"
CANONICAL = f"{SITE_URL}/catalog/"
BRAND = "DeskLark Studio"

# The 8 live batch-1 listings -- URLs copied verbatim from metrics.md's
# "Etsy API stats pull" table (2026-08-04) / pins-queue.json's listing_url
# for the same 8 slugs. Every other product is not yet published on Etsy.
LIVE_LISTINGS = {
    "saas-metrics-nrr-dashboard": "https://www.etsy.com/listing/4546844459/saas-metrics-nrr-dashboard",
    "etsy-shop-profit-tax-estimator": "https://www.etsy.com/listing/4546845029/etsy-shop-profit-tax-estimator",
    "ecommerce-margin-calculator": "https://www.etsy.com/listing/4546845187/ecommerce-margin-calculator",
    "airbnb-host-pl-tracker": "https://www.etsy.com/listing/4546861028/airbnb-host-pl-tracker",
    "backtoschool": "https://www.etsy.com/listing/4546861118/back-to-school-money-semester-planner",
    "budget": "https://www.etsy.com/listing/4546861206/debt-snowball-zero-based-budget-planner",
    "fall": "https://www.etsy.com/listing/4546846561/fall-budget-halloween-party-planner",
    "meal": "https://www.etsy.com/listing/4546861350/adhd-friendly-meal-planning-grocery-budget",
}

# Short catalog-card names -- see module docstring. Sourced from metrics.md /
# pins-queue.json's own shorthand for each product, not invented here.
DISPLAY_NAME = {
    "saas-metrics-nrr-dashboard": "SaaS Metrics & NRR Dashboard",
    "etsy-shop-profit-tax-estimator": "Etsy Shop Profit & Tax Estimator",
    "ecommerce-margin-calculator": "E-commerce Margin Calculator",
    "airbnb-host-pl-tracker": "Airbnb Host P&L Tracker",
    "backtoschool": "Back-to-School Money & Semester Planner",
    "budget": "Debt Snowball & Zero-Based Budget Planner",
    "campbudget": "Summer Camp Budget Planner",
    "cashstuffing": "Cash Stuffing Budget System",
    "christmas": "Christmas Budget Planner",
    "declutter": "Spring Declutter Planner",
    "engaged": "Newly Engaged Planner",
    "fall": "Fall Budget & Halloween Party Planner",
    "freelancertax": "Freelancer Quarterly Tax Planner",
    "gradbudget": "Graduation Gift Budget Planner",
    "honeymoon": "Honeymoon Budget Planner",
    "meal": "ADHD-Friendly Meal Planner",
    "movingbudget": "Moving Budget Planner",
    "newyear": "New Year Money Reset Planner",
    "taxorganizer": "Tax Document Organizer",
    "vacationbudget": "Summer Vacation Budget Planner",
    "valentine": "Valentine's Day Budget Planner",
    "wedding": "Wedding Budget Planner",
}

# Short season/family badge -- paraphrased from each package.json's own
# "seasonal_window" field (kept verbatim, with full sourcing, in package.json
# itself; this is just the card-badge-length summary of the same claim).
SEASON_TAG = {
    "saas-metrics-nrr-dashboard": "Evergreen",
    "etsy-shop-profit-tax-estimator": "Evergreen",
    "ecommerce-margin-calculator": "Evergreen",
    "airbnb-host-pl-tracker": "Evergreen",
    "engaged": "Dec–Feb (engagement season)",
    "wedding": "Evergreen",
    "honeymoon": "May–Oct (wedding season)",
    "valentine": "Feb 14 (Valentine's Day)",
    "fall": "Aug–Oct (fall & Halloween)",
    "christmas": "Oct–Dec (holiday season)",
    "newyear": "Dec–Jan (New Year reset)",
    "gradbudget": "May–Jun (grad season)",
    "campbudget": "Summer camp season",
    "vacationbudget": "Jun–Aug (summer travel)",
    "movingbudget": "May–Sep (peak moving season)",
    "backtoschool": "Aug–Sep (back to school)",
    "budget": "Evergreen",
    "cashstuffing": "Evergreen",
    "meal": "Evergreen",
    "declutter": "Spring (spring cleaning)",
    "taxorganizer": "Jan–Apr (tax season)",
    "freelancertax": "Jan–Apr (tax season)",
}

# Editorial grouping: (section id, heading, intro line, [slugs in display order])
FAMILIES = [
    (
        "spreadsheets",
        "Financial Spreadsheets — Business & Investor Tools",
        "Formula-driven Excel/Google Sheets workbooks for specific business verticals. Evergreen -- no seasonal window.",
        ["saas-metrics-nrr-dashboard", "etsy-shop-profit-tax-estimator", "ecommerce-margin-calculator", "airbnb-host-pl-tracker"],
    ),
    (
        "wedding-romance",
        "Wedding, Engagement & Romance",
        "From the proposal through the honeymoon, plus a standalone Valentine's Day planner.",
        ["engaged", "wedding", "honeymoon", "valentine"],
    ),
    (
        "holiday-seasonal",
        "Holiday & Seasonal",
        "Autumn through the New Year reset.",
        ["fall", "christmas", "newyear"],
    ),
    (
        "life-transitions",
        "Life Transitions & Travel",
        "Graduation, camp, vacation, moving, and back-to-school -- the money side of a season-specific life event.",
        ["gradbudget", "campbudget", "vacationbudget", "movingbudget", "backtoschool"],
    ),
    (
        "everyday-systems",
        "Everyday Money & Life Systems",
        "Ongoing habits and systems with no single seasonal peak -- budgeting, saving, eating, decluttering, and tax admin.",
        ["budget", "cashstuffing", "meal", "declutter", "taxorganizer", "freelancertax"],
    ),
]


def load_products():
    products = {}
    for pkg_dir in LISTING_PACKAGES_DIR.iterdir():
        pj = pkg_dir / "package.json"
        if not pkg_dir.is_dir() or not pj.exists():
            continue
        pkg = json.loads(pj.read_text())
        if pkg.get("product_type") not in ("printable", "spreadsheet"):
            continue
        products[pkg["slug"]] = pkg
    return products


def fmt_price(price):
    # $4.50 keeps its cents; whole-dollar prices ($5, $39) print without them.
    if float(price) == int(price):
        return f"${int(price)}"
    return f"${price:.2f}"


def esc(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def product_card_html(slug, pkg):
    name = DISPLAY_NAME[slug]
    subtitle = esc(pkg["subtitle"])
    price = fmt_price(pkg["price"])
    season = esc(SEASON_TAG[slug])
    kind = "Spreadsheet" if pkg["product_type"] == "spreadsheet" else "Printable"
    is_live = slug in LIVE_LISTINGS
    if is_live:
        tag = "a"
        open_tag = f'<a class="catalog-card catalog-card--live" href="{esc(LIVE_LISTINGS[slug])}">'
        badge = '<span class="catalog-live-badge">Live on Etsy</span>'
        cta = '<span class="catalog-cta">View on Etsy &rarr;</span>'
    else:
        tag = "div"
        open_tag = '<div class="catalog-card catalog-card--soon">'
        badge = '<span class="catalog-soon-badge">Coming soon</span>'
        cta = '<span class="catalog-cta catalog-cta--disabled">Coming soon</span>'
    return f"""        {open_tag}
          <div class="catalog-card-media">
            <img src="images/{slug}.webp" width="600" height="480" loading="lazy" decoding="async"
                 alt="{esc(name)} mockup pages -- {BRAND}">
            {badge}
          </div>
          <div class="catalog-card-body">
            <span class="catalog-kind">{kind}</span>
            <h3>{esc(name)}</h3>
            <p class="catalog-desc">{subtitle}</p>
            <div class="catalog-meta-row">
              <span class="catalog-price">{price}</span>
              <span class="catalog-season">{season}</span>
            </div>
            {cta}
          </div>
        </{tag}>
"""


def family_section_html(section_id, heading, intro, slugs, products):
    cards = "".join(product_card_html(slug, products[slug]) for slug in slugs)
    return f"""    <section class="family-section" aria-labelledby="{section_id}-heading">
      <h2 id="{section_id}-heading">{esc(heading)}</h2>
      <p class="catalog-family-intro">{esc(intro)}</p>
      <div class="catalog-grid">
{cards}      </div>
    </section>
"""


def item_list_json_ld(products):
    items = []
    position = 1
    for _, _, _, slugs in FAMILIES:
        for slug in slugs:
            pkg = products[slug]
            is_live = slug in LIVE_LISTINGS
            offer = {
                "@type": "Offer",
                "priceCurrency": "USD",
                "price": f"{float(pkg['price']):.2f}",
                "availability": "https://schema.org/InStock" if is_live else "https://schema.org/PreOrder",
            }
            if is_live:
                # "url" only asserted for real, live offers -- omitted (not a
                # fake/placeholder guess) for the 14 not-yet-published products.
                offer["url"] = LIVE_LISTINGS[slug]
            items.append({
                "@type": "ListItem",
                "position": position,
                "item": {
                    "@type": "Product",
                    "name": DISPLAY_NAME[slug],
                    "description": pkg["subtitle"],
                    "image": f"{SITE_URL}/catalog/images/{slug}.webp",
                    "brand": {"@type": "Brand", "name": BRAND},
                    "offers": offer,
                },
            })
            position += 1
    doc = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"{BRAND} Product Catalog",
        "description": "All 22 DeskLark Studio printable and spreadsheet products, grouped by family and season.",
        "url": CANONICAL,
        "numberOfItems": len(items),
        "itemListElement": items,
    }
    return json.dumps(doc, indent=2)


def main():
    products = load_products()
    all_slugs = [slug for _, _, _, slugs in FAMILIES for slug in slugs]
    missing = set(products) - set(all_slugs)
    if missing:
        raise SystemExit(f"Products not assigned to a FAMILIES section: {sorted(missing)}")
    extra = set(all_slugs) - set(products)
    if extra:
        raise SystemExit(f"FAMILIES references slugs with no package.json: {sorted(extra)}")

    sections_html = "".join(
        family_section_html(sid, heading, intro, slugs, products)
        for sid, heading, intro, slugs in FAMILIES
    )
    json_ld = item_list_json_ld(products)
    live_count = sum(1 for s in all_slugs if s in LIVE_LISTINGS)

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Catalog | {BRAND}</title>
<meta name="description" content="All 22 {BRAND} printable and spreadsheet products in one lookbook -- financial spreadsheets, wedding & romance, holiday & seasonal, life transitions & travel, and everyday money systems. Instant digital download.">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{CANONICAL}">

<meta property="og:type" content="website">
<meta property="og:title" content="Catalog | {BRAND}">
<meta property="og:description" content="All 22 {BRAND} printable and spreadsheet products in one lookbook, grouped by family and season.">
<meta property="og:url" content="{CANONICAL}">
<meta property="og:site_name" content="{BRAND}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Catalog | {BRAND}">
<meta name="twitter:description" content="All 22 {BRAND} printable and spreadsheet products in one lookbook.">

<link rel="stylesheet" href="../styles.css">
<script type="application/ld+json">
{json_ld}
</script>
</head>
<body>

<a class="skip-link" href="#catalog-body">Skip to catalog</a>

<header class="site-header">
  <div class="wrap">
    <p class="wordmark">{BRAND}</p>
    <p class="tagline">The full catalog -- 22 printables and spreadsheets, one page.</p>
  </div>
</header>

<main class="wrap">

  <section class="hub-intro">
    <h1>Catalog</h1>
    <p class="lede">
      Every {BRAND} product in one place, grouped by family and season: financial spreadsheets,
      wedding &amp; romance, holiday &amp; seasonal, life transitions &amp; travel, and everyday
      money systems. {live_count} of 22 are live on Etsy today (marked <strong>Live on Etsy</strong>
      below); the rest are built and reviewer-approved, publishing as their own seasonal or batch
      window opens.
    </p>
  </section>

  <div id="catalog-body">
{sections_html}  </div>

</main>

<footer class="site-footer">
  <div class="wrap">
    <nav class="site-links" aria-label="DeskLark Studio sites">
      <a href="https://desklark.com/">DeskLark Studio home</a>
      <a href="https://weddingbudget.desklark.com/">Wedding Budget Calculator</a>
      <a href="https://cashstuffing.desklark.com/">Cash Stuffing Calculator</a>
      <a href="https://setaside.desklark.com/">Freelancer Set-Aside Calculator</a>
      <a href="https://disclosure.desklark.com/">AI-Disclosure Generator</a>
      <a href="https://www.etsy.com/shop/DeskLarkStudio">Etsy shop</a>
    </nav>
    <p>{BRAND} &middot; No accounts, no cookies, no analytics, no data collected by this page.</p>
    <p class="footer-fine">Prices and availability shown here match each product's own listing page; instant digital download, no physical item ships.</p>
  </div>
</footer>

</body>
</html>
"""
    (CATALOG_DIR / "index.html").write_text(page)
    print(f"Wrote index.html: {len(all_slugs)} products, {live_count} live on Etsy, {len(page)} bytes of markup.")


if __name__ == "__main__":
    main()
