# backend/app.py

from flask import Flask, render_template, request, redirect, session
import sqlite3
import requests
import pickle
import os
import pandas as pd

# graph
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import date, timedelta

# -----------------------------
# CONFIG
# -----------------------------
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "database.db")
MODEL_PATH = os.path.join(BASE_DIR, "pollution_model.pkl")

# ✅ Your OpenWeather API key
API_KEY = "7d23b6f823c1037a16b419811a72faa8"

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = "secret123"


# -----------------------------
# DB: Ensure tables exist
# -----------------------------
def ensure_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # pollution history
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pollution(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT,
        aqi REAL,
        pm25 REAL,
        pm10 REAL,
        temperature REAL,
        humidity REAL,
        date TEXT
    )
    """)

    # adopt tree
    cur.execute("""
    CREATE TABLE IF NOT EXISTS adopt_tree(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        location TEXT
    )
    """)

    conn.commit()
    conn.close()


# -----------------------------
# ML model loader
# -----------------------------
def load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


# -----------------------------
# Save today's environment to DB (for graphs)
# -----------------------------
def save_today_to_db(city, aqi, pm25, pm10, temperature=None, humidity=None):
    today = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # avoid duplicates for same city+date
    cur.execute("SELECT id FROM pollution WHERE city=? AND date=?", (city, today))
    exists = cur.fetchone()

    if not exists:
        cur.execute(
            """INSERT INTO pollution (city, aqi, pm25, pm10, temperature, humidity, date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (city, aqi, pm25, pm10, temperature, humidity, today)
        )
        conn.commit()

    conn.close()


def get_last_7_days(city):
    """Return list of (date, aqi) for last 7 entries."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT date, aqi
            FROM pollution
            WHERE city=?
            ORDER BY date DESC
            LIMIT 7
        """, (city,))
        rows = cur.fetchall()
    except Exception as e:
        print("DB ERROR (get_last_7_days):", e)
        rows = []
    conn.close()

    rows.reverse()  # oldest -> newest
    return rows


def make_trend_graph(rows):
    img_path = os.path.join(app.static_folder, "pollution_trend.png")

    # If not enough history, create a simple placeholder chart
    if not rows or len(rows) < 2:
        plt.figure(figsize=(8, 3.2))
        plt.title("Air Quality Trend (Last 7 Days)")
        plt.xlabel("Date")
        plt.ylabel("Air Quality Level")
        plt.text(0.5, 0.5, "Not enough history yet.\nCheck back after 2+ days.",
                 ha="center", va="center", fontsize=12)
        plt.tight_layout()
        plt.savefig(img_path)
        plt.close()
        return

    dates = [r[0] for r in rows]
    values = [r[1] for r in rows]

    plt.figure(figsize=(8, 3.2))
    plt.plot(dates, values, marker="o")
    plt.xticks(rotation=20)
    plt.title("Air Quality Trend (Last 7 Days)")
    plt.xlabel("Date")
    plt.ylabel("Air Quality Level")
    plt.tight_layout()
    plt.savefig(img_path)
    plt.close()

def forecast_next_3_days(predicted_today):
    """Simple future prediction cards (demo-friendly)."""
    today = date.today()
    out = []
    for i in range(1, 4):
        d = today + timedelta(days=i)

        # small variation
        pred = float(predicted_today) + (i * 2)

        out.append({
            "day": d.strftime("%a"),
            "pred": round(pred, 1)
        })
    return out


# -----------------------------
# LIVE WEATHER + POLLUTION (City)
# -----------------------------
def get_live_environment(city="Bengaluru"):
    try:
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
        w = requests.get(weather_url, timeout=10).json()

        if str(w.get("cod")) != "200":
            print("WEATHER ERROR (CITY):", w)
            return None

        lat = w["coord"]["lat"]
        lon = w["coord"]["lon"]

        temperature = w["main"]["temp"]
        humidity = w["main"]["humidity"]
        description = w["weather"][0]["description"]
        real_city = w.get("name", city)

        pollution_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        p = requests.get(pollution_url, timeout=10).json()

        if "list" not in p:
            print("POLLUTION ERROR (CITY):", p)
            return None

        aqi = p["list"][0]["main"]["aqi"]
        pm25 = p["list"][0]["components"]["pm2_5"]
        pm10 = p["list"][0]["components"]["pm10"]

        return {
    "city": city,
    "latitude": round(float(lat), 5),
    "longitude": round(float(lon), 5),
    "temperature": temperature,
    "humidity": humidity,
    "description": description,
    "aqi": aqi,
    "pm25": pm25,
    "pm10": pm10
}
    except Exception as e:
        print("API EXCEPTION (CITY):", e)
        return None


