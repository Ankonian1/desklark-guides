#!/usr/bin/env python3
"""Resize each product's Etsy-listing hero mockup for the catalog lookbook page.

Why this exists: build/listing-packages/<slug>/images/01-hero.png is a
2000x1600 PNG (~170-620KB each) sized for Etsy's listing-image requirements.
Embedding all 22 of those directly in one page would blow the lookbook's
2.5MB page-weight budget many times over. This script makes small, catalog-
grade copies instead: 600px-wide WebP, sized for a lookbook card, not a
full-screen product photo.

Source of truth for the 22-product list: this script does NOT hardcode the
slug list. It reads every build/listing-packages/*/package.json, keeps the
ones with product_type in {"printable", "spreadsheet"} (this excludes
aidisclosurekit, product_type "guide" -- a PDF compliance kit, not a
printable/spreadsheet product, and the reason the catalog has 22 items, not
23), and resizes exactly one hero per product: images/01-hero.png.

Usage (run from this directory, or anywhere -- paths are anchored to this
file's location):
    python3 resize_heroes.py
    python3 resize_heroes.py --quality 82 --width 600

Idempotent: safe to re-run any time a listing-package's 01-hero.png changes
(e.g. a future re-shoot) -- it always overwrites images/<slug>.webp. Prints a
per-file size report plus a total, so a re-run doubles as a page-weight
sanity check without needing a separate script.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

CATALOG_DIR = Path(__file__).resolve().parent
BUILD_DIR = CATALOG_DIR.parent.parent  # .../build
LISTING_PACKAGES_DIR = BUILD_DIR / "listing-packages"
OUT_DIR = CATALOG_DIR / "images"

CATALOG_PRODUCT_TYPES = {"printable", "spreadsheet"}


def discover_products():
    """Return sorted list of (slug, package_dir) for every printable/spreadsheet
    product under build/listing-packages/ -- i.e. everything the catalog page
    should show. Skips any package missing package.json or its hero image."""
    products = []
    for pkg_dir in sorted(LISTING_PACKAGES_DIR.iterdir()):
        pj_path = pkg_dir / "package.json"
        if not pkg_dir.is_dir() or not pj_path.exists():
            continue
        pkg = json.loads(pj_path.read_text())
        if pkg.get("product_type") not in CATALOG_PRODUCT_TYPES:
            continue
        hero = pkg_dir / "images" / "01-hero.png"
        if not hero.exists():
            print(f"  SKIP {pkg_dir.name}: no images/01-hero.png", file=sys.stderr)
            continue
        products.append((pkg.get("slug", pkg_dir.name), hero))
    return products


def resize_one(src: Path, dest: Path, width: int, quality: int) -> int:
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        new_h = round(h * width / w)
        im = im.resize((width, new_h), Image.LANCZOS)
        im.save(dest, "WEBP", quality=quality, method=6)
    return dest.stat().st_size


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--width", type=int, default=600, help="output width in px (default 600)")
    ap.add_argument("--quality", type=int, default=82, help="WebP quality 0-100 (default 82)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    products = discover_products()
    if not products:
        print("No printable/spreadsheet products found -- check LISTING_PACKAGES_DIR", file=sys.stderr)
        sys.exit(1)

    total_bytes = 0
    print(f"Resizing {len(products)} hero images to {args.width}px wide, WebP q{args.quality}\n")
    for slug, src in products:
        dest = OUT_DIR / f"{slug}.webp"
        size = resize_one(src, dest, args.width, args.quality)
        total_bytes += size
        print(f"  {slug:45s} {size/1024:6.1f} KB  -> images/{slug}.webp")

    print(f"\n{len(products)} images, {total_bytes/1024:.1f} KB total ({total_bytes/1024/1024:.2f} MB)")


if __name__ == "__main__":
    main()
