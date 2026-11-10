import logging
import os
import secrets
import sqlite3

import pandas as pd
import plotly.express as px
from flask import Flask, flash, redirect, render_template, request, session, url_for
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from werkzeug.security import check_password_hash, generate_password_hash

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DATABASE = os.environ.get("DATABASE_PATH", "predictions.db")

FEATURES = ["attendance", "study_hours", "internal_marks", "assignments"]

# Allowed range for every model input: field -> (label, min, max)
INPUT_RULES = {
    "attendance": ("Attendance %", 0, 100),
    "study_hours": ("Study hours per day", 0, 24),
    "internal_marks": ("Internal marks", 0, 100),
    "assignments": ("Assignment marks", 0, 100),
}

MIN_PASSWORD_LENGTH = 6

# ---------------------------------------------------------------- model

data = pd.read_csv("student_data.csv")

X = data[FEATURES]
y = data["final_score"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = LinearRegression()
model.fit(X_train, y_train)

fig = px.scatter(
    data,
    x="study_hours",
    y="final_score",
    title="Study Hours vs Final Score",
    template="plotly_dark",
    trendline="ols",
)
fig.update_layout(
    autosize=True,
    height=450,
    paper_bgcolor="#1e1e1e",
    plot_bgcolor="#1e1e1e",
    font=dict(color="white", size=14),
    title_font=dict(size=22),
    margin=dict(l=20, r=20, t=50, b=20),
)
fig.update_traces(marker=dict(size=10))

graph_html = fig.to_html(full_html=False, config={"displayModeBar": False})


def predict_score(values):
    """Predict the final score for a dict of inputs, kept within 0-100."""
    frame = pd.DataFrame({name: [values[name]] for name in FEATURES})
    score = float(model.predict(frame)[0])
    return round(min(max(score, 0.0), 100.0), 2)


def grade_for(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "Fail"


def parse_inputs(form):
    """Validate the prediction form. Returns (values, errors)."""
    values, errors = {}, []

    for name, (label, low, high) in INPUT_RULES.items():
        raw = (form.get(name) or "").strip()

        try:
            number = float(raw)
        except ValueError:
            errors.append(f"{label} must be a number.")
            continue

        # NaN fails both comparisons, so it is rejected here too
        if not (low <= number <= high):
            errors.append(f"{label} must be between {low} and {high}.")
            continue

        values[name] = number

    return values, errors


# ------------------------------------------------------------------ app

app = Flask(__name__)

secret_key = os.environ.get("SECRET_KEY")

if not secret_key:
    # Still safe, but every restart logs all users out.
    secret_key = secrets.token_hex(32)
    log.warning("SECRET_KEY is not set - using a temporary random key.")

app.secret_key = secret_key
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# ------------------------------------------------------------- database

conn = sqlite3.connect(DATABASE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    attendance REAL,
    study_hours REAL,
    internal_marks REAL,
    assignments REAL,
    predicted_score REAL,
    grade TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")

# Databases created before all four inputs were stored need the new columns
existing_columns = {
    row[1] for row in cursor.execute("PRAGMA table_info(predictions)")
}

for column in ("internal_marks", "assignments"):
    if column not in existing_columns:
        cursor.execute(f"ALTER TABLE predictions ADD COLUMN {column} REAL")

conn.commit()

# --------------------------------------------------------------- routes


@app.route("/", methods=["GET", "POST"])
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        values, errors = parse_inputs(request.form)

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("home"))

        prediction = predict_score(values)
        grade = grade_for(prediction)

        cursor.execute(
            """
            INSERT INTO predictions (
                user_id, attendance, study_hours,
                internal_marks, assignments, predicted_score, grade
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                values["attendance"],
                values["study_hours"],
                values["internal_marks"],
                values["assignments"],
                prediction,
                grade,
            ),
        )
        conn.commit()

        # Shown once on the page we redirect to
        session["last_result"] = {"prediction": prediction, "grade": grade}
        return redirect(url_for("home"))

    result = session.pop("last_result", None)

    cursor.execute(
        """
        SELECT attendance, study_hours, internal_marks, assignments,
               predicted_score, grade
        FROM predictions
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (session["user_id"],),
    )
    history = cursor.fetchall()

    if history:
        scores = [item[4] for item in history]
        average_score = round(sum(scores) / len(scores), 2)
        highest_score = max(scores)
        latest_grade = history[0][5]
    else:
        average_score = 0
        highest_score = 0
        latest_grade = "-"

    return render_template(
        "index.html",
        result=result,
        history=history,
        graph_html=graph_html,
        rules=INPUT_RULES,
        total_predictions=len(history),
        average_score=average_score,
        highest_score=highest_score,
        latest_grade=latest_grade,
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username:
            flash("Username is required.", "error")
            return redirect(url_for("signup"))

        if len(password) < MIN_PASSWORD_LENGTH:
            flash(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
                "error",
            )
            return redirect(url_for("signup"))

        try:
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            flash("That username is already taken.", "error")
            return redirect(url_for("signup"))

        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        cursor.execute(
            "SELECT id, username, password FROM users WHERE username=?",
            (username,),
        )
        user = cursor.fetchone()

        if user and check_password_hash(user[2], password):
            session.clear()
            session["user"] = user[1]
            session["user_id"] = user[0]
            return redirect(url_for("home"))

        flash("Invalid username or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
