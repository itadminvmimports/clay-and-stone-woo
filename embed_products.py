"""
embed_products.py
Fetches products from WooCommerce, creates embeddings using Voyage AI,
and stores them in Supabase product_embeddings_woo table.
Also upserts product display data into the products table for fast serving.
Run from the code directory:
    conda activate imgtools
    python embed_products.py
"""
from dotenv import load_dotenv
load_dotenv(override=True)
import os
import re
import time
import requests
import urllib3
import voyageai
urllib3.disable_warnings()
from supabase import create_client

# ─── Config ───────────────────────────────────────────────────────────────────
supabase  = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
vo        = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
WC_URL    = os.getenv("WC_URL")
WC_KEY    = os.getenv("WC_KEY")
WC_SECRET = os.getenv("WC_SECRET")

# ─── Helpers ──────────────────────────────────────────────────────────────────
def wc_get(endpoint, params={}):
    p = dict(params)
    p.update({"consumer_key": WC_KEY, "consumer_secret": WC_SECRET})
    r = requests.get(
        f"{WC_URL}/wp-json/wc/v3/{endpoint}",
        params=p,
        verify=False
    )
    result = r.json()
    if isinstance(result, dict) and result.get("code"):
        print(f"WC API error: {result}")
        return []
    return result

def get_meta(meta_data, key):
    return next((m["value"] for m in meta_data if m["key"] == key), "")

def build_content(p):
    description = re.sub(r"<[^>]+>", "", p.get("description") or p.get("short_description") or "").strip()
    return f"""Product: {p['name']}
Category: {p['categories'][0]['name'] if p.get('categories') else ''}
Price: ${p.get('regular_price', '')}
Origin: {get_meta(p.get('meta_data', []), 'origin')}
Dimensions: {get_meta(p.get('meta_data', []), 'dimensions')}
Use: {get_meta(p.get('meta_data', []), 'indoor_outdoor')}
Stock: {p.get('stock_quantity') if p.get('stock_quantity') is not None else 'available'}
Description: {description}"""

def get_subcategory(categories):
    for c in categories:
        if c["slug"] != "clay-and-stone":
            return c["slug"]
    return "all"

def normalize_product(p):
    description = re.sub(r"<[^>]+>", "", p.get("description") or p.get("short_description", "")).strip()
    image = p["images"][0]["src"] if p.get("images") else ""
    return {
        "id":             p["id"],
        "name":           p["name"],
        "price":          int(float(p["regular_price"])) if p.get("regular_price") else 0,
        "description":    description,
        "image":          image,
        "stock":          p.get("stock_quantity"),
        "active":         p.get("status") == "publish",
        "category": get_subcategory(p.get("categories", [])),
        "origin":         get_meta(p.get("meta_data", []), "origin"),
        "dimensions":     get_meta(p.get("meta_data", []), "dimensions"),
        "indoor_outdoor": get_meta(p.get("meta_data", []), "indoor_outdoor"),
        "updated_at":     "now()",
    }

# ─── Main ─────────────────────────────────────────────────────────────────────
def embed_products():
    print("Fetching products from WooCommerce...")
    cs_cats = wc_get("products/categories", {"slug": "clay-and-stone"})
    cat_id  = cs_cats[0]["id"] if cs_cats else None
    params  = {"per_page": 100, "status": "publish"}
    if cat_id:
        params["category"] = cat_id

    products = wc_get("products", params)
    print(f"Found {len(products)} products.\n")

    for p in products:
        name    = p["name"]
        content = build_content(p)

        # ── Embeddings ────────────────────────────────────────────────────────
        print(f"Embedding: {name}")
        result    = vo.embed([content], model="voyage-3-lite")
        embedding = result.embeddings[0]
        supabase.table("product_embeddings_woo").upsert({
            "product_id":   p["id"],
            "product_name": name,
            "content":      content,
            "embedding":    embedding,
        }, on_conflict="product_id").execute()

        # ── Product display data ───────────────────────────────────────────────
        product_data = normalize_product(p)
        supabase.table("products").upsert(
            product_data, on_conflict="id"
        ).execute()

        print(f"  Stored: {name}\n")

    print("All products embedded and stored successfully.")

if __name__ == "__main__":
    embed_products()