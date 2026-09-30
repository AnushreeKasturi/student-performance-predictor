import io

from predictor.extensions import db
from predictor.ml.batch import MAX_ROWS, read_class_csv, risk_level, template_csv
from predictor.models import ClassReport

from .conftest import VALID_INPUT, signup_and_login


def signup_teacher(client, username="ms_rao"):
    password = "teacher-pass-1"
    client.post("/signup", data={"username": username, "password": password,
                                 "confirm": password, "role": "teacher"})
    client.post("/login", data={"username": username, "password": password})


def upload(client, text, name="Maths 11B"):
    return client.post("/class/upload", data={
        "name": name, "file": (io.BytesIO(text.encode()), "class.csv"),
    }, content_type="multipart/form-data")


def test_students_cannot_access_class_pages(logged_in):
    assert logged_in.get("/class/").status_code == 403
    assert logged_in.get("/class/template.csv").status_code == 403


def test_template_round_trips(client):
    records, errors = read_class_csv(template_csv())
    assert not errors
    assert [r["student"] for r in records] == ["Student A", "Student B"]


def test_upload_creates_ranked_report(app, client):
    signup_teacher(client)
    response = upload(client, template_csv())
    assert response.status_code == 302

    page = client.get(response.headers["Location"]).data
    assert b"Maths 11B" in page and b"Student A" in page
    with app.app_context():
        report = db.session.execute(db.select(ClassReport)).scalar_one()
        # Struggling student A is ranked above student B
        assert report.rows[0]["student"] == "Student A"
        assert report.rows[0]["risk"] in {"At risk", "Watch"}


def test_upload_with_errors_is_rejected(app, client):
    signup_teacher(client)
    bad = template_csv().replace("Student B,portuguese,70", "Student B,portuguese,700")
    response = upload(client, bad)
    assert response.status_code == 400
    assert b"Row 3: period1_score" in response.data
    with app.app_context():
        assert db.session.execute(db.select(ClassReport)).first() is None


def test_upload_missing_columns(client):
    signup_teacher(client)
    response = upload(client, "student,subject\nA,math\n")
    assert b"Missing column(s)" in response.data


def test_row_limit():
    header, row = template_csv().splitlines()[:2]
    _, errors = read_class_csv("\n".join([header] + [row] * (MAX_ROWS + 5)))
    assert any("limit" in e for e in errors)


def test_reports_are_private_to_their_teacher(client):
    signup_teacher(client, "teacher_one")
    location = upload(client, template_csv()).headers["Location"]
    client.post("/logout")
    signup_teacher(client, "teacher_two")
    assert client.get(location).status_code == 404


def test_export_and_delete(app, client):
    signup_teacher(client)
    location = upload(client, template_csv()).headers["Location"]
    csv_text = client.get(location + "/export.csv").data.decode()
    assert csv_text.splitlines()[0].startswith("student,subject")
    assert len(csv_text.strip().splitlines()) == 3
    client.post(location + "/delete")
    with app.app_context():
        assert db.session.execute(db.select(ClassReport)).first() is None


def test_risk_levels():
    assert risk_level(45, 38) == "At risk"
    assert risk_level(55, 48) == "Watch"
    assert risk_level(70, 63) == "On track"


def test_batch_api(client):
    students = [{**VALID_INPUT, "student": "A"}, {**VALID_INPUT, "student": "B",
                                                   "period2_score": "30"}]
    body = client.post("/api/predict/batch", json={"students": students}).get_json()
    assert [r["student"] for r in body["results"]] == ["B", "A"]  # riskiest first


def test_batch_api_errors(client):
    response = client.post("/api/predict/batch", json={"students": [{**VALID_INPUT, "goout": 9}]})
    assert response.status_code == 400
    assert "goout" in response.get_json()["rows"]["0"]
    assert client.post("/api/predict/batch", json={"students": []}).status_code == 400


def test_pdf_report(client):
    signup_and_login(client)
    location = client.post("/predict", data=VALID_INPUT).headers["Location"]
    prediction_id = location.split("result=")[1].split("#")[0]
    response = client.get(f"/history/{prediction_id}/report.pdf")
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    client.post("/logout")
    signup_and_login(client, "someone_else")
    assert client.get(f"/history/{prediction_id}/report.pdf").status_code == 404
