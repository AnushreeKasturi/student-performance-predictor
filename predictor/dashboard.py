import csv
import io
import json
from functools import lru_cache

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .charts import trend_chart
from .extensions import db
from .ml.inference import MODEL_PATH, get_predictor
from .ml.schema import FEATURES, FEATURES_BY_NAME, parse_inputs
from .models import Prediction
from .reports import prediction_pdf

bp = Blueprint("dashboard", __name__)


@lru_cache(maxsize=1)
def model_card() -> dict:
    """Headline metrics from training, shown on the dashboard."""
    metrics = json.loads((MODEL_PATH.parent / "metrics.json").read_text())
    importance = metrics["feature_importance"]["values"]
    top = max(importance.values())
    labels = {"is_math": "subject", "studytime": "study_hours"}
    return {
        **metrics,
        "importance_bars": [
            {"label": FEATURES_BY_NAME[labels.get(k, k)].label, "value": v,
             "pct": round(100 * v / top, 1)}
            for k, v in importance.items()
        ],
    }


def dashboard_context(**extra) -> dict:
    history = current_user.predictions
    scores = [p.predicted_score for p in history]
    stats = {
        "total": len(history),
        "average": round(sum(scores) / len(scores), 1) if scores else None,
        "best": max(scores) if scores else None,
        "latest_grade": history[0].grade if history else None,
    }
    return {"features": FEATURES, "history": history, "stats": stats,
            "chart_html": trend_chart(history), "model": model_card(),
            "values": {}, "errors": {}, "result": None, **extra}


@bp.route("/")
@login_required
def index():
    result = None
    if result_id := request.args.get("result", type=int):
        result = db.session.get(Prediction, result_id)
        if result is None or result.user_id != current_user.id:
            result = None
    values = result.inputs() if result else {}
    return render_template("dashboard.html", **dashboard_context(result=result, values=values))


@bp.route("/predict", methods=["POST"])
@login_required
def predict():
    values, errors = parse_inputs(request.form)
    if errors:
        flash("Please fix the highlighted fields.", "error")
        context = dashboard_context(values=request.form.to_dict(), errors=errors)
        return render_template("dashboard.html", **context), 400

    outcome = get_predictor().predict(values)
    prediction = Prediction(
        user_id=current_user.id, **values,
        predicted_score=outcome.score, lower=outcome.lower, upper=outcome.upper,
        grade=outcome.grade,
        explanation={
            "impacts": [vars(i) for i in outcome.impacts],
            "recommendations": [vars(r) for r in outcome.recommendations],
        },
    )
    db.session.add(prediction)
    db.session.commit()
    # Post/Redirect/Get: the result is re-loaded from the database after redirect
    return redirect(url_for("dashboard.index", result=prediction.id) + "#result")


def owned_prediction(prediction_id: int) -> Prediction:
    prediction = db.session.get(Prediction, prediction_id)
    if prediction is None or prediction.user_id != current_user.id:
        abort(404)
    return prediction


@bp.route("/history/<int:prediction_id>/report.pdf")
@login_required
def prediction_report(prediction_id: int):
    prediction = owned_prediction(prediction_id)
    return Response(
        prediction_pdf(prediction, current_user.username), mimetype="application/pdf",
        headers={"Content-Disposition":
                 f"attachment; filename=prediction-report-{prediction.id}.pdf"},
    )


@bp.route("/history/<int:prediction_id>/delete", methods=["POST"])
@login_required
def delete_prediction(prediction_id: int):
    prediction = owned_prediction(prediction_id)
    db.session.delete(prediction)
    db.session.commit()
    flash("Prediction deleted.", "info")
    return redirect(url_for("dashboard.index") + "#history")


@bp.route("/history/clear", methods=["POST"])
@login_required
def clear_history():
    db.session.execute(db.delete(Prediction).filter_by(user_id=current_user.id))
    db.session.commit()
    flash("History cleared.", "info")
    return redirect(url_for("dashboard.index"))


@bp.route("/history/export.csv")
@login_required
def export_history():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = ["created_at", *Prediction.INPUT_FIELDS, "predicted_score", "lower", "upper", "grade"]
    writer.writerow(header)
    for p in current_user.predictions:
        writer.writerow([p.created_at.isoformat(timespec="seconds"),
                         *p.inputs().values(), p.predicted_score, p.lower, p.upper, p.grade])
    return Response(
        buffer.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions.csv"},
    )
