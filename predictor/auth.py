from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, RadioField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

from .extensions import db
from .models import User

bp = Blueprint("auth", __name__)


class SignupForm(FlaskForm):
    username = StringField("Username", validators=[
        DataRequired(), Length(3, 30),
        Regexp(r"^[A-Za-z0-9_.-]+$", message="Use letters, numbers, dots, dashes or underscores."),
    ])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField("Confirm password", validators=[
        DataRequired(), EqualTo("password", message="Passwords must match."),
    ])
    role = RadioField("I am a", default="student", validators=[DataRequired()], choices=[
        ("student", "Student"), ("teacher", "Teacher (can analyse a whole class)"),
    ])


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])


def leave_or_redirect():
    """Signed-in users skip the auth pages; demo users are signed out first."""
    if not current_user.is_authenticated:
        return None
    if current_user.is_demo:
        logout_user()
        return None
    return redirect(url_for("dashboard.index"))


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if redirect_response := leave_or_redirect():
        return redirect_response
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if db.session.execute(db.select(User).filter_by(username=username)).scalar():
            form.username.errors.append("That username is taken.")
        else:
            user = User(username=username, role=form.role.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("signup.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if redirect_response := leave_or_redirect():
        return redirect_response
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            db.select(User).filter_by(username=form.username.data.strip())
        ).scalar()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("dashboard.index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
