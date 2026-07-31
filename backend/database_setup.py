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

conn.commit()
conn.close()

print("Database Created Successfully ✅")
