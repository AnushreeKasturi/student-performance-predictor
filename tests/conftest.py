import pytest

from predictor import create_app
from predictor.config import TestConfig
from predictor.extensions import db

VALID_INPUT = {
    "subject": "math",
    "period1_score": "65",
    "period2_score": "70",
    "study_hours": "3",
    "absences": "6",
    "failures": "0",
    "goout": "4",
    "health": "4",
    "higher": "yes",
    "internet": "yes",
}


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def signup_and_login(client, username="alice", password="correct-horse"):
    client.post("/signup", data={"username": username, "password": password, "confirm": password})
    return client.post("/login", data={"username": username, "password": password})


@pytest.fixture
def logged_in(client):
    signup_and_login(client)
    return client
