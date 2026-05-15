from flask import Flask, render_template, jsonify, request, redirect, url_for
from dotenv import load_dotenv
import base64
import os
import re
import json
import hmac
import hashlib
import html
import time
import logging
import requests
import urllib3
import threading

urllib3.disable_warnings()

load_dotenv()

import voyageai
vo = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))

from supabase import create_client
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

WC_URL    = os.getenv("WC_URL")
WC_KEY    = os.getenv("WC_KEY")
WC_SECRET = os.getenv("WC_SECRET")
WC_STORE  = os.getenv("WC_STORE", "https://villaandmissionimportscom.kinsta.cloud")

_categories_cache = None
_categories_time  = 0
CATEGORIES_TTL    = 3600  # 1 hour

# ─── WooCommerce Helpers ──────────────────────────────────────────────────────

def wc_get(endpoint, params={}):
    p = dict(params)
    p.update({"consumer_key": WC_KEY, "consumer_secret": WC_SECRET})
    r = requests.get(
        f"{WC_URL}/wp-json/wc/v3/{endpoint}",
        params=p,
    )
    result = r.json()
    if isinstance(result, dict) and result.get("code"):
        print(f"WC API error: {result}")
        return []
    return result

def get_meta(meta_data, key):
    return next((m["value"] for m in meta_data if m["key"] == key), "")

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
        "category":       get_subcategory(p.get("categories", [])),
        "origin":         get_meta(p.get("meta_data", []), "origin"),
        "dimensions":     get_meta(p.get("meta_data", []), "dimensions"),
        "indoor_outdoor": get_meta(p.get("meta_data", []), "indoor_outdoor"),
    }

def get_products(category=None):
    query = supabase.table("products").select("*").eq("active", True)
    if category and category != "all":
        query = query.eq("category", category)
    result = query.execute()
    return result.data if result.data else []

def get_categories():
    global _categories_cache, _categories_time
    now = time.time()
    if _categories_cache and now - _categories_time < CATEGORIES_TTL:
        return _categories_cache
    cats = wc_get("products/categories", {
        "parent": 250,
        "per_page": 100,
        "orderby": "name",
        "order": "asc"
    })
    result = {"all": "All Pieces"}
    if isinstance(cats, list):
        for c in cats:
            result[c["slug"]] = html.unescape(c["name"])
    _categories_cache = result
    _categories_time  = now
    return result

def refresh_categories_cache():
    global _categories_cache, _categories_time
    # Warm cache immediately on startup
    try:
        cats = wc_get("products/categories", {
            "parent": 250,
            "per_page": 100,
            "orderby": "name",
            "order": "asc"
        })
        result = {"all": "All Pieces"}
        if isinstance(cats, list):
            for c in cats:
                result[c["slug"]] = html.unescape(c["name"])
        _categories_cache = result
        _categories_time  = time.time()
        print("Categories cache warmed on startup")
    except Exception as e:
        print(f"Category cache warmup error: {e}")
    # Then refresh hourly
    while True:
        time.sleep(CATEGORIES_TTL)
        try:
            cats = wc_get("products/categories", {
                "parent": 250,
                "per_page": 100,
                "orderby": "name",
                "order": "asc"
            })
            result = {"all": "All Pieces"}
            if isinstance(cats, list):
                for c in cats:
                    result[c["slug"]] = html.unescape(c["name"])
            _categories_cache = result
            _categories_time  = time.time()
            print("Categories cache refreshed")
        except Exception as e:
            print(f"Category cache refresh error: {e}")

threading.Thread(target=refresh_categories_cache, daemon=True).start()

# ─── Embedding Helper ─────────────────────────────────────────────────────────

def build_embedding_content(p):
    description = re.sub(r"<[^>]+>", "", p.get("description") or p.get("short_description") or "").strip()
    return f"""Product: {p['name']}
Category: {p['categories'][0]['name'] if p.get('categories') else ''}
Price: ${p.get('regular_price', '')}
Origin: {get_meta(p.get('meta_data', []), 'origin')}
Dimensions: {get_meta(p.get('meta_data', []), 'dimensions')}
Use: {get_meta(p.get('meta_data', []), 'indoor_outdoor')}
Stock: {p.get('stock_quantity') if p.get('stock_quantity') is not None else 'available'}
Description: {description}"""

def embed_and_store(p):
    content   = build_embedding_content(p)
    result    = vo.embed([content], model="voyage-3-lite")
    embedding = result.embeddings[0]
    supabase.table("product_embeddings_woo").upsert({
        "product_id":   p["id"],
        "product_name": p["name"],
        "content":      content,
        "embedding":    embedding,
    }, on_conflict="product_id").execute()
    print(f"Embedded: {p['name']}")

# ─── App ──────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

@app.template_filter('img_url')
def img_url_filter(image):
    if not image:
        return ''
    if image.startswith('http') or image.startswith('/'):
        return image
    return f'/static/images/{image}'

# ─── Public Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", featured=get_products()[:3])

