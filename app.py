import os
from datetime import date
from datetime import datetime, timedelta
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///userinfo.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide an username", 400)
        elif not request.form.get("password"):
            return apology("must provide a password", 400)
        elif not request.form.get("confirmation"):
            return apology("must provide a confirmation of password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 400)
        elif not request.form.get("weight"):
            return apology("must provide your weight in kg", 400)
        elif not request.form.get("height"):
            return apology("must provide your height in cms", 400)
        elif not request.form.get("age"):
            return apology("must provide your age", 400)
        elif not request.form.get("gender"):
            return apology("must provide your gender", 400)

        rows = db.execute("SELECT * FROM Users WHERE username = ?", request.form.get("username"))
        if len(rows) != 0:
            return apology("username already exists", 400)

        db.execute(
            "INSERT INTO Users (username, password) VALUES (?, ?)",
            request.form.get("username"), generate_password_hash(request.form.get("password"))
        )

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        db.execute(
            "INSERT INTO UserInformation (user_id, weight, height, age, gender) VALUES (?, ?, ?, ?, ?)",
            str(rows[0]["user_id"]), request.form.get("weight"), request.form.get("height"), request.form.get("age"), request.form.get("gender")
        )


        return redirect("/success")

    else:
        return render_template("register.html")

@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":


        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        rows = db.execute("SELECT * FROM Users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["password"], request.form.get("password")):
            return apology("invalid username and/or password", 403)


        # Remember which user has logged in
        session["user_id"] = rows[0]["user_id"]
        session["username"] = rows[0]["username"]


        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/")
@login_required
def index():
    # Retrieve user information from the database
    user_id = session["user_id"]
    user_data = db.execute("SELECT weight, height, age, target_bmi, target_date, target_weight FROM UserInformation WHERE user_id = ?", user_id)[0]
    name = session["username"]
    weight = user_data["weight"]
    height = user_data["height"] / 100  # Convert height to meters
    bmi = weight / (height * height)
    db.execute("UPDATE UserInformation SET bmi = ? WHERE user_id = ?", bmi, user_id)

    # Add calculated BMI to user_data dictionary
    user_data["bmi"] = bmi

    # Set target_bmi to 0 if it's None
    target_bmi = user_data["target_bmi"]
    if target_bmi is None:
        target_bmi = 0

    # Calculate progress towards the target BMI
    if target_bmi > 0:
        progress = round((bmi / target_bmi) * 100, 2)
        user_data["progress"] = progress

    return render_template("index.html", name=name, user_data=user_data)

@app.route("/get_user_data")
@login_required
def get_user_data():
    user_id = session["user_id"]
    user_data = db.execute("SELECT * FROM UserInformation WHERE user_id = ?", user_id)[0]
    return jsonify(user_data)


@app.route("/set_target", methods=["POST"])
@login_required
def set_target():
    # Retrieve user information from the database
    user_id = session["user_id"]
    user_data = db.execute("SELECT weight, height, age FROM UserInformation WHERE user_id = ?", user_id)[0]

    target_weight = float(request.form.get("target_weight"))
    target_date = request.form.get("target_date")

    # Calculate target BMI
    height = user_data["height"] / 100  # Convert height to meters
    target_bmi = target_weight / (height * height)

    # Update the target BMI, target weight, and target date in the database
    db.execute("UPDATE UserInformation SET target_bmi = ?, target_weight = ?, target_date = ? WHERE user_id = ?", target_bmi, target_weight, target_date, user_id)

    return redirect("/")

@app.route("/calorie", methods=["GET"])
@login_required
def calorie_chart():
    user_id = session["user_id"]

    # Calculate the date 10 days ago from today
    ten_days_ago = datetime.now() - timedelta(days=10)

    # Fetch calorie intake data for the past 10 days from the database
    calorie_data = db.execute(
        "SELECT DISTINCT intake_date, SUM(calories) as total_calories FROM CalorieIntake WHERE user_id = ? AND intake_date >= ? GROUP BY intake_date ORDER BY intake_date",
        user_id, ten_days_ago.strftime('%Y-%m-%d')
    )

    return render_template("calorie.html", calorie_data=calorie_data)

@app.route("/subtract_calorie", methods=["POST"])
@login_required
def subtract_calorie():
    if request.method == "POST":
        user_id = session["user_id"]
        intake_date = request.form.get("intake_date")
        subtract_calories = int(request.form.get("calories"))

        # Subtract the calorie intake data from the CalorieIntake table
        db.execute("INSERT INTO CalorieIntake (user_id, intake_date, calories) VALUES (?, ?, ?)",
                   user_id, intake_date, -subtract_calories)

        return redirect("/calorie")

@app.route("/submit_calorie", methods=["POST"])
@login_required
def submit_calorie():
    if request.method == "POST":
        user_id = session["user_id"]
        intake_date = request.form.get("intake_date")
        calories = int(request.form.get("calories"))

        # Insert the calorie intake data into the CalorieIntake table manually
        db.execute("INSERT INTO CalorieIntake (user_id, intake_date, calories) VALUES (?, ?, ?)",
                   user_id, intake_date, calories)

        return redirect("/calorie")

@app.route("/science")
@login_required
def science_workouts():
    return render_template("science.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    username = session["username"]
    user_data = db.execute("SELECT * FROM UserInformation WHERE user_id = ?", user_id)[0]

    if request.method == "POST":
        height = request.form.get("height")
        weight = request.form.get("weight")
        # Get other form fields here

        # Update the user's profile information in the database
        db.execute("UPDATE UserInformation SET height = ?, weight = ? WHERE user_id = ?", height, weight, user_id)
        # Update other profile information in the same way

        flash("Profile updated successfully!")
        return redirect("/profile")

    return render_template("profile.html", user_data=user_data, username=username)

@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    user_id = session["user_id"]
    height = request.form.get("height")
    weight = request.form.get("weight")
    # Get other form fields here

    # Update the user's profile information in the database
    db.execute("UPDATE UserInformation SET height = ?, weight = ? WHERE user_id = ?", height, weight, user_id)
    # Update other profile information in the same way

    flash("Profile updated successfully!")
    return redirect("/profile")

@app.route("/update_records", methods=["POST"])
@login_required
def update_records():
    user_id = session["user_id"]
    bench_press_pr = request.form.get("bench_press_pr")
    squats_pr = request.form.get("squats_pr")
    deadlifts_pr = request.form.get("deadlifts_pr")
    # Get other form fields for personal records

    # Update personal records in the database
    db.execute("UPDATE UserInformation SET bench_press_pr = ?, squats_pr = ?, deadlifts_pr = ? WHERE user_id = ?",
               bench_press_pr, squats_pr, deadlifts_pr, user_id)
    # Update other personal records in the same way

    flash("Personal records updated successfully!")
    return redirect("/profile")