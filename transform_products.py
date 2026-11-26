#!/usr/bin/env python3
"""
Transform KGBOX Shopify products.json into a Brick Fanatics affiliate feed.

What it does:
  1. Fetches https://kgboxofficial.com/products.json?limit=250&page=N
     (paginating until a page returns no products).
  2. Emits one row per product variant with an affiliate-tracked URL:
       https://kgboxofficial.com/products/<handle>?variant=<id>&ref=<code>
     (the variant parameter is omitted for single "Default Title" variants).
  3. Writes affiliate_feed.csv, affiliate_feed.json and affiliate_feed.xml.

Usage:
  python3 transform_products.py --ref YOUR_GOAFFPRO_REF_CODE
  python3 transform_products.py --ref YOUR_CODE --out-dir ./feed
  python3 transform_products.py --ref YOUR_CODE --input sample_products.json

Host the output folder at a stable URL and re-run on a schedule
(e.g. hourly via cron, GitHub Actions, or a Cloudflare Worker) so new
products, price changes and availability stay current.

No third-party packages required. Python 3.9+.
"""

import argparse
import csv
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode

STORE_URL = "https://kgboxofficial.com"
DEFAULT_CURRENCY = "USD"  # products.json has no currency field; store currency is USD.
PAGE_LIMIT = 250
DESCRIPTION_MAX_CHARS = 1000

FIELDS = [
    "id",
    "product_id",
    "sku",
    "title",
    "variant_title",
    "description",
    "image_url",
    "additional_image_urls",
    "price",
    "compare_at_price",
    "currency",
    "availability",
    "url",
    "product_url",
    "brand",
    "tags",
    "updated_at",
]


class TextExtractor(HTMLParser):
    """Collect visible text from an HTML fragment."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)


def html_to_text(html):
    if not html:
        return ""
    parser = TextExtractor()
    parser.feed(html)
    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > DESCRIPTION_MAX_CHARS:
        text = text[:DESCRIPTION_MAX_CHARS].rsplit(" ", 1)[0].strip() + "..."
    return text


def fetch_products(store_url):
    products = []
    page = 1
    while True:
        url = f"{store_url}/products.json?limit={PAGE_LIMIT}&page={page}"
        request = urllib.request.Request(url, headers={"User-Agent": "KGBOX affiliate feed builder"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        batch = data.get("products", [])
        if not batch:
            break
        products.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
        page += 1
    return products


def load_products(input_path, store_url):
    if input_path:
        data = json.loads(Path(input_path).read_text(encoding="utf-8"))
        return data.get("products", [])
    return fetch_products(store_url)


def build_rows(products, store_url, ref_code, currency, sub_id=None):
    rows = []
    for product in products:
        handle = product.get("handle", "")
        if not handle:
            continue
        product_url = f"{store_url}/products/{handle}"
        images = [img.get("src", "") for img in product.get("images", []) if img.get("src")]
        description = html_to_text(product.get("body_html", ""))
        variants = product.get("variants", []) or [{}]
        multiple_variants = len(variants) > 1

        for variant in variants:
            variant_id = variant.get("id", "")
            variant_title = variant.get("title", "") or ""
            params = {}
            if multiple_variants or (variant_title and variant_title != "Default Title"):
                if variant_id:
                    params["variant"] = variant_id
            params["ref"] = ref_code
            if sub_id:
                params["sub_id"] = sub_id
            tracked_url = f"{product_url}?{urlencode(params)}"

            rows.append(
                {
                    "id": str(variant_id),
                    "product_id": str(product.get("id", "")),
                    "sku": variant.get("sku") or "",
                    "title": product.get("title", ""),
                    "variant_title": "" if variant_title == "Default Title" else variant_title,
                    "description": description,
                    "image_url": images[0] if images else "",
                    "additional_image_urls": " | ".join(images[1:]),
                    "price": variant.get("price") or "",
                    "compare_at_price": variant.get("compare_at_price") or "",
                    "currency": currency,
                    "availability": "in_stock" if variant.get("available") else "out_of_stock",
                    "url": tracked_url,
                    "product_url": product_url,
                    "brand": product.get("vendor", "") or "KGBOX",
                    "tags": ", ".join(product.get("tags", []) or []),
                    "updated_at": product.get("updated_at", ""),
                }
            )
    return rows


def write_csv(rows, path):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows, path):
    path.write_text(json.dumps({"products": rows}, indent=2, ensure_ascii=False), encoding="utf-8")


def write_xml(rows, path):
    root = ET.Element("products")
    for row in rows:
        item = ET.SubElement(root, "product")
        for field in FIELDS:
            child = ET.SubElement(item, field)
            child.text = str(row.get(field, ""))
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description="Build the KGBOX Brick Fanatics affiliate feed.")
    parser.add_argument("--ref", required=True, help="GoAffPro ref code for Brick Fanatics.")
    parser.add_argument("--store", default=STORE_URL, help="Store base URL.")
    parser.add_argument("--currency", default=DEFAULT_CURRENCY, help="Currency code to stamp on every row.")
    parser.add_argument("--sub-id", default=None, help="Optional GoAffPro sub_id for placement-level tracking.")
    parser.add_argument("--out-dir", default=".", help="Folder for affiliate_feed.csv/.json/.xml.")
    parser.add_argument("--input", default=None, help="Local products.json file to transform instead of fetching.")
    args = parser.parse_args()

    store_url = args.store.rstrip("/")
    products = load_products(args.input, store_url)
    rows = build_rows(products, store_url, args.ref, args.currency, args.sub_id)
    if not rows:
        print("No products found. Nothing written.", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(rows, out_dir / "affiliate_feed.csv")
    write_json(rows, out_dir / "affiliate_feed.json")
    write_xml(rows, out_dir / "affiliate_feed.xml")
    print(f"Wrote {len(rows)} variant rows from {len(products)} products to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
