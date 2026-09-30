from predictor.extensions import db
from predictor.models import Prediction

from .conftest import VALID_INPUT, signup_and_login


def test_prediction_is_shown_after_redirect(logged_in):
    response = logged_in.post("/predict", data=VALID_INPUT)
    assert response.status_code == 302
    assert "result=" in response.headers["Location"]

    page = logged_in.get(response.headers["Location"]).data
    assert b"90% prediction range" in page
    assert b"Why this score?" in page


def test_prediction_saves_all_inputs(app, logged_in):
    logged_in.post("/predict", data=VALID_INPUT)
    with app.app_context():
        p = db.session.execute(db.select(Prediction)).scalar_one()
        assert p.period1_score == 65 and p.internet == "yes" and p.subject == "math"
        assert 0 <= p.lower <= p.predicted_score <= p.upper <= 100
        assert p.explanation["impacts"]


def test_invalid_input_rerenders_with_errors(app, logged_in):
    response = logged_in.post("/predict", data={**VALID_INPUT, "period1_score": "250"})
    assert response.status_code == 400
    assert b"Must be between 0 and 100." in response.data
    with app.app_context():
        assert db.session.execute(db.select(Prediction)).first() is None


def test_users_only_see_their_own_results(client):
    signup_and_login(client, "alice")
    location = client.post("/predict", data=VALID_INPUT).headers["Location"]
    client.post("/logout")

    signup_and_login(client, "mallory")
    page = client.get(location).data
    assert b"90% prediction range" not in page
    assert client.post("/history/1/delete").status_code == 404


def test_delete_and_clear_history(app, logged_in):
    for _ in range(3):
        logged_in.post("/predict", data=VALID_INPUT)
    logged_in.post("/history/1/delete")
    with app.app_context():
        assert db.session.query(Prediction).count() == 2
    logged_in.post("/history/clear")
    with app.app_context():
        assert db.session.query(Prediction).count() == 0


def test_export_csv(logged_in):
    logged_in.post("/predict", data=VALID_INPUT)
    response = logged_in.get("/history/export.csv")
    assert response.mimetype == "text/csv"
    lines = response.data.decode().strip().splitlines()
    assert lines[0].startswith("created_at,subject,period1_score")
    assert len(lines) == 2


def test_trend_chart_after_two_predictions(logged_in):
    logged_in.post("/predict", data=VALID_INPUT)
    assert b"plotly" not in logged_in.get("/").data
    logged_in.post("/predict", data={**VALID_INPUT, "period2_score": "80"})
    assert b"plotly" in logged_in.get("/").data
