import streamlit as st
import requests
from datetime import datetime
import geocoder

API_BASE = "http://127.0.0.1:5000"

st.set_page_config(page_title="Food Donation System", layout="wide", page_icon="🍽️")

# ---------------- Styles -----------------
st.markdown("""
<style>
[data-testid="stSidebar"]{background:linear-gradient(180deg,#1e3a8a,#2563eb);color:white;}
.stButton>button{background:linear-gradient(90deg,#9333ea,#3b82f6);color:white;border-radius:8px;padding:10px 20px;border:none;font-weight:bold;}
.stButton>button:hover{background:linear-gradient(90deg,#7e22ce,#2563eb);}
.main-title{text-align:center;font-size:36px;font-weight:800;background:linear-gradient(90deg,#2563eb,#9333ea);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:5px;}
.subtitle{text-align:center;color:#4b5563;font-size:16px;}
.donation-card{background:#fff;padding:20px;margin:15px 0;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.08);}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>🍽️ Food Donation System</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Connecting Donors with NGOs to reduce food waste 🤝</p>", unsafe_allow_html=True)

# ---------------- Session -----------------
if "user_id" not in st.session_state: st.session_state["user_id"] = None
if "user_type" not in st.session_state: st.session_state["user_type"] = None
if "lat" not in st.session_state: st.session_state["lat"] = None
if "lon" not in st.session_state: st.session_state["lon"] = None

menu = st.sidebar.radio("Menu", ["Register", "Post Donation", "View Donations"])

# ---------------- Register -----------------
if menu == "Register":
    st.subheader("Register as Donor/NGO")
    with st.form("reg"):
        col1, col2 = st.columns(2)
        with col1:
            user_type = st.selectbox("Type", ["donor", "ngo"])
            name = st.text_input("Name")
            email = st.text_input("Email")
        with col2:
            phone = st.text_input("Phone")
            address = st.text_area("Address")
        submit = st.form_submit_button("Register")
    if submit:
        r = requests.post(f"{API_BASE}/api/register", json={
            "user_type": user_type, "name": name, "email": email, "phone": phone, "address": address
        })
        if r.ok:
            st.success(f"Registered {user_type} | ID={r.json()['user_id']}")
            st.session_state["user_id"] = r.json()['user_id']
            st.session_state["user_type"] = user_type
        else:
            try:
                st.error(r.json().get("error", "Error"))
            except:
                st.error(r.text)

# ---------------- Post Donation -----------------
if menu == "Post Donation":
    st.subheader("Post a Food Donation")
    if st.session_state["user_type"] != "donor":
        st.warning("Only donors can post donations")
    else:
        donor_id = st.session_state["user_id"]
        st.info(f"Logged in as Donor ID:{donor_id}")

        if st.button("Capture My Location"):
            g = geocoder.ip('me')
            if g.ok:
                st.session_state["lat"], st.session_state["lon"] = g.latlng
                st.success(f"Location captured: ({st.session_state['lat']},{st.session_state['lon']})")
            else:
                st.error("Could not get location")

        with st.form("don_form"):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Food Item")
                qty = st.text_input("Quantity (e.g., 2kg, 5 plates)")
                food_image = st.file_uploader("Upload Food Image", type=["png", "jpg", "jpeg"])
            with col2:
                desc = st.text_area("Description (expiry, freshness etc.)")
            submit = st.form_submit_button("Submit Donation")

        if submit:
            if not title or not qty or not desc or not food_image:
                st.error("All fields including image are required")
            elif not st.session_state["lat"] or not st.session_state["lon"]:
                st.error("Capture your location first")
            else:
                payload = {
                    "donor_id": donor_id,
                    "title": title,
                    "quantity": qty,
                    "description": desc,
                    "latitude": st.session_state["lat"],
                    "longitude": st.session_state["lon"]
                }

                files = {"food_image": (food_image.name, food_image.getvalue(), food_image.type)}

                try:
                    r = requests.post(f"{API_BASE}/api/donations", data=payload, files=files)
                    if r.ok:
                        st.success("Donation posted!")
                        st.json(r.json())
                    else:
                        try:
                            st.error(r.json().get("error", "Failed"))
                        except:
                            st.error(f"Error: {r.text}")
                except Exception as e:
                    st.error(f"Error: {e}")

# ---------------- View Donations -----------------
if menu=="View Donations":
    st.subheader("NGO: Browse Donations")
    if st.session_state["user_type"]!="ngo":
        st.warning("Only NGOs can view donations")
    else:
        ngo_id = st.session_state["user_id"]
        r = requests.get(f"{API_BASE}/api/donations")
        if r.ok:
            try:
                donations = r.json()
            except:
                st.error(f"Unexpected response: {r.text}")
                donations = []

            if not donations:
                st.info("No donations")
            for d in donations:
                st.markdown(
                    f"<div class='donation-card'>"
                    f"<h3>{d['title']} ({d['quantity']})</h3>"
                    f"<p>{d['description']}</p>"
                    f"<p>📍 Location: <a href='https://www.google.com/maps?q={d.get('latitude')},{d.get('longitude')}' target='_blank'>View on Google Maps</a></p>"
                    f"<p>CO₂ Emission Saved: {d['co2_saved']} kg </p>"
                    f"<p>Donor: {d['donor_name']}</p>"
                    f"<p>Posted: {datetime.fromisoformat(d['created_at']).strftime('%d %b %Y %I:%M %p')}</p>"
                    f"{'<img src='+API_BASE+d['image_url']+' width=200>' if d.get('image_url') else ''}"
                    f"</div>",
                    unsafe_allow_html=True
                )
                if d.get("claimed_by"):
                    st.info(f"Already claimed by {d['claimed_by']}")
                else:
                    if st.button(f"Claim Donation #{d['id']}", key=f"claim_{d['id']}"):
                        res = requests.post(f"{API_BASE}/api/donations/{d['id']}/claim", json={"ngo_id":ngo_id})
                        if res.ok:
                            st.success("Claimed successfully!")
                        else:
                            try:
                                st.error(res.json().get("error","Failed"))
                            except:
                                st.error(f"Error: {res.text}")
        else:
            st.error("Error fetching donations")