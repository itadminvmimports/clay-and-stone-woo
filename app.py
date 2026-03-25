from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash
from dotenv import load_dotenv
import os

load_dotenv()

from supabase import create_client
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_products(category=None):
    query = supabase.table("products").select("*").eq("active", True).order("id")
    if category and category != "all":
        query = query.eq("category", category)
    result = query.execute()
    return result.data

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

CATEGORIES = {
    "all":        "All Pieces",
    "statement":  "Statement Vases",
    "glazed":     "Glazed Ceramic",
    "white":      "White Urns",
    "terracotta": "Terracotta & Garden",
    "berber":     "Berber Collection",
}

# ─── Public Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    featured = get_products()[:3]
    return render_template("index.html", featured=featured)

@app.route("/products")
def products():
    category = request.args.get("category", "all")
    filtered = get_products(category)
    return render_template("products.html",
                           products=filtered,
                           categories=CATEGORIES,
                           active=category)

@app.route("/product/<int:product_id>")
def product(product_id):
    result = supabase.table("products").select("*").eq("id", product_id).execute()
    if not result.data:
        return "Product not found", 404
    return render_template("product.html", product=result.data[0])

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/inquire", methods=["POST"])
def inquire():
    import resend
    resend.api_key = os.getenv("RESEND_API_KEY")
    data    = request.json
    name    = data.get("name", "")
    email   = data.get("email", "")
    phone   = data.get("phone", "")
    message = data.get("message", "")
    product = data.get("product", "")
    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": "asif.shakeel@gmail.com",
        "subject": f"New Inquiry — {product}",
        "html": f"""
            <h2>New inquiry from Clay & Stone</h2>
            <p><strong>Product:</strong> {product}</p>
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Phone:</strong> {phone}</p>
            <p><strong>Message:</strong> {message}</p>
        """
    })
    return jsonify({"status": "ok"})

