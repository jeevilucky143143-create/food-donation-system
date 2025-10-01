from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, re

app = Flask(__name__)
CORS(app)

# ---------------- Database Setup ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.sqlite")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------- Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(10), nullable=False)  # donor / ngo
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(80))
    address = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.String(100), default="1")
    pickup_address = db.Column(db.String(300))
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    image_path = db.Column(db.String(300), nullable=True)
    co2_saved = db.Column(db.Float, default=0.0)
    claimed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    donor = db.relationship("User", foreign_keys=[donor_id], backref="donations_made")
    ngo = db.relationship("User", foreign_keys=[claimed_by], backref="donations_claimed")

# ---------------- Utility ----------------
def estimate_co2_saving(quantity: str) -> float:
    """Estimate CO₂ saving based on quantity (kg or plates)."""
    if not quantity:
        return 1.0
    q = quantity.lower().strip()
    try:
        match_kg = re.search(r"([\d\.]+)\s*kg", q)
        if match_kg:
            return round(float(match_kg.group(1)) * 2.0, 2)
        match_num = re.search(r"([\d\.]+)", q)
        if "plate" in q or "meal" in q:
            return round(float(match_num.group(1)) * 1.0, 2) if match_num else 1.0
        if match_num:
            return round(float(match_num.group(1)) * 1.0, 2)
    except:
        pass
    return 1.0

def donation_to_dict(d: Donation) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "description": d.description,
        "quantity": d.quantity,
        "pickup_address": d.pickup_address,
        "latitude": d.latitude,
        "longitude": d.longitude,
        "image_url": f"/images/{os.path.basename(d.image_path)}" if d.image_path else None,
        "co2_saved": d.co2_saved,
        "claimed_by": d.ngo.name if d.ngo else None,
        "created_at": d.created_at.isoformat(),
        "donor_name": d.donor.name if d.donor else None,
        "donor_id": d.donor_id,
    }

# ---------------- Routes ----------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    if not data or not data.get("name") or data.get("user_type") not in ["donor", "ngo"]:
        return jsonify({"error": "Invalid data"}), 400
    u = User(
        name=data["name"], user_type=data["user_type"],
        email=data.get("email"), phone=data.get("phone"),
        address=data.get("address")
    )
    db.session.add(u)
    db.session.commit()
    return jsonify({"message": "registered", "user_id": u.id}), 201

@app.route("/api/donations", methods=["POST"])
def create_donation():
    donor_id = request.form.get("donor_id")
    title = request.form.get("title")
    if not donor_id or not title:
        return jsonify({"error": "donor_id and title required"}), 400

    donor = User.query.get(donor_id)
    if not donor or donor.user_type != "donor":
        return jsonify({"error": "valid donor_id required"}), 400

    qty = request.form.get("quantity", "1")
    co2_val = estimate_co2_saving(qty)

    try:
        lat = float(request.form.get("latitude"))
        lon = float(request.form.get("longitude"))
    except:
        return jsonify({"error": "latitude and longitude must be numeric"}), 400

    image_file = request.files.get("food_image")
    image_path = None
    if image_file:
        IMG_DIR = os.path.join(BASE_DIR, "food_images")
        os.makedirs(IMG_DIR, exist_ok=True)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image_file.filename}"
        image_path = os.path.join(IMG_DIR, filename)
        image_file.save(image_path)

    d = Donation(
        donor_id=donor_id,
        title=title,
        description=request.form.get("description"),
        quantity=qty,
        latitude=lat,
        longitude=lon,
        image_path=image_path,
        co2_saved=co2_val
    )
    db.session.add(d)
    db.session.commit()
    return jsonify({"message": "donation created", "donation": donation_to_dict(d)}), 201

@app.route("/api/donations", methods=["GET"])
def list_donations():
    donations = Donation.query.order_by(Donation.created_at.desc()).all()
    return jsonify([donation_to_dict(d) for d in donations])

@app.route("/api/donations/<int:donation_id>/claim", methods=["POST"])
def claim_donation(donation_id):
    data = request.json
    ngo_id = data.get("ngo_id")
    ngo = User.query.get(ngo_id)
    donation = Donation.query.get(donation_id)
    if not ngo or ngo.user_type != "ngo":
        return jsonify({"error": "Invalid NGO"}), 400
    if not donation:
        return jsonify({"error": "Donation not found"}), 404
    if donation.claimed_by:
        return jsonify({"error": "Already claimed"}), 400
    donation.claimed_by = ngo_id
    db.session.commit()
    return jsonify({"message": "claimed", "donation": donation_to_dict(donation)}), 200

@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(os.path.join(BASE_DIR, "food_images"), filename)

# ---------------- Error Handling ----------------
@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
