from predictor.extensions import db
from predictor.models import User

from .conftest import signup_and_login


def test_dashboard_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_signup_stores_hashed_password(app, client):
    signup_and_login(client)
    with app.app_context():
        user = db.session.execute(db.select(User)).scalar_one()
        assert user.username == "alice"
        assert user.password_hash != "correct-horse"
        assert user.check_password("correct-horse")


def test_login_then_dashboard(client):
    response = signup_and_login(client)
    assert response.status_code == 302
    assert b"Predict a final score" in client.get("/").data


def test_duplicate_username_rejected(client):
    signup_and_login(client)
    client.post("/logout")
    response = client.post("/signup", data={
        "username": "alice", "password": "another-pass", "confirm": "another-pass",
    })
    assert b"That username is taken." in response.data


def test_short_password_rejected(client):
    data = {"username": "bob", "password": "short", "confirm": "short"}
    response = client.post("/signup", data=data)
    assert b"at least 8" in response.data


def test_wrong_password(client):
    signup_and_login(client)
    client.post("/logout")
    response = client.post("/login", data={"username": "alice", "password": "wrong-password"},
                           follow_redirects=True)
    assert b"Invalid username or password." in response.data


def test_logout_requires_post(logged_in):
    assert logged_in.get("/logout").status_code == 405
    assert logged_in.post("/logout").status_code == 302
    assert logged_in.get("/").status_code == 302
