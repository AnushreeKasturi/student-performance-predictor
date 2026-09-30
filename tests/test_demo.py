from datetime import timedelta

from predictor import demo
from predictor.extensions import db
from predictor.models import ClassReport, Prediction, User, utcnow

from .conftest import signup_and_login


def demo_users(app):
    with app.app_context():
        return db.session.scalars(db.select(User).where(User.is_demo)).all()


def test_student_demo_is_prefilled_and_logged_in(app, client):
    response = client.post("/demo/student")
    assert response.status_code == 302
    assert "result=" in response.headers["Location"]

    page = client.get(response.headers["Location"]).data
    assert b"exploring a demo account" in page
    assert b"Why this score?" in page
    assert b"plotly" in page  # trend chart needs 2+ predictions
    with app.app_context():
        user = db.session.scalars(db.select(User).where(User.is_demo)).one()
        assert user.role == "student"
        assert len(user.predictions) == len(demo.STUDENT_JOURNEY)


def test_teacher_demo_lands_on_class_report(app, client):
    response = client.post("/demo/teacher")
    assert "/class/" in response.headers["Location"]
    page = client.get(response.headers["Location"]).data
    assert b"Demo class" in page and b"Elif" in page


def test_each_visitor_gets_a_private_account(app, client):
    client.post("/demo/student")
    client.post("/logout")
    client.post("/demo/student")
    users = demo_users(app)
    assert len(users) == 2
    assert users[0].username != users[1].username


def test_unknown_role_is_404(client):
    assert client.post("/demo/admin").status_code == 404


def test_demo_requires_post(client):
    assert client.get("/demo/student").status_code == 405


def test_expired_demo_accounts_are_purged(app, client):
    signup_and_login(client, "real_user")
    client.post("/logout")
    client.post("/demo/teacher")
    with app.app_context():
        old = db.session.scalars(db.select(User).where(User.is_demo)).one()
        old.created_at = utcnow() - timedelta(hours=25)
        db.session.commit()

    client.post("/logout")
    client.post("/demo/student")
    with app.app_context():
        usernames = {u.username for u in db.session.scalars(db.select(User))}
        assert "real_user" in usernames
        assert len(usernames) == 2  # the real user + the new demo user
        # the expired account's data went with it
        assert db.session.query(ClassReport).count() == 0
        assert db.session.query(Prediction).count() == len(demo.STUDENT_JOURNEY)


def test_demo_user_cap(app, client, monkeypatch):
    monkeypatch.setattr(demo, "MAX_DEMO_USERS", 3)
    for _ in range(5):
        client.post("/demo/student")
        client.post("/logout")
    assert len(demo_users(app)) == 3


def test_signup_link_signs_demo_user_out(client):
    client.post("/demo/student")
    page = client.get("/signup")
    assert page.status_code == 200
    assert b"Create account" in page.data
    assert client.get("/").status_code == 302  # no longer logged in
