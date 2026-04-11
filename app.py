from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from dotenv import load_dotenv
import base64
import os
import re
import json
import hmac
import hashlib
import logging
import requests
import urllib3
import stripe

urllib3.disable_warnings()
load_dotenv()

import voyageai
vo = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))

from supabase import create_client
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

WC_URL    = os.getenv("WC_URL")
WC_KEY    = os.getenv("WC_KEY")
WC_SECRET = os.getenv("WC_SECRET")

STRIPE_PUB_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

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

def wc_post(endpoint, data):
    r = requests.post(
        f"{WC_URL}/wp-json/wc/v3/{endpoint}",
        params={"consumer_key": WC_KEY, "consumer_secret": WC_SECRET},
        json=data,
    )
    result = r.json()
    if isinstance(result, dict) and result.get("code"):
        print(f"WC API error: {result}")
        return None
    return result

def get_meta(meta_data, key):
    return next((m["value"] for m in meta_data if m["key"] == key), "")

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
        "category":       p["categories"][0]["slug"] if p.get("categories") else "all",
        "origin":         get_meta(p.get("meta_data", []), "origin"),
        "dimensions":     get_meta(p.get("meta_data", []), "dimensions"),
        "indoor_outdoor": get_meta(p.get("meta_data", []), "indoor_outdoor"),
    }

def get_products(category=None):
    params = {"per_page": 100, "status": "publish"}
    cs_cats = wc_get("products/categories", {"slug": "clay-and-stone"})
    if cs_cats and isinstance(cs_cats, list):
        params["category"] = cs_cats[0]["id"]
    if category and category != "all":
        sub_cats = wc_get("products/categories", {"slug": category})
        if sub_cats and isinstance(sub_cats, list):
            params["category"] = sub_cats[0]["id"]
    return [normalize_product(p) for p in wc_get("products", params)]

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

import html

def get_categories():
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
    return result

# ─── Public Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", featured=get_products()[:3])

@app.route("/products")
def products():
    category = request.args.get("category", "all")
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
    return render_template("product.html", product=normalize_product(p))

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

# ─── Cart ─────────────────────────────────────────────────────────────────────

@app.route("/cart/add", methods=["POST"])
def cart_add():
    data       = request.json
    cart       = session.get("cart", [])
    product_id = data.get("product_id")
    for item in cart:
        if item["product_id"] == product_id:
            item["qty"] += 1
            session["cart"] = cart
            return jsonify({"status": "ok", "count": sum(i["qty"] for i in cart)})
    cart.append({
        "product_id": product_id,
        "name":       data.get("name"),
        "price":      data.get("price"),
        "image":      data.get("image"),
        "qty":        1,
    })
    session["cart"] = cart
    return jsonify({"status": "ok", "count": sum(i["qty"] for i in cart)})

@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    data = request.json
    cart = session.get("cart", [])
    cart = [i for i in cart if i["product_id"] != data.get("product_id")]
    session["cart"] = cart
    return jsonify({"status": "ok", "count": sum(i["qty"] for i in cart)})

@app.route("/cart/update", methods=["POST"])
def cart_update():
    data = request.json
    cart = session.get("cart", [])
    for item in cart:
        if item["product_id"] == data.get("product_id"):
            item["qty"] = max(1, int(data.get("qty", 1)))
    session["cart"] = cart
    return jsonify({"status": "ok", "count": sum(i["qty"] for i in cart)})

@app.route("/cart")
def cart():
    cart  = session.get("cart", [])
    total = sum(i["price"] * i["qty"] for i in cart)
    return render_template("cart.html", cart=cart, total=total)

@app.route("/cart/count")
def cart_count():
    cart = session.get("cart", [])
    return jsonify({"count": sum(i["qty"] for i in cart)})

@app.route("/cart/data")
def cart_data():
    cart = session.get("cart", [])
    return jsonify({"cart": cart})

