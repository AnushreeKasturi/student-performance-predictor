from datetime import UTC, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="student")
    is_demo = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    predictions = db.relationship(
        "Prediction", back_populates="user", cascade="all, delete-orphan",
        order_by="Prediction.created_at.desc()",
    )
    class_reports = db.relationship(
        "ClassReport", back_populates="teacher", cascade="all, delete-orphan",
        order_by="ClassReport.created_at.desc()",
    )

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    # Inputs
    subject = db.Column(db.String(20), nullable=False)
    period1_score = db.Column(db.Float, nullable=False)
    period2_score = db.Column(db.Float, nullable=False)
    study_hours = db.Column(db.Float, nullable=False)
    absences = db.Column(db.Float, nullable=False)
    failures = db.Column(db.Float, nullable=False)
    goout = db.Column(db.Float, nullable=False)
    health = db.Column(db.Float, nullable=False)
    higher = db.Column(db.String(3), nullable=False)
    internet = db.Column(db.String(3), nullable=False)

    # Outputs
    predicted_score = db.Column(db.Float, nullable=False)
    lower = db.Column(db.Float, nullable=False)
    upper = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(2), nullable=False)
    explanation = db.Column(db.JSON, nullable=False, default=dict)

    user = db.relationship("User", back_populates="predictions")

    INPUT_FIELDS = ("subject", "period1_score", "period2_score", "study_hours", "absences",
                    "failures", "goout", "health", "higher", "internet")

    def inputs(self) -> dict:
        return {name: getattr(self, name) for name in self.INPUT_FIELDS}


class ClassReport(db.Model):
    """A teacher's batch of predictions for a whole class, from one CSV upload."""

    __tablename__ = "class_reports"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    rows = db.Column(db.JSON, nullable=False, default=list)

    teacher = db.relationship("User", back_populates="class_reports")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))