@app.route("/products")
def products():
    category   = request.args.get("category", "all")
    categories = get_categories()
    return render_template("products.html",
                           products=get_products(category),
                           categories=categories,
                           active=category)

@app.route("/product/<int:product_id>")
def product(product_id):
    p = wc_get(f"products/{product_id}")
    if not p or "id" not in p:
        return "Product not found", 404
    return render_template("product.html",
                           product=normalize_product(p),
                           wc_store=WC_STORE)

@app.route("/about")
def about():
    return render_template("about.html")

# ─── Inquiry ──────────────────────────────────────────────────────────────────

@app.route("/inquire", methods=["POST"])
def inquire():
    import resend
    resend.api_key = os.getenv("RESEND_API_KEY")
    data = request.json
    resend.Emails.send({
        "from":    "orders@claynstone.com",
        "to":      os.getenv("INQUIRY_EMAIL", "asif.shakeel@gmail.com"),
        "subject": f"New Inquiry — {data.get('product', '')}",
        "html":    f"""
            <h2>New inquiry from Clay & Stone</h2>
            <p><strong>Product:</strong> {data.get('product', '')}</p>
            <p><strong>Name:</strong> {data.get('name', '')}</p>
            <p><strong>Email:</strong> {data.get('email', '')}</p>
            <p><strong>Phone:</strong> {data.get('phone', '')}</p>
            <p><strong>Message:</strong> {data.get('message', '')}</p>
        """
    })
    return jsonify({"status": "ok"})

# ─── Chat (RAG) ───────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    import anthropic
    data     = request.json
    messages = data.get("messages", [])
    query    = messages[-1]["content"] if messages else ""

    result    = vo.embed([query], model="voyage-3-lite")
    embedding = result.embeddings[0]

    result = supabase.rpc("match_products_woo", {
        "query_embedding": embedding,
        "match_count": 3
    }).execute()

    relevant        = result.data if result.data else []
    product_context = "\n\n".join([p["content"] for p in relevant])

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    system = f"""You are a knowledgeable assistant for Clay & Stone, a Moroccan pottery boutique in San Diego.

Relevant pieces from our current collection:
{product_context}

Keep responses concise — 2-3 sentences max unless the customer asks for more detail.
Be specific and accurate about dimensions, price, origin and stock.
Never use words like "affordable", "budget", "cheap", or "expensive" unless the customer brings up price first.
Present each piece on its own merits — don't compare prices unless asked.
If stock is 0 suggest they call us.
Store hours: Mon-Sat 10am-6pm. 1815 Morena Blvd, San Diego CA 92110. Tel: 858-375-4556.
Respond in the same language the customer uses.
No bullet points, no bold, no emojis."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=system,
        messages=messages,
    )
    return jsonify({"reply": response.content[0].text})

# ─── WooCommerce Webhooks ─────────────────────────────────────────────────────

@app.route("/woo/webhook", methods=["POST"])
def woo_webhook():
    """Fires after a completed order — stock already decremented by WooCommerce."""
    secret   = os.getenv("WOO_WEBHOOK_SECRET", "")
    payload  = request.get_data()
    sig      = request.headers.get("X-WC-Webhook-Signature", "")
    expected = base64.b64encode(
        hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    ).decode()
    if secret and not hmac.compare_digest(sig, expected):
        return jsonify({"status": "error", "message": "Invalid signature"}), 401
    topic = request.headers.get("X-WC-Webhook-Topic", "")
    print(f"WooCommerce webhook received: {topic}")
    return jsonify({"status": "ok"})

@app.route("/woo/product-updated", methods=["POST"])
def woo_product_updated():
    """Fires when a product is created or updated — re-embeds for RAG."""
    secret   = os.getenv("WOO_WEBHOOK_SECRET", "")
    payload  = request.get_data()
    sig      = request.headers.get("X-WC-Webhook-Signature", "")
    expected = base64.b64encode(
        hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    ).decode()
    if secret and not hmac.compare_digest(sig, expected):
        return jsonify({"status": "error", "message": "Invalid signature"}), 401
    p = json.loads(payload)
    if p.get("status") == "publish":
        embed_and_store(p)
        print(f"Re-embedded: {p.get('name')}")
    return jsonify({"status": "ok"})

@app.route("/woo/product-deleted", methods=["POST"])
def woo_product_deleted():
    """Fires when a product is deleted — removes from RAG."""
    secret   = os.getenv("WOO_WEBHOOK_SECRET", "")
    payload  = request.get_data()
    sig      = request.headers.get("X-WC-Webhook-Signature", "")
    expected = base64.b64encode(
        hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    ).decode()
    if secret and not hmac.compare_digest(sig, expected):
        return jsonify({"status": "error", "message": "Invalid signature"}), 401
    p = json.loads(payload)
    product_id = p.get("id")
    if product_id:
        supabase.table("product_embeddings_woo").delete().eq("product_id", product_id).execute()
        print(f"Removed embedding for product id: {product_id}")
    return jsonify({"status": "ok"})

# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5001, host='0.0.0.0')
