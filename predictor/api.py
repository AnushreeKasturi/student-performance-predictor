"""Stateless JSON API. Predictions made here are not saved to any account."""

from dataclasses import asdict

from flask import Blueprint, jsonify, request

from .extensions import csrf
from .ml.batch import MAX_ROWS, predict_class
from .ml.inference import get_predictor
from .ml.schema import FEATURES, parse_inputs

bp = Blueprint("api", __name__, url_prefix="/api")
csrf.exempt(bp)


@bp.get("/health")
def health():
    return jsonify(status="ok", model=get_predictor().model_name)


@bp.get("/schema")
def schema():
    return jsonify(features=[
        {k: v for k, v in asdict(f).items() if v not in (None, ())} for f in FEATURES
    ])


@bp.post("/predict")
def predict():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Request body must be a JSON object."), 400
    values, errors = parse_inputs(payload)
    if errors:
        return jsonify(error="Invalid input.", fields=errors), 400
    predictor = get_predictor()
    return jsonify(model=predictor.model_name, **predictor.predict(values).to_dict())


@bp.post("/predict/batch")
def predict_batch():
    payload = request.get_json(silent=True)
    students = payload.get("students") if isinstance(payload, dict) else None
    if not isinstance(students, list) or not students:
        return jsonify(error='Body must be {"students": [ ... ]} with at least one student.'), 400
    if len(students) > MAX_ROWS:
        return jsonify(error=f"At most {MAX_ROWS} students per request."), 400

    records, errors = [], {}
    for index, student in enumerate(students):
        values, row_errors = parse_inputs(student if isinstance(student, dict) else {})
        if row_errors:
            errors[index] = row_errors
        else:
            name = str(student.get("student") or f"#{index}")[:80]
            records.append({"student": name, **values})
    if errors:
        return jsonify(error="Invalid input.", rows=errors), 400
    return jsonify(model=get_predictor().model_name, results=predict_class(records))