# -----------------------------
# LIVE WEATHER + POLLUTION (GPS coords)
# -----------------------------
def get_live_environment_by_coords(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)

        weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        w = requests.get(weather_url, timeout=10).json()

        print("GPS WEATHER RESPONSE:", w)

        if str(w.get("cod")) != "200":
            print("WEATHER ERROR (GPS):", w)
            return None

        city = w.get("name", "Your Location")
        temperature = w["main"]["temp"]
        humidity = w["main"]["humidity"]
        description = w["weather"][0]["description"]

        pollution_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        p = requests.get(pollution_url, timeout=10).json()

        print("GPS POLLUTION RESPONSE:", p)

        if "list" not in p:
            print("POLLUTION ERROR (GPS):", p)
            return None

        aqi = p["list"][0]["main"]["aqi"]
        pm25 = p["list"][0]["components"]["pm2_5"]
        pm10 = p["list"][0]["components"]["pm10"]

        return {
            "city": city,
            "temperature": temperature,
            "humidity": humidity,
            "description": description,
            "aqi": aqi,
            "pm25": pm25,
            "pm10": pm10
        }

    except Exception as e:
        print("API EXCEPTION (GPS):", e)
        return None


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                (name, email, password, role)
            )
            conn.commit()
        except Exception as e:
            print("REGISTER ERROR:", e)
        conn.close()

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["role"] = user[4]
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    lat = request.args.get("lat")
    lon = request.args.get("lon")
    city = request.args.get("city")

    print("DASHBOARD PARAMS => lat:", lat, "lon:", lon, "city:", city)

    # GPS first
    if lat and lon:
        env = get_live_environment_by_coords(lat, lon)
    # manual city override
    elif city:
        env = get_live_environment(city)
    # default
    else:
        env = get_live_environment("Bengaluru")

    if env is None:
        return "⚠ API Error. Check terminal output."

    # Save today's data for 7-day graph
    save_today_to_db(
        env["city"],
        env["aqi"],
        env["pm25"],
        env["pm10"],
        env.get("temperature"),
        env.get("humidity")
    )

    # Predict air-quality value using ML model (if model exists)
    model = load_model()
    if model:
        # Your current model expects pm25, pm10 (matches earlier training)
        X = pd.DataFrame([[env["pm25"], env["pm10"]]], columns=["pm25", "pm10"])
        predicted = float(model.predict(X)[0])
    else:
        predicted = float(env["aqi"])  # fallback
    predicted_aqi = predicted
    # graph: last 7 days + save image
    rows = get_last_7_days(env["city"])
    make_trend_graph(rows)

    # future cards (next 3 days)
    forecast = forecast_next_3_days(predicted)

    return render_template(
    "dashboard.html",
    city=env["city"],
    latitude=env.get("latitude"),
    longitude=env.get("longitude"),
    temperature=env["temperature"],
    humidity=env["humidity"],
    description=env["description"],
    pm25=env["pm25"],
    pm10=env["pm10"],
    actual_aqi=env["aqi"],
    predicted_aqi=round(predicted_aqi, 2),
    forecast=forecast
)

@app.route("/adopt", methods=["GET", "POST"])
def adopt():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        location = request.form["location"]

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO adopt_tree (user_id, location) VALUES (?, ?)",
                    (session["user_id"], location))
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("adopt_tree.html")


@app.route("/municipal")
def municipal():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("municipal.html")


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name, email, role FROM users WHERE id=?", (session["user_id"],))
    user = cur.fetchone()

    cur.execute("SELECT location FROM adopt_tree WHERE user_id=? ORDER BY id DESC", (session["user_id"],))
    adoptions = cur.fetchall()

    conn.close()

    return render_template(
        "profile.html",
        name=user[0] if user else "",
        email=user[1] if user else "",
        role=user[2] if user else "",
        adoptions=adoptions
    )


@app.route("/awareness")
def awareness():
    return render_template("awareness.html")


@app.route("/emission")
def emission():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("emission_test.html")


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    ensure_tables()
    app.run(debug=True)
