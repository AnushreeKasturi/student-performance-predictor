"""Batch predictions for a whole class (CSV upload / batch API)."""

import csv
import io
from collections import Counter

from .inference import GRADE_BANDS, get_predictor
from .schema import FEATURE_NAMES, parse_inputs

MAX_ROWS = 500
PASS_MARK = 50
RISK_ORDER = {"At risk": 0, "Watch": 1, "On track": 2}

TEMPLATE_ROWS = [
    {"student": "Student A", "subject": "math", "period1_score": 45, "period2_score": 40,
     "study_hours": 1, "absences": 16, "failures": 2, "goout": 5, "health": 3,
     "higher": "no", "internet": "yes"},
    {"student": "Student B", "subject": "portuguese", "period1_score": 70, "period2_score": 75,
     "study_hours": 6, "absences": 2, "failures": 0, "goout": 2, "health": 4,
     "higher": "yes", "internet": "yes"},
]


def template_csv() -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["student", *FEATURE_NAMES])
    writer.writeheader()
    writer.writerows(TEMPLATE_ROWS)
    return buffer.getvalue()


def risk_level(score: float, lower: float) -> str:
    """At risk: predicted to fail. Watch: a fail is inside the 90% range."""
    if score < PASS_MARK:
        return "At risk"
    if lower < PASS_MARK:
        return "Watch"
    return "On track"


def read_class_csv(text: str) -> tuple[list[dict], list[str]]:
    """Parse and validate an uploaded CSV. Returns (records, errors)."""
    reader = csv.DictReader(io.StringIO(text))
    missing = [name for name in FEATURE_NAMES if name not in (reader.fieldnames or [])]
    if missing:
        return [], [f"Missing column(s): {', '.join(missing)}."]

    records, errors = [], []
    for line_no, raw in enumerate(reader, start=2):  # line 1 is the header
        if len(records) + len(errors) >= MAX_ROWS:
            errors.append(f"Too many rows: the limit is {MAX_ROWS} students per upload.")
            break
        values, row_errors = parse_inputs(raw)
        if row_errors:
            detail = "; ".join(f"{field}: {msg}" for field, msg in row_errors.items())
            errors.append(f"Row {line_no}: {detail}")
            continue
        student = (raw.get("student") or "").strip() or f"Row {line_no}"
        records.append({"student": student[:80], **values})
    if not records and not errors:
        errors.append("The file has no student rows.")
    return records, errors


def predict_class(records: list[dict]) -> list[dict]:
    predictor = get_predictor()
    rows = []
    for record in records:
        values = {k: record[k] for k in FEATURE_NAMES}
        result = predictor.predict(values)
        biggest_drag = min(result.impacts, key=lambda i: i.value)
        rows.append({
            **record,
            "score": result.score, "lower": result.lower, "upper": result.upper,
            "grade": result.grade, "risk": risk_level(result.score, result.lower),
            "top_negative": biggest_drag.label if biggest_drag.value < 0 else None,
            "suggestion": result.recommendations[0].message if result.recommendations else None,
        })
    return sorted(rows, key=lambda r: (RISK_ORDER[r["risk"]], r["score"]))


def summarize(rows: list[dict]) -> dict:
    grades = Counter(r["grade"] for r in rows)
    risks = Counter(r["risk"] for r in rows)
    order = [g for _, g in GRADE_BANDS] + ["F"]
    top = max(grades.values(), default=1)
    return {
        "students": len(rows),
        "average": round(sum(r["score"] for r in rows) / len(rows), 1) if rows else None,
        "at_risk": risks["At risk"],
        "watch": risks["Watch"],
        "grade_bars": [{"grade": g, "count": grades[g], "pct": round(100 * grades[g] / top, 1)}
                       for g in order],
    }
