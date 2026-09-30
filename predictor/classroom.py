"""Teacher-only pages: upload a class CSV and get risk-ranked predictions."""

import csv
import io
from functools import wraps

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .ml.batch import predict_class, read_class_csv, summarize, template_csv
from .ml.schema import FEATURE_NAMES
from .models import ClassReport

bp = Blueprint("classroom", __name__, url_prefix="/class")


def teacher_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_teacher:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def owned_report(report_id: int) -> ClassReport:
    report = db.session.get(ClassReport, report_id)
    if report is None or report.teacher_id != current_user.id:
        abort(404)
    return report


@bp.route("/")
@teacher_required
def index():
    return render_template("class_index.html", reports=current_user.class_reports,
                           columns=FEATURE_NAMES, errors=[])


@bp.route("/template.csv")
@teacher_required
def template():
    return Response(template_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=class-template.csv"})


@bp.route("/upload", methods=["POST"])
@teacher_required
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Choose a CSV file to upload.", "error")
        return redirect(url_for("classroom.index"))
    try:
        text = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("The file must be a UTF-8 encoded CSV.", "error")
        return redirect(url_for("classroom.index"))

    records, errors = read_class_csv(text)
    if errors:
        flash("The upload was not saved. Fix these problems and try again.", "error")
        return render_template("class_index.html", reports=current_user.class_reports,
                               columns=FEATURE_NAMES, errors=errors[:20],
                               more_errors=max(0, len(errors) - 20)), 400

    name = (request.form.get("name") or "").strip() or file.filename.rsplit(".", 1)[0]
    report = ClassReport(teacher_id=current_user.id, name=name[:120],
                         rows=predict_class(records))
    db.session.add(report)
    db.session.commit()
    return redirect(url_for("classroom.report", report_id=report.id))


@bp.route("/<int:report_id>")
@teacher_required
def report(report_id: int):
    report = owned_report(report_id)
    return render_template("class_report.html", report=report, summary=summarize(report.rows))


@bp.route("/<int:report_id>/export.csv")
@teacher_required
def export(report_id: int):
    report = owned_report(report_id)
    columns = ["student", *FEATURE_NAMES, "score", "lower", "upper", "grade", "risk",
               "top_negative", "suggestion"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(report.rows)
    return Response(buffer.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename=class-report-{report.id}.csv"})


@bp.route("/<int:report_id>/delete", methods=["POST"])
@teacher_required
def delete(report_id: int):
    db.session.delete(owned_report(report_id))
    db.session.commit()
    flash("Class report deleted.", "info")
    return redirect(url_for("classroom.index"))
