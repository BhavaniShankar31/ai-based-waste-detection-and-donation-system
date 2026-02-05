from flask import Flask, render_template, request
import os, json, base64, requests
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HISTORY_FILE = "history.json"


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def save_history(entry):
    history = load_history()
    history.insert(0, entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)


def classify_image(filepath, lat, lon):
    # Convert image to Base64
    with open(filepath, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    prompt = """
You are a waste identification and disposal recommendation system.

1. Identify clearly what object is in the image (example: "plastic bottle", "pair of jeans", "banana peel").
2. Classify it into one of the following categories:
   - compostable (organic, food or natural materials)
   - recyclable (plastic, glass, paper, cardboard, metal, bottles, cans)
   - donatable (clean & reusable clothes, shoes, toys, books, bags, household items)
3. Then provide a friendly disposal recommendation.

Return ONLY valid JSON exactly in this format:

{
"item": "<identified object>",
"category": "<compostable/recyclable/donatable/unknown>",
"action": "<clear and friendly disposal advice based on the item and category>"
}
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llava",
            "prompt": prompt,
            "images": [image_base64],
            "stream": False
        },
        timeout=120
    )

    text = response.json()["response"].strip()

    # Extract clean JSON
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        data = json.loads(text[start:end])

        item = data.get("item", "Unknown Item").strip()
        category = data.get("category", "unknown").lower().strip()
        action = data.get("action", "No recommendation available.").strip()

    except:
        item = "Unknown Item"
        category = "unknown"
        action = "Could not classify clearly. Try using a clearer image."

    donation_places = []

    if category == "donatable" and lat and lon:
        try:
            url = (
                "https://api.geoapify.com/v2/places?"
                "categories=service.social_facility.shelter,service.social_facility.food,office.non_profit"
                f"&filter=circle:{lon},{lat},15000"
                f"&limit=15&apiKey=67301d1322ab4c93b4270635f24d767d"
            )

            r = requests.get(url).json()
            print("🔍 API RESULT:", r)

            if "features" in r and len(r["features"]) > 0:
                for p in r["features"]:
                    donation_places.append({
                        "name": p["properties"].get("name", "Donation Center / NGO"),
                        "address": p["properties"].get("formatted", "Address unavailable")
                    })

            # If still no donation centers found → Expand to places of worship (common donation points in India)
            if len(donation_places) == 0:
                url2 = (
                    "https://api.geoapify.com/v2/places?"
                    "categories=religion.place_of_worship"
                    f"&filter=circle:{lon},{lat},15000"
                    f"&limit=10&apiKey=67301d1322ab4c93b4270635f24d767d"
                )
                r2 = requests.get(url2).json()
                if "features" in r2:
                    for p in r2["features"]:
                        donation_places.append({
                            "name": p["properties"].get("name", "Religious Center Accepting Charity"),
                            "address": p["properties"].get("formatted", "Address unavailable")
                        })
        except Exception as e:
            print("❌ Error Fetching Donation Places:", e)


    return item, category, action, donation_places


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    image = request.files["image"]
    filename = datetime.now().strftime("%Y%m%d%H%M%S") + ".jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    image.save(filepath)

    lat = request.form.get("lat")
    lon = request.form.get("lon")
    print("📍 LAT:", lat, "LON:", lon)


    item, category, action, donation_places = classify_image(filepath, lat, lon)

    save_history({
        "image": filepath,
        "action": f"{item} → {category}",
        "time": datetime.now().strftime("%d %b %Y, %I:%M %p")
    })

    return render_template("result.html",
                           image_path="/" + filepath,
                           item=item,
                           category=category,
                           action=action,
                           show_donations=(category == "donatable"),
                           donation_places=donation_places)


@app.route("/history")
def history():
    return render_template("history.html", history=load_history())


if __name__ == "__main__":
    app.run(debug=True)
