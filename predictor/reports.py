"""One-page PDF report for a saved prediction."""

from fpdf import FPDF

from .ml.schema import FEATURES

BLUE = (42, 120, 214)
RED = (227, 73, 72)
INK = (11, 11, 11)
MUTED = (82, 81, 78)
RULE = (220, 219, 214)


def _format_input(feature, value) -> str:
    if feature.kind == "choice":
        return dict(feature.choices).get(value, str(value))
    return f"{value:g}"


def prediction_pdf(prediction, username: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)
    width = pdf.w - 36

    # Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(width, 10, "Student Performance Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    created = prediction.created_at.strftime("%d %b %Y, %H:%M")
    pdf.cell(width, 6, f"Prepared for {username} - {created}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Headline
    score = f"{prediction.predicted_score:.1f}"
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(*INK)
    pdf.cell(pdf.get_string_width(score) + 2, 16, score)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*MUTED)
    pdf.cell(25, 18, "/ 100", align="L")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*INK)
    pdf.cell(0, 16, f"Grade {prediction.grade}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(width, 6, f"90% prediction range: {prediction.lower:.0f} to {prediction.upper:.0f}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Inputs table
    _heading(pdf, width, "Inputs")
    pdf.set_font("Helvetica", "", 10)
    inputs = prediction.inputs()
    half = width / 2
    for i, feature in enumerate(FEATURES):
        pdf.set_text_color(*MUTED)
        pdf.cell(half * 0.6, 7, feature.label)
        pdf.set_text_color(*INK)
        pdf.cell(half * 0.4, 7, _format_input(feature, inputs[feature.name]),
                 new_x="LMARGIN" if i % 2 else "RIGHT", new_y="NEXT" if i % 2 else "TOP")
    pdf.ln(6)

    # Impact bars (diverging: blue adds points, red removes them)
    _heading(pdf, width, "Why this score?")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(width, 5, "Points each factor adds or removes compared with a typical student.",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    impacts = [i for i in prediction.explanation.get("impacts", []) if i["value"]][:6]
    max_abs = max((abs(i["value"]) for i in impacts), default=1)
    label_w, value_w = 50, 18
    track_w = width - label_w - value_w
    for imp in impacts:
        y = pdf.get_y()
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(label_w, 7, imp["label"])
        center = pdf.l_margin + label_w + track_w / 2
        bar = (track_w / 2 - 2) * abs(imp["value"]) / max_abs
        pdf.set_fill_color(*(BLUE if imp["value"] > 0 else RED))
        pdf.rect(center if imp["value"] > 0 else center - bar, y + 1.5, max(bar, 0.6), 4, "F")
        pdf.set_draw_color(*RULE)
        pdf.line(center, y, center, y + 7)
        pdf.set_x(pdf.l_margin + label_w + track_w)
        pdf.cell(value_w, 7, f"{imp['value']:+.1f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Recommendations
    _heading(pdf, width, "What could raise it?")
    pdf.set_font("Helvetica", "", 10)
    recs = prediction.explanation.get("recommendations", [])
    if recs:
        for rec in recs:
            pdf.set_text_color(*INK)
            pdf.cell(width - 40, 7, f"- {rec['message']}")
            pdf.cell(40, 7, f"+{rec['gain']:.1f} (to {rec['new_score']:.1f})", align="R",
                     new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(*MUTED)
        pdf.cell(width, 7, "No single habit change raises this prediction noticeably.",
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(width, 4, (
        "Predictions come from a model trained on the UCI Student Performance dataset "
        "(Cortez & Silva, 2008). Explanations and suggestions reflect associations in that "
        "data, not guaranteed causes. The 90% range is calibrated on held-out data."
    ))
    return bytes(pdf.output())


def _heading(pdf: FPDF, width: float, text: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(width, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*RULE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + width, pdf.get_y())
    pdf.ln(2)
