from flask import Flask, render_template, request, redirect, session, jsonify, flash
import sqlite3
import requests
import pickle
import os
import pandas as pd
from datetime import datetime, date, timedelta
import math
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "database.db")
MODEL_PATH = os.path.join(BASE_DIR, "pollution_model.pkl")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

API_KEY = "08c15b843efa68ef89ebe213c829c0c9"

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = "secret123"


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_logged_in():
    return "user_id" in session


def require_login():
    if not is_logged_in():
        return False, redirect("/login")
    return True, None


def require_municipal():
    if "user_id" not in session:
        return False, redirect("/login")
    if session.get("role") != "municipal":
        flash("This page is only for municipal users.", "error")
        return False, redirect("/dashboard")
    return True, None


def approx_distance_km(lat1, lon1, lat2, lon2):
    return (((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5) * 111.0


def ensure_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS pollution(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT,
        latitude REAL,
        longitude REAL,
        aqi REAL,
        pm25 REAL,
        pm10 REAL,
        ts TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS adopt_tree(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        district TEXT,
        area TEXT,
        location TEXT,
        tree_type TEXT,
        plant_date TEXT,
        purpose TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS districts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS areas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        district TEXT,
        name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS burn_reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        area TEXT,
        lat REAL,
        lon REAL,
        photo_path TEXT,
        note TEXT,
        ml_label TEXT,
        confidence REAL,
        status TEXT,
        ts TEXT
    )
    """)

    conn.commit()
    conn.close()


def seed_districts():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM districts")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    districts = ["Bengaluru Urban", "Bengaluru Rural", "Mysuru", "Tumakuru"]
    for d in districts:
        cur.execute("INSERT OR IGNORE INTO districts(name) VALUES(?)", (d,))

    areas = {
        "Bengaluru Urban": ["Whitefield", "Marathahalli", "Electronic City", "Jayanagar"],
        "Bengaluru Rural": ["Devanahalli", "Hoskote"],
        "Mysuru": ["Vijayanagar", "Hebbal"],
        "Tumakuru": ["Tumkur City", "Gubbi", "Koratagere", "Tiptur"],
    }

    for dist, area_list in areas.items():
        for area_name in area_list:
            cur.execute("INSERT INTO areas(district, name) VALUES(?,?)", (dist, area_name))

    conn.commit()
    conn.close()


def load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print("MODEL LOAD ERROR:", e)
        return None


def geocode_area(area_text: str):
    try:
        url = f"https://api.openweathermap.org/geo/1.0/direct?q={area_text}&limit=1&appid={API_KEY}"
        data = requests.get(url, timeout=10).json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print("GEOCODE ERROR:", e)
        return None


def get_aqi_by_coords(lat, lon):
    try:
        url = (
            "https://api.openweathermap.org/data/2.5/air_pollution"
            f"?lat={lat}&lon={lon}&appid={API_KEY}"
        )
        payload = requests.get(url, timeout=10).json()
        if "list" not in payload or not payload["list"]:
            return None
        aqi = payload["list"][0]["main"]["aqi"]
        pm25 = payload["list"][0]["components"]["pm2_5"]
        pm10 = payload["list"][0]["components"]["pm10"]
        return float(aqi), float(pm25), float(pm10)
    except Exception as e:
        print("AQI COORD ERROR:", e)
        return None


def get_live_environment(city="Tumakuru"):
    try:
        weather_url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&appid={API_KEY}&units=metric"
        )
        weather = requests.get(weather_url, timeout=10).json()

        if str(weather.get("cod")) != "200":
            print("WEATHER ERROR:", weather)
            return None

        lat = float(weather["coord"]["lat"])
        lon = float(weather["coord"]["lon"])

        aqi_data = get_aqi_by_coords(lat, lon)
        if not aqi_data:
            return None

        aqi, pm25, pm10 = aqi_data

        return {
            "city": weather.get("name", city),
            "latitude": lat,
            "longitude": lon,
            "temperature": float(weather["main"]["temp"]),
            "humidity": float(weather["main"]["humidity"]),
            "description": weather["weather"][0]["description"],
            "aqi": aqi,
            "pm25": pm25,
            "pm10": pm10,
        }
    except Exception as e:
        print("API EXCEPTION (CITY):", e)
        return None


def get_live_environment_by_coords(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)

        weather_url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        )
        weather = requests.get(weather_url, timeout=10).json()

        if str(weather.get("cod")) != "200":
            print("WEATHER ERROR (GPS):", weather)
            return None

        aqi_data = get_aqi_by_coords(lat, lon)
        if not aqi_data:
            return None

        aqi, pm25, pm10 = aqi_data

        return {
            "city": weather.get("name", "Your Location"),
            "latitude": lat,
            "longitude": lon,
            "temperature": float(weather["main"]["temp"]),
            "humidity": float(weather["main"]["humidity"]),
            "description": weather["weather"][0]["description"],
            "aqi": aqi,
            "pm25": pm25,
            "pm10": pm10,
        }
    except Exception as e:
        print("API EXCEPTION (GPS):", e)
        return None


def save_pollution_point(place_name, lat, lon, aqi, pm25, pm10):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pollution(city, latitude, longitude, aqi, pm25, pm10, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(place_name),
            float(lat),
            float(lon),
            float(aqi),
            float(pm25),
            float(pm10),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()


def forecast_next_3_days(predicted_today):
    today = date.today()
    out = []
    for i in range(1, 4):
        d = today + timedelta(days=i)
        pred = float(predicted_today) + (i * 0.3)
        out.append({"day": d.strftime("%a"), "pred": round(pred, 2)})
    return out


def aqi_status_details(aqi_value):
    value = int(round(float(aqi_value)))

    if value <= 1:
        return {"label": "Good", "tone": "good", "message": "Air quality is good right now."}
    if value == 2:
        return {
            "label": "Fair",
            "tone": "good",
            "message": "Air quality is acceptable right now.",
        }
    if value == 3:
        return {
            "label": "Moderate",
            "tone": "mid",
            "message": "Air quality is moderate. Sensitive people should take care.",
        }
    if value == 4:
        return {
            "label": "Poor",
            "tone": "bad",
            "message": "Air quality is unhealthy. Reduce outdoor exposure if possible.",
        }
    return {
        "label": "Very Poor",
        "tone": "bad",
        "message": "Air quality is very unhealthy right now.",
    }


@app.route("/")
def home():
    return render_template("index.html", title="EcoGuardian")


@app.route("/register", methods=["GET", "POST"])
def register():
    if is_logged_in():
        return redirect("/dashboard")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "citizen").strip()

        if not name or not email or not password:
            flash("Please fill in all required fields.", "error")
            return render_template("register.html", title="Register")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                (name, email, password, role),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("That email is already registered.", "error")
            return render_template("register.html", title="Register")

        conn.close()
        flash("Account created successfully. Please login.", "success")
        return redirect("/login")

    return render_template("register.html", title="Register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if is_logged_in():
        return redirect("/dashboard")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, role FROM users WHERE email=? AND password=?",
            (email, password),
        )
        user = cur.fetchone()
        conn.close()

        if not user:
            flash("Invalid email or password.", "error")
            return render_template("login.html", title="Login")

        session["user_id"] = user[0]
        session["user_name"] = user[1]
        session["role"] = user[2]

        flash(f"Welcome back, {user[1]}!", "success")
        return redirect("/dashboard")

    return render_template("login.html", title="Login")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    ok, resp = require_login()
    if not ok:
        return resp

    if session.get("role") == "municipal":
        return redirect("/municipal-dashboard")
    return redirect("/citizen-dashboard")


@app.route("/citizen-dashboard")
def citizen_dashboard():
    ok, resp = require_login()
    if not ok:
        return resp

    if session.get("role") == "municipal":
        return redirect("/municipal-dashboard")

    lat = request.args.get("lat")
    lon = request.args.get("lon")
    city = request.args.get("city")
    area = request.args.get("area")

    if lat and lon:
        env = get_live_environment_by_coords(lat, lon)
    elif area:
        coords = geocode_area(area)
        if not coords:
            flash("We could not find that area. Try a nearby landmark or city name.", "error")
            return redirect("/citizen-dashboard")
        env = get_live_environment_by_coords(coords[0], coords[1])
    elif city:
        env = get_live_environment(city)
    else:
        env = get_live_environment("Tumakuru")

    if env is None:
        flash("Live air data is temporarily unavailable. Please try again.", "error")
        return render_template("dashboard.html", title="Dashboard", data_unavailable=True)

    save_pollution_point(
        env["city"],
        env["latitude"],
        env["longitude"],
        env["aqi"],
        env["pm25"],
        env["pm10"],
    )

    predicted_aqi = float(env["aqi"])
    model = load_model()
    if model:
        try:
            features = pd.DataFrame([[env["pm25"], env["pm10"]]], columns=["pm25", "pm10"])
            predicted_aqi = float(model.predict(features)[0])
        except Exception as e:
            print("PREDICT ERROR:", e)

    actual_aqi = float(env["aqi"])
    live_status = aqi_status_details(actual_aqi)
    forecast = forecast_next_3_days(predicted_aqi)

    return render_template(
        "dashboard.html",
        title="Dashboard",
        city=env["city"],
        latitude=env["latitude"],
        longitude=env["longitude"],
        temperature=round(float(env["temperature"]), 1),
        humidity=round(float(env["humidity"]), 1),
        description=env["description"].title(),
        pm25=round(float(env["pm25"]), 1),
        pm10=round(float(env["pm10"]), 1),
        actual_aqi=round(actual_aqi, 1),
        predicted_aqi=round(predicted_aqi, 1),
        forecast=forecast,
        last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        cache_bust=int(datetime.now().timestamp()),
        role=session.get("role", "citizen"),
        data_unavailable=False,
        live_status=live_status,
    )


@app.route("/municipal-dashboard")
def municipal_dashboard():
    ok, resp = require_municipal()
    if not ok:
        return resp

    conn = db_connect()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM burn_reports")
    total_reports = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM burn_reports WHERE status='Pending'")
    pending_reports = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM adopt_tree")
    total_adoptions = cur.fetchone()[0]

    cur.execute(
        """
        SELECT area, status, ts
        FROM burn_reports
        ORDER BY id DESC
        LIMIT 5
        """
    )
    recent_reports = cur.fetchall()

    conn.close()

    return render_template(
        "municipal.html",
        title="Municipal Dashboard",
        total_reports=total_reports,
        pending_reports=pending_reports,
        total_adoptions=total_adoptions,
        recent_reports=recent_reports,
    )


@app.route("/profile")
def profile():
    ok, resp = require_login()
    if not ok:
        return resp

    conn = db_connect()
    cur = conn.cursor()

    cur.execute("SELECT name, email, role FROM users WHERE id=?", (session["user_id"],))
    user = cur.fetchone()

    cur.execute(
        """
        SELECT district, area, location, tree_type, plant_date, purpose
        FROM adopt_tree
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (session["user_id"],),
    )
    adoptions = cur.fetchall()
    conn.close()

    if not user:
        session.clear()
        return redirect("/login")

    return render_template(
        "profile.html",
        title="Profile",
        user=user,
        adoptions=adoptions,
    )


@app.route("/adopt", methods=["GET", "POST"])
def adopt():
    ok, resp = require_login()
    if not ok:
        return resp

    if request.method == "POST":
        district = request.form.get("district", "").strip()
        area = request.form.get("area", "").strip()
        location = request.form.get("location", "").strip()
        tree_type = request.form.get("tree_type", "").strip()
        plant_date = request.form.get("plant_date", "").strip()
        purpose = request.form.get("purpose", "").strip()

        if not district or not area or not tree_type or not plant_date:
            flash("Please fill in district, area, tree type, and planting date.", "error")
        else:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO adopt_tree(user_id,district,area,location,tree_type,plant_date,purpose)
                VALUES(?,?,?,?,?,?,?)
                """,
                (session["user_id"], district, area, location, tree_type, plant_date, purpose),
            )
            conn.commit()
            conn.close()
            flash("Your tree adoption was submitted successfully.", "success")
            return redirect("/profile")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM districts ORDER BY name")
    districts = [r[0] for r in cur.fetchall()]
    conn.close()

    return render_template("adopt.html", title="Adopt Tree", districts=districts)


@app.route("/api/areas-by-district")
def areas_by_district():
    district = request.args.get("district", "").strip()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM areas WHERE district=? ORDER BY name", (district,))
    areas = [r[0] for r in cur.fetchall()]
    conn.close()
    return jsonify(areas)


@app.route("/report-burning", methods=["GET", "POST"])
def report_burning():
    ok, resp = require_login()
    if not ok:
        return resp

    if request.method == "POST":
        area = request.form.get("area", "").strip()
        note = request.form.get("note", "").strip()

        if not area:
            flash("Please enter the area or location.", "error")
            return render_template("report_burning.html", title="Report Burning")

        coords = geocode_area(area)
        if not coords:
            flash("Location not found. Try a nearby landmark or a clearer area name.", "error")
            return render_template("report_burning.html", title="Report Burning")

        lat, lon = coords

        file = request.files.get("photo")
        if not file or file.filename.strip() == "":
            flash("Please upload a photo for the report.", "error")
            return render_template("report_burning.html", title="Report Burning")

        filename = secure_filename(file.filename)
        filename = f"{int(datetime.now().timestamp())}_{filename}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        file.save(save_path)

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO burn_reports(user_id, area, lat, lon, photo_path, note, ml_label, confidence, status, ts)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                session["user_id"],
                area,
                lat,
                lon,
                save_path,
                note,
                "Likely Burning",
                0.75,
                "Pending",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        conn.close()

        flash("Your report was submitted. You can now track it in Hotspots.", "success")
        return redirect("/hotspots")

    return render_template("report_burning.html", title="Report Burning")


@app.route("/hotspots")
def hotspots():
    ok, resp = require_login()
    if not ok:
        return resp
    return render_template("hotspot.html", title="Hotspots")


@app.route("/api/burn-reports")
def api_burn_reports():
    ok, resp = require_login()
    if not ok:
        return resp

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, area, lat, lon, note, ml_label, confidence, status, ts
        FROM burn_reports
        ORDER BY id DESC
        LIMIT 200
        """
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify(
        [
            {
                "id": r[0],
                "area": r[1],
                "lat": r[2],
                "lon": r[3],
                "note": r[4],
                "label": r[5],
                "confidence": r[6],
                "status": r[7],
                "ts": r[8],
            }
            for r in rows
        ]
    )


@app.route("/api/aqi-now")
def api_aqi_now():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if not lat or not lon:
        return jsonify({"error": "lat/lon required"}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return jsonify({"error": "Invalid coordinates"}), 400

    data = get_aqi_by_coords(lat, lon)
    if not data:
        return jsonify({"error": "AQI fetch failed"}), 500

    aqi, pm25, pm10 = data
    return jsonify(
        {
            "lat": lat,
            "lon": lon,
            "aqi": float(aqi),
            "pm25": float(pm25),
            "pm10": float(pm10),
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


@app.route("/scan-grid")
def scan_grid():
    ok, resp = require_login()
    if not ok:
        return resp

    lat0 = request.args.get("lat")
    lon0 = request.args.get("lon")

    if lat0 and lon0:
        lat0 = float(lat0)
        lon0 = float(lon0)
        center_name = "HexGrid(GPS)"
    else:
        lat0, lon0 = 13.3409, 77.1010
        center_name = "HexGrid(Tumakuru)"

    step_km = float(request.args.get("step_km", 2.8))
    radius_km = float(request.args.get("radius_km", 8.0))

    horizontal_step_km = step_km
    vertical_step_km = step_km * 0.866

    dlat_base = vertical_step_km / 111.0
    dlon_base = horizontal_step_km / (111.0 * math.cos(math.radians(lat0)))
    half_dlon = dlon_base / 2.0

    row_count = int(radius_km / vertical_step_km)
    col_count = int(radius_km / horizontal_step_km)

    saved, failed = 0, 0

    for row in range(-row_count, row_count + 1):
        lat = lat0 + row * dlat_base
        row_offset = half_dlon if row % 2 != 0 else 0.0

        for col in range(-col_count, col_count + 1):
            lon = lon0 + (col * dlon_base) + row_offset

            dist = approx_distance_km(lat0, lon0, lat, lon)
            if dist > radius_km:
                continue

            aqi_data = get_aqi_by_coords(lat, lon)
            if not aqi_data:
                failed += 1
                continue

            aqi, pm25, pm10 = aqi_data
            save_pollution_point(f"{center_name}[{row},{col}]", lat, lon, aqi, pm25, pm10)
            saved += 1

    return jsonify({"saved": saved, "failed": failed})


@app.route("/api/aqi-zones")
def api_aqi_zones():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT city, latitude, longitude, aqi, pm25, pm10, ts
        FROM pollution
        ORDER BY id DESC
        LIMIT 1200
        """
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify(
        [
            {
                "city": r[0],
                "lat": r[1],
                "lon": r[2],
                "aqi": r[3],
                "pm25": r[4],
                "pm10": r[5],
                "ts": r[6],
            }
            for r in rows
        ]
    )


@app.route("/api/aqi-zones-near")
def api_aqi_zones_near():
    ok, resp = require_login()
    if not ok:
        return resp

    lat = request.args.get("lat")
    lon = request.args.get("lon")
    radius_km = float(request.args.get("radius_km", 20))

    if not lat or not lon:
        return jsonify({"error": "lat/lon required"}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return jsonify({"error": "invalid coordinates"}), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT city, latitude, longitude, aqi, pm25, pm10, ts
        FROM pollution
        ORDER BY id DESC
        LIMIT 3000
        """
    )
    rows = cur.fetchall()
    conn.close()

    filtered = []
    seen = set()

    for row in rows:
        city, plat, plon, aqi, pm25, pm10, ts = row

        if plat is None or plon is None:
            continue

        distance = approx_distance_km(lat, lon, float(plat), float(plon))
        if distance <= radius_km:
            key = (round(float(plat), 3), round(float(plon), 3))
            if key in seen:
                continue
            seen.add(key)

            filtered.append(
                {
                    "city": city,
                    "lat": float(plat),
                    "lon": float(plon),
                    "aqi": float(aqi),
                    "pm25": float(pm25) if pm25 is not None else None,
                    "pm10": float(pm10) if pm10 is not None else None,
                    "ts": ts,
                    "distance_km": round(distance, 2),
                }
            )

    return jsonify(filtered)


@app.route("/map")
def map_view():
    ok, resp = require_login()
    if not ok:
        return resp
    return render_template("map.html", title="Map View")


@app.route("/green-route")
def green_route():
    ok, resp = require_login()
    if not ok:
        return resp
    return render_template("green_route.html", title="Green Route")


if __name__ == "__main__":
    ensure_tables()
    seed_districts()
    app.run(debug=True)
