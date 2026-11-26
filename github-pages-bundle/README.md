# KGBOX Brick Fanatics affiliate feed

## Order of operations

1. Install GoAffPro (free plan) in Shopify first. You need Brick Fanatics' `ref` code before the feed URLs can be final.
2. In GoAffPro, create the program: 10% commission, link tracking only, no discount code.
3. Add Brick Fanatics as an affiliate and note their `ref` code.
4. Set the cookie duration (Settings > General > Cookie Duration). 30 to 60 days is typical. Agree the window with Brick Fanatics.
5. Test one tracked link in an incognito window before building the full feed.
6. Run the transform script with the real ref code, host the output at a stable URL, and refresh it on a schedule (hourly is plenty).
7. Send Brick Fanatics the feed URL and ask which format they prefer (CSV, JSON or XML) and how often they will pull it.
8. Run test purchases: guest checkout and Shop Pay, clicked from a feed URL in incognito. Confirm the commission appears in GoAffPro and that Shopify Collabs does not also pay on the same order. Remove or pause Brick Fanatics in Collabs so the same sale cannot pay twice.
9. Go live only after both test purchases attribute correctly.

## How the transform works

`transform_products.py` fetches `https://kgboxofficial.com/products.json?limit=250` page by page until a page comes back empty, then writes one row per variant:

| Feed field | Source in products.json |
|---|---|
| id | variant `id` |
| product_id | product `id` |
| sku | variant `sku` (blank when Shopify has none) |
| title | product `title` |
| variant_title | variant `title` (blank for "Default Title") |
| description | `body_html` with HTML stripped, trimmed to about 1,000 characters |
| image_url | first `images[].src` |
| additional_image_urls | remaining `images[].src`, pipe separated |
| price | variant `price` |
| compare_at_price | variant `compare_at_price` |
| currency | stamped as USD (products.json has no currency field; the store currency is USD) |
| availability | `in_stock` when variant `available` is true, else `out_of_stock` |
| url | `https://kgboxofficial.com/products/<handle>?variant=<id>&ref=<code>` |
| product_url | the same product URL without tracking |
| brand | product `vendor` |
| tags | product `tags` |
| updated_at | product `updated_at` |

The raw `products.json` has no product URL field and no affiliate tracking. The script builds the URL from the handle and appends the GoAffPro `ref` code. That is the whole transform.

## Run it

```bash
python3 transform_products.py --ref YOUR_GOAFFPRO_REF_CODE --out-dir ./feed
```

Outputs: `affiliate_feed.csv`, `affiliate_feed.json`, `affiliate_feed.xml`.

Optional: `--sub-id brickfanatics` adds GoAffPro placement tracking. Different placements can use different sub_ids later.

## Hosting and refresh

Any static host works: a small cron job, GitHub Actions on a schedule, or a Cloudflare Worker. The feed file must sit at one stable URL that Brick Fanatics can pull. Re-running the script refreshes new products, prices and availability automatically.

### Free route: GitHub Actions + GitHub Pages

1. Create a free GitHub account and a new public repository, for example `kgbox-affiliate-feed`.
2. Put `transform_products.py` in the repository root and `.github/workflows/update-feed.yml` in the repository (both files are in this folder).
3. In the repository, open Settings > Pages and set the source to GitHub Actions.
4. Open Actions > Update BrickFanatics affiliate feed > Run workflow once to publish the first version.
5. The feed then lives at `https://<your-github-name>.github.io/kgbox-affiliate-feed/affiliate_feed.json` (also `.csv` and `.xml`). The workflow re-runs hourly and replaces the files at the same addresses.
6. Send Brick Fanatics the JSON (or CSV/XML) address once.

No Shopify password or API key is needed: the script reads the public `products.json` endpoint.

### Paid route: Mulwi

Install Mulwi Shopping Feeds in Shopify, choose Pro 1, create a custom feed, and set the product link template to append `?ref=BRICKFANATICS`. Mulwi hosts the feed address and refreshes it for you. Send Brick Fanatics that address once.

## Before launch

- Confirm the ref code from GoAffPro, do not guess it.
- Test in incognito. A logged-in admin browser can carry its own referral cookie and misattribute test orders.
- Keep the test orders refundable and check both GoAffPro and Collabs after each one.
