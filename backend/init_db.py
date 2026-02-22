import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "database.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# -----------------------------
# USERS TABLE
# -----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    role TEXT
)
""")

# -----------------------------
# POLLUTION TABLE
# -----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS pollution (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aqi REAL,
    pm25 REAL,
    pm10 REAL
)
""")

# Insert sample pollution data (only if empty)
cursor.execute("SELECT COUNT(*) FROM pollution")
if cursor.fetchone()[0] == 0:
    data = [
        (120, 55, 80),
        (90, 40, 60),
        (150, 70, 95),
        (200, 110, 140),
        (60, 20, 35),
        (180, 95, 120)
    ]
    cursor.executemany(
        "INSERT INTO pollution (aqi, pm25, pm10) VALUES (?, ?, ?)",
        data
    )

# -----------------------------
# ADOPT TREE TABLE
# -----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS adopt_tree (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    location TEXT
)
""")

conn.commit()
conn.close()

print("✅ All tables created successfully!")
