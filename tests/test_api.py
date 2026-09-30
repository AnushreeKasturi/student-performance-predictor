from .conftest import VALID_INPUT


def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "ok"
    assert body["model"]


def test_schema_lists_every_feature(client):
    names = [f["name"] for f in client.get("/api/schema").get_json()["features"]]
    assert names == list(VALID_INPUT)


def test_predict_returns_explained_result(client):
    response = client.post("/api/predict", json=VALID_INPUT)
    assert response.status_code == 200
    body = response.get_json()
    interval = body["interval"]
    assert 0 <= interval["lower"] <= body["predicted_score"] <= interval["upper"] <= 100
    assert body["grade"] in {"A", "B", "C", "D", "E", "F"}
    assert {i["feature"] for i in body["impacts"]} == set(VALID_INPUT)


def test_predict_accepts_json_numbers(client):
    payload = {**VALID_INPUT, "period1_score": 65, "period2_score": 70.5}
    assert client.post("/api/predict", json=payload).status_code == 200


def test_predict_validation_errors(client):
    response = client.post("/api/predict", json={**VALID_INPUT, "absences": -1, "subject": "art"})
    assert response.status_code == 400
    fields = response.get_json()["fields"]
    assert set(fields) == {"absences", "subject"}


def test_predict_rejects_non_object(client):
    assert client.post("/api/predict", json=[1, 2, 3]).status_code == 400
    assert client.post("/api/predict", data="not json").status_code == 400