@app.route("/chat", methods=["POST"])
def chat():
    import anthropic
    data     = request.json
    messages = data.get("messages", [])
    client   = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    system   = """You are a knowledgeable assistant for a Moroccan pottery boutique 
in San Diego. You help customers with:
- Product questions (indoor/outdoor use, dimensions, care, sealing)
- Style recommendations based on their space
- Origin and cultural context of pieces
- Pricing and availability inquiries
- Arranging visits to the store

Be warm, knowledgeable, and inspiring. Keep responses concise.
If asked about pricing, direct them to the product page or suggest contacting the store.
Store hours: Mon-Sat 10am-6pm PST. Located in San Diego, CA.
Respond in plain conversational sentences. No bullet points, no bold text, no headers, no emojis. Just warm, natural conversation like a knowledgeable shopkeeper."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=system,
        messages=messages,
    )
    return jsonify({"reply": response.content[0].text})

# ─── Admin: Auth ─────────────────────────────────────────────────────────────

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == os.getenv("ADMIN_PASSWORD", "admin123"):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Incorrect password"
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

# ─── Admin: Dashboard ────────────────────────────────────────────────────────

@app.route("/admin")
@admin_required
def admin_dashboard():
    all_products = supabase.table("products").select("*").order("created_at", desc=True).execute().data
    return render_template("admin.html", products=all_products, categories=CATEGORIES, view="dashboard")

# ─── Admin: Add Product ──────────────────────────────────────────────────────

@app.route("/admin/product/new", methods=["GET", "POST"])
@admin_required
def admin_new_product():
    if request.method == "POST":
        data = {
            "name":           request.form.get("name"),
            "category":       request.form.get("category"),
            "price": int(float(request.form.get("price", 0))),
            "description":    request.form.get("description"),
            "origin":         request.form.get("origin"),
            "image":          request.form.get("image"),
            "dimensions":     request.form.get("dimensions"),
            "indoor_outdoor": request.form.get("indoor_outdoor"),
            "active":         request.form.get("active") == "on",
        }
        supabase.table("products").insert(data).execute()
        return redirect(url_for("admin_dashboard"))
    return render_template("admin.html", categories=CATEGORIES, view="new")

# ─── Admin: Edit Product ─────────────────────────────────────────────────────

@app.route("/admin/product/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_product(product_id):
    if request.method == "POST":
        data = {
            "name":           request.form.get("name"),
            "category":       request.form.get("category"),
            "price": int(float(request.form.get("price", 0))),
            "description":    request.form.get("description"),
            "origin":         request.form.get("origin"),
            "image":          request.form.get("image"),
            "dimensions":     request.form.get("dimensions"),
            "indoor_outdoor": request.form.get("indoor_outdoor"),
            "active":         request.form.get("active") == "on",
        }
        supabase.table("products").update(data).eq("id", product_id).execute()
        return redirect(url_for("admin_dashboard"))
    result = supabase.table("products").select("*").eq("id", product_id).execute()
    if not result.data:
        return "Product not found", 404
    return render_template("admin.html", product=result.data[0], categories=CATEGORIES, view="edit")

# ─── Admin: Delete Product ───────────────────────────────────────────────────

@app.route("/admin/product/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_delete_product(product_id):
    supabase.table("products").delete().eq("id", product_id).execute()
    return redirect(url_for("admin_dashboard"))

# ─── Admin: Toggle Active ────────────────────────────────────────────────────

@app.route("/admin/product/<int:product_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_product(product_id):
    result = supabase.table("products").select("active").eq("id", product_id).execute()
    if result.data:
        current = result.data[0]["active"]
        supabase.table("products").update({"active": not current}).eq("id", product_id).execute()
    return redirect(url_for("admin_dashboard"))


# ─── Cart ────────────────────────────────────────────────────────────────────

@app.route("/cart/add", methods=["POST"])
def cart_add():
    data = request.json
    cart = session.get("cart", [])
    product_id = data.get("product_id")
    # Check if already in cart
    for item in cart:
        if item["product_id"] == product_id:
            item["qty"] += 1
            session["cart"] = cart
            return jsonify({"status": "ok", "cart": cart, "count": sum(i["qty"] for i in cart)})
    cart.append({
        "product_id": product_id,
        "name":       data.get("name"),
        "price":      data.get("price"),
        "image":      data.get("image"),
        "qty":        1
    })
    session["cart"] = cart
    return jsonify({"status": "ok", "cart": cart, "count": sum(i["qty"] for i in cart)})

@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    data = request.json
    cart = session.get("cart", [])
    cart = [i for i in cart if i["product_id"] != data.get("product_id")]
    session["cart"] = cart
    return jsonify({"status": "ok", "cart": cart, "count": sum(i["qty"] for i in cart)})

@app.route("/cart/update", methods=["POST"])
def cart_update():
    data = request.json
    cart = session.get("cart", [])
    for item in cart:
        if item["product_id"] == data.get("product_id"):
            item["qty"] = max(1, int(data.get("qty", 1)))
    session["cart"] = cart
    return jsonify({"status": "ok", "cart": cart, "count": sum(i["qty"] for i in cart)})

@app.route("/cart")
def cart():
    cart = session.get("cart", [])
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

# ─── Checkout ────────────────────────────────────────────────────────────────

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", [])
    if not cart:
        return redirect(url_for("products"))
    total = sum(i["price"] * i["qty"] for i in cart)
    if request.method == "POST":
        # Store order in Supabase
        order_data = {
            "customer_name":  request.form.get("name"),
            "customer_email": request.form.get("email"),
            "customer_phone": request.form.get("phone"),
            "address":        request.form.get("address"),
            "city":           request.form.get("city"),
            "state":          request.form.get("state"),
            "zip":            request.form.get("zip"),
            "items":          str(cart),
            "total":          total,
            "status":         "pending"
        }
        supabase.table("orders").insert(order_data).execute()
        # Send confirmation email
        import resend
        resend.api_key = os.getenv("RESEND_API_KEY")
        items_html = "".join(f"<li>{i['name']} x{i['qty']} — ${i['price'] * i['qty']}</li>" for i in cart)
        resend.Emails.send({
            "from":    "onboarding@resend.dev",
            "to":      request.form.get("email"),
            "subject": "Your Clay & Stone Order",
            "html":    f"""
                <h2>Thank you for your order!</h2>
                <p>We'll be in touch to confirm shipping details.</p>
                <ul>{items_html}</ul>
                <p><strong>Total: ${total}</strong></p>
                <p>Clay & Stone — a collection of Villa & Mission Imports<br>
                1815 Morena Blvd, San Diego CA 92110 · 858-375-4556</p>
            """
        })
        session["cart"] = []
        return redirect(url_for("order_confirmation"))
    return render_template("checkout.html", cart=cart, total=total)

@app.route("/order-confirmation")
def order_confirmation():
    return render_template("order_confirmation.html")

# ─── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)