# ─── Checkout ─────────────────────────────────────────────────────────────────

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", [])
    if not cart:
        return redirect(url_for("products"))
    total = sum(i["price"] * i["qty"] for i in cart)

    if request.method == "POST":
        name              = request.form.get("name", "")
        email             = request.form.get("email", "")
        phone             = request.form.get("phone", "")
        address           = request.form.get("address", "")
        city              = request.form.get("city", "")
        state             = request.form.get("state", "")
        zip_              = request.form.get("zip", "")
        payment_method_id = request.form.get("payment_method_id", "")

        if not payment_method_id:
            return render_template("checkout.html", cart=cart, total=total,
                                   stripe_pub_key=STRIPE_PUB_KEY,
                                   error="Payment information is required.")

        # ── Charge via Stripe ──────────────────────────────────────────────
        try:
            intent = stripe.PaymentIntent.create(
                amount=total * 100,
                currency="usd",
                payment_method=payment_method_id,
                confirm=True,
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                description=f"Clay & Stone order — {name}",
                receipt_email=email,
                metadata={"customer_name": name, "customer_phone": phone},
            )
        except stripe.error.CardError as e:
            return render_template("checkout.html", cart=cart, total=total,
                                   stripe_pub_key=STRIPE_PUB_KEY,
                                   error=e.user_message)
        except Exception as e:
            print(f"Stripe error: {e}")
            return render_template("checkout.html", cart=cart, total=total,
                                   stripe_pub_key=STRIPE_PUB_KEY,
                                   error="Payment failed. Please try again or call us at 858-375-4556.")

        # ── Create WooCommerce order ───────────────────────────────────────
        name_parts = name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name  = name_parts[1] if len(name_parts) > 1 else ""

        order_data = {
            "payment_method":       "stripe",
            "payment_method_title": "Credit Card (Stripe)",
            "set_paid":             True,
            "status":               "processing",
            "billing": {
                "first_name": first_name,
                "last_name":  last_name,
                "address_1":  address,
                "city":       city,
                "state":      state,
                "postcode":   zip_,
                "country":    "US",
                "email":      email,
                "phone":      phone,
            },
            "shipping": {
                "first_name": first_name,
                "last_name":  last_name,
                "address_1":  address,
                "city":       city,
                "state":      state,
                "postcode":   zip_,
                "country":    "US",
            },
            "line_items": [
                {"product_id": item["product_id"], "quantity": item["qty"]}
                for item in cart
            ],
            "customer_note": f"Stripe PaymentIntent: {intent.id}",
        }

        order = wc_post("orders", order_data)

        if not order:
            print(f"WooCommerce order failed — Stripe charged: {intent.id}")
            return render_template("checkout.html", cart=cart, total=total,
                                   stripe_pub_key=STRIPE_PUB_KEY,
                                   error=f"Payment succeeded but order creation failed. Please call us at 858-375-4556 with reference: {intent.id}")

        # ── Send confirmation emails ───────────────────────────────────────
        try:
            import resend
            resend.api_key = os.getenv("RESEND_API_KEY")
            items_html = "".join(
                f"<li>{i['name']} &times;{i['qty']} — ${i['price'] * i['qty']}</li>"
                for i in cart
            )
            resend.Emails.send({
                "from":    "orders@claynstone.com",
                "to":      email,
                "subject": "Your Clay & Stone Order",
                "html":    f"""
                    <h2>Thank you for your order!</h2>
                    <p>Your payment has been processed successfully.</p>
                    <ul>{items_html}</ul>
                    <p><strong>Total: ${total}</strong></p>
                    <p>Clay & Stone — a collection of Villa &amp; Mission Imports<br>
                    1815 Morena Blvd, San Diego CA 92110 · 858-375-4556</p>
                """
            })
            resend.Emails.send({
                "from":    "orders@claynstone.com",
                "to":      os.getenv("INQUIRY_EMAIL", "asif.shakeel@gmail.com"),
                "subject": f"New Order — {name} (#{order.get('id', '')})",
                "html":    f"""
                    <h2>New Clay & Stone order — PAID</h2>
                    <p><strong>Customer:</strong> {name}</p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Phone:</strong> {phone}</p>
                    <p><strong>Address:</strong> {address}, {city}, {state} {zip_}</p>
                    <ul>{items_html}</ul>
                    <p><strong>Total: ${total}</strong></p>
                    <p><strong>Stripe PaymentIntent:</strong> {intent.id}</p>
                    <p><strong>WooCommerce order ID:</strong> #{order.get('id', '')}</p>
                """
            })
        except Exception as e:
            print(f"Email error: {e}")

        session["cart"] = []
        session["last_order_id"] = order.get("id")
        return redirect(url_for("order_confirmation"))

    return render_template("checkout.html", cart=cart, total=total,
                           stripe_pub_key=STRIPE_PUB_KEY)

@app.route("/order-confirmation")
def order_confirmation():
    order_id = session.pop("last_order_id", None)
    return render_template("order_confirmation.html", order_id=order_id)

# ─── Stock Check ──────────────────────────────────────────────────────────────

@app.route("/check-stock", methods=["POST"])
def check_stock():
    data  = request.json
    items = data.get("items", [])
    for item in items:
        name     = item.get("name")
        qty      = item.get("quantity", 1)
        products = wc_get("products", {"search": name, "per_page": 5})
        if products and isinstance(products, list):
            for p in products:
                if p["name"] == name and p.get("manage_stock"):
                    if (p["stock_quantity"] or 0) < qty:
                        return jsonify({"ok": False, "item": name, "available": p["stock_quantity"]})
    return jsonify({"ok": True})

# ─── WooCommerce Webhooks ─────────────────────────────────────────────────────

@app.route("/woo/webhook", methods=["POST"])
def woo_webhook():
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

# DEV ONLY — remove before production
@app.route("/cart/clear")
def cart_clear():
    session["cart"] = []
    return redirect(url_for("cart"))

# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5001, host='0.0.0.0')
