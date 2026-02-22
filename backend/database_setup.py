import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Users Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    role TEXT
)
""")

# Pollution Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS pollution (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT,
    aqi INTEGER,
    pm25 REAL,
    pm10 REAL,
    date TEXT
)
""")

# Trees Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS trees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    location TEXT,
    tree_type TEXT,
    date TEXT
)
""")

conn.commit()
conn.close()

print("Database Created Successfully ✅")
