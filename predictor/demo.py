"""One-click demo accounts so visitors can explore without signing up.

Every click creates a private, pre-filled throwaway account, so visitors never
see (or break) each other's data. Demo accounts are deleted after 24 hours.
"""

import secrets
from datetime import timedelta

from flask import Blueprint, abort, redirect, url_for
from flask_login import login_user

from .config import BASE_DIR
from .extensions import db
from .ml.batch import predict_class, read_class_csv
from .ml.inference import get_predictor
from .models import ClassReport, Prediction, User, utcnow

bp = Blueprint("demo", __name__, url_prefix="/demo")

DEMO_TTL = timedelta(hours=24)
MAX_DEMO_USERS = 200
DEMO_CLASS_CSV = BASE_DIR / "data" / "demo_class.csv"

# A student improving week by week
STUDENT_JOURNEY = [
    {"period1_score": 48, "period2_score": 50, "study_hours": 2, "absences": 14, "goout": 5},
    {"period1_score": 55, "period2_score": 58, "study_hours": 4, "absences": 10, "goout": 4},
    {"period1_score": 62, "period2_score": 66, "study_hours": 6, "absences": 6, "goout": 3},
    {"period1_score": 68, "period2_score": 74, "study_hours": 8, "absences": 4, "goout": 3},
]
STUDENT_DEFAULTS = {"subject": "math", "failures": 0, "health": 4, "higher": "yes",
                    "internet": "yes"}


def purge_demo_users() -> None:
    """Delete expired demo accounts, and the oldest ones beyond the cap."""
    expired = db.select(User).where(User.is_demo, User.created_at < utcnow() - DEMO_TTL)
    for user in db.session.scalars(expired):
        db.session.delete(user)
    db.session.flush()

    keep = MAX_DEMO_USERS - 1  # leave room for the account about to be created
    surplus = db.select(User).where(User.is_demo).order_by(User.created_at.desc()).offset(keep)
    for user in db.session.scalars(surplus):
        db.session.delete(user)


def seed_student(user: User) -> None:
    predictor = get_predictor()
    now = utcnow()
    for weeks_ago, step in zip(range(len(STUDENT_JOURNEY) - 1, -1, -1), STUDENT_JOURNEY,
                               strict=True):
        values = {**STUDENT_DEFAULTS, **step}
        result = predictor.predict(values)
        db.session.add(Prediction(
            user=user, created_at=now - timedelta(weeks=weeks_ago), **values,
            predicted_score=result.score, lower=result.lower, upper=result.upper,
            grade=result.grade,
            explanation={"impacts": [vars(i) for i in result.impacts],
                         "recommendations": [vars(r) for r in result.recommendations]},
        ))


def seed_class(user: User) -> ClassReport:
    records, errors = read_class_csv(DEMO_CLASS_CSV.read_text(encoding="utf-8"))
    assert not errors, errors
    report = ClassReport(teacher=user, name="Demo class · Term 2", rows=predict_class(records))
    db.session.add(report)
    return report


@bp.route("/<role>", methods=["POST"])
def start(role: str):
    if role not in {"student", "teacher"}:
        abort(404)
    purge_demo_users()

    user = User(username=f"demo-{secrets.token_hex(4)}", role=role, is_demo=True)
    user.set_password(secrets.token_urlsafe(32))  # nobody can log in with it
    db.session.add(user)
    seed_student(user)
    report = seed_class(user) if role == "teacher" else None
    db.session.commit()

    login_user(user)
    if report is not None:
        return redirect(url_for("classroom.report", report_id=report.id))
    latest = user.predictions[0]
    return redirect(url_for("dashboard.index", result=latest.id) + "#result")
