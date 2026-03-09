from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import os

load_dotenv()

from supabase import create_client
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_products(category=None):
    query = supabase.table("products").select("*").eq("active", True)
    if category and category != "all":
        query = query.eq("category", category)
    result = query.execute()
    return result.data
app = Flask(__name__)

# ─── Placeholder products until Supabase is connected ───────────────────────
# PRODUCTS = [
#     {
#         "id": 1,
#         "name": "Picasso Faces Vase",
#         "category": "statement",
#         "price": 1200,
#         "description": "A stunning large-format vase hand-painted with vivid cubist faces. Each piece is unique, crafted by artisans in Marrakech.",
#         "origin": "Marrakech, Morocco",
#         "image": "picasso_vase.jpg",
#         "dimensions": "24\" H x 8\" W",
#         "indoor_outdoor": "Indoor",
#     },
#     {
#         "id": 2,
#         "name": "Iridescent Dark Amphora",
#         "category": "glazed",
#         "price": 850,
#         "description": "A deep charcoal vase with iridescent glaze that shifts between green, purple and blue in different light.",
#         "origin": "Fes, Morocco",
#         "image": "dark_vase.jpg",
#         "dimensions": "20\" H x 7\" W",
#         "indoor_outdoor": "Indoor / Covered Outdoor",
#     },
#     {
#         "id": 3,
#         "name": "Tall Green Glazed Cylinder",
#         "category": "glazed",
#         "price": 650,
#         "description": "Tall cylindrical vase with rich forest green glaze over a textured cream body. Bold and architectural.",
#         "origin": "Safi, Morocco",
#         "image": "green_vase.jpg",
#         "dimensions": "36\" H x 10\" W",
#         "indoor_outdoor": "Indoor / Covered Outdoor",
#     },
#     {
#         "id": 4,
#         "name": "White Glazed Urn",
#         "category": "white",
#         "price": 780,
#         "description": "Elegant oversized urn in pure white glaze. Minimalist and versatile — a statement in any space.",
#         "origin": "Marrakech, Morocco",
#         "image": "white_urn.jpg",
#         "dimensions": "30\" H x 12\" W",
#         "indoor_outdoor": "Indoor",
#     },
#     {
#         "id": 5,
#         "name": "Terracotta Garden Urn",
#         "category": "terracotta",
#         "price": 320,
#         "description": "Traditional hand-thrown terracotta urn with rope-twist detail. Weather-resistant and timeless.",
#         "origin": "Ourika Valley, Morocco",
#         "image": "terracotta_urn.jpg",
#         "dimensions": "18\" H x 14\" W",
#         "indoor_outdoor": "Indoor / Outdoor",
#     },
#     {
#         "id": 6,
#         "name": "Berber Geometric Vessel",
#         "category": "berber",
#         "price": 420,
#         "description": "Ancient Berber geometric patterns etched into natural clay. A collector's piece with centuries of tradition.",
#         "origin": "Atlas Mountains, Morocco",
#         "image": "berber_vessel.jpg",
#         "dimensions": "14\" H x 10\" W",
#         "indoor_outdoor": "Indoor",
#     },
# ]

CATEGORIES = {
    "all":       "All Pieces",
    "statement": "Statement Vases",
    "glazed":    "Glazed Ceramic",
    "white":     "White Urns",
    "terracotta":"Terracotta & Garden",
    "berber":    "Berber Collection",
}

# ─── Routes ─────────────────────────────────────────────────────────────────

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
    
    data = request.json
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
            <h2>New inquiry from Souk & Stone</h2>
            <p><strong>Product:</strong> {product}</p>
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Phone:</strong> {phone}</p>
            <p><strong>Message:</strong> {message}</p>
        """
    })

    return jsonify({"status": "ok"})

# ─── AI Chat endpoint ────────────────────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    import anthropic
    data = request.json
    messages = data.get("messages", [])

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    system = """You are a knowledgeable assistant for a Moroccan pottery boutique 
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

# ─── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)