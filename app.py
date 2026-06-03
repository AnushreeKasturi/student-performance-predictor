from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import plotly.express as px
import sqlite3

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression

# Load dataset
data = pd.read_csv("student_data.csv")

# Input features
X = data[['attendance', 'study_hours', 'internal_marks', 'assignments']]

# Output target
y = data['final_score']

# Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = LinearRegression()
model.fit(X_train, y_train)
fig = px.scatter(
    data,
    x="study_hours",
    y="final_score",
    title="Study Hours vs Final Score",
    template="plotly_dark"
)
fig.update_layout(
    width=400,
    height=350,
    margin=dict(l=20, r=20, t=40, b=20)
)

graph_html = fig.to_html(
    full_html=False,
    config={'displayModeBar': False}
)

# Create Flask app
app = Flask(__name__)
app.secret_key = "mysecretkey"

# Connect to SQLite database
conn = sqlite3.connect("predictions.db", check_same_thread=False)

cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS predictions (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    attendance REAL,

    study_hours REAL,

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

conn.commit()



# Home page
@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
     return redirect(url_for("login"))

    prediction = None
    grade = None

    # When user submits form
    if request.method == "POST":

        # Get input values from form
        attendance = float(request.form["attendance"])
        study_hours = float(request.form["study_hours"])
        internal_marks = float(request.form["internal_marks"])
        assignments = float(request.form["assignments"])

        # Convert into DataFrame
        new_data = pd.DataFrame({
            'attendance': [attendance],
            'study_hours': [study_hours],
            'internal_marks': [internal_marks],
            'assignments': [assignments]
        })

        # Predict score
        prediction = round(model.predict(new_data)[0], 2)

                # Grade logic
        if prediction >= 90:
            grade = "A"

        elif prediction >= 80:
            grade = "B"

        elif prediction >= 70:
            grade = "C"

        else:
            grade = "Fail"

        # Save prediction to database
               # Save prediction to database
        cursor.execute("""
        INSERT INTO predictions (

            user_id,
            attendance,
            study_hours,
            predicted_score,
            grade

        )

        VALUES (?, ?, ?, ?, ?)
        """, (

            session["user_id"],
            attendance,
            study_hours,
            prediction,
            grade

        ))

        conn.commit()
        return redirect(url_for("home"))

    # Load prediction history
    cursor.execute("""
SELECT attendance, study_hours, predicted_score, grade
FROM predictions
WHERE user_id=?
ORDER BY id DESC
""", (session["user_id"],))

    history = cursor.fetchall()
    # Send prediction to HTML page
    return render_template(
    "index.html",
    prediction=prediction,
    grade=grade,
    history=history,
    graph_html=graph_html
)
@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        try:
            cursor.execute("""
            INSERT INTO users (username, password)
            VALUES (?, ?)
            """, (username, password))

            conn.commit()

            return redirect(url_for("login"))

        except:
            return "Username already exists!"

    return render_template("signup.html")
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        cursor.execute("""
        SELECT * FROM users
        WHERE username=? AND password=?
        """, (username, password))

        user = cursor.fetchone()

        if user:

            session["user"] = username
            session["user_id"] = user[0]

            return redirect(url_for("home"))

        else:
            return "Invalid username or password"

    return render_template("login.html")
@app.route("/logout")
def logout():

    session.pop("user", None)
    session.pop("user_id", None)

    return redirect(url_for("login"))

# Run app
if __name__ == "__main__":
    app.run(debug=True)