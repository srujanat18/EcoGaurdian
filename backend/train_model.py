import os
import sqlite3
import pandas as pd
import pickle

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "database.db")
MODEL_PATH = os.path.join(BASE_DIR, "pollution_model.pkl")


def main():
    if not os.path.exists(DB_PATH):
        print("❌ database.db not found.")
        return

    conn = sqlite3.connect(DB_PATH)

    query = "SELECT aqi, pm25, pm10 FROM pollution"
    df = pd.read_sql_query(query, conn)
    conn.close()

    df = df.dropna()

    if len(df) < 5:
        print("❌ Not enough data to train. Add more pollution records.")
        print("Current rows:", len(df))
        return

    X = df[["pm25", "pm10"]]
    y = df["aqi"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    print("📊 Model trained successfully!")
    print("Rows used:", len(df))

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    print("✅ Model saved at:", MODEL_PATH)


if __name__ == "__main__":
    main()
