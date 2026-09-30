"""Single source of truth for the model's input features.

The same spec drives input validation (web form + JSON API), the HTML form
attributes, and the mapping from raw UCI columns to model features.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Feature:
    name: str
    label: str
    help: str
    kind: str  # "number" | "choice"
    min: float | None = None
    max: float | None = None
    step: float = 1
    choices: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    actionable: bool = False


FEATURES: tuple[Feature, ...] = (
    Feature("subject", "Subject", "Course the prediction is for", "choice",
            choices=(("math", "Mathematics"), ("portuguese", "Portuguese"))),
    Feature("period1_score", "Period 1 score", "First-period grade, out of 100",
            "number", 0, 100, 0.5),
    Feature("period2_score", "Period 2 score", "Second-period grade, out of 100",
            "number", 0, 100, 0.5),
    Feature("study_hours", "Weekly study hours", "Hours of self-study per week",
            "number", 0, 60, 0.5, actionable=True),
    Feature("absences", "Absences", "Number of classes missed this year",
            "number", 0, 100, 1, actionable=True),
    Feature("failures", "Past failures", "Number of previously failed classes",
            "number", 0, 10, 1),
    Feature("goout", "Social outings", "Going out with friends (1 = very low, 5 = very high)",
            "number", 1, 5, 1, actionable=True),
    Feature("health", "Health", "Current health status (1 = very bad, 5 = very good)",
            "number", 1, 5, 1),
    Feature("higher", "Higher-ed plans", "Wants to pursue higher education",
            "choice", choices=(("yes", "Yes"), ("no", "No")), actionable=True),
    Feature("internet", "Internet at home", "Has internet access at home",
            "choice", choices=(("yes", "Yes"), ("no", "No"))),
)

FEATURE_NAMES = [f.name for f in FEATURES]
FEATURES_BY_NAME = {f.name: f for f in FEATURES}

# Model columns (numeric encoding of the inputs above)
MODEL_COLUMNS = [
    "is_math", "period1_score", "period2_score", "studytime", "absences",
    "failures", "goout", "health", "higher", "internet",
]


def study_hours_to_band(hours: float) -> int:
    """UCI `studytime` is banded: 1 (<2h), 2 (2-5h), 3 (5-10h), 4 (>10h)."""
    if hours < 2:
        return 1
    if hours <= 5:
        return 2
    if hours <= 10:
        return 3
    return 4


def parse_inputs(raw) -> tuple[dict, dict]:
    """Validate raw form/JSON values. Returns (clean_values, errors)."""
    clean, errors = {}, {}
    for f in FEATURES:
        value = raw.get(f.name)
        if value is None or str(value).strip() == "":
            errors[f.name] = "This field is required."
            continue
        if f.kind == "choice":
            value = str(value).strip().lower()
            if value not in {c for c, _ in f.choices}:
                errors[f.name] = f"Must be one of: {', '.join(c for c, _ in f.choices)}."
                continue
            clean[f.name] = value
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                errors[f.name] = "Must be a number."
                continue
            if number != number or not (f.min <= number <= f.max):  # NaN check
                errors[f.name] = f"Must be between {f.min:g} and {f.max:g}."
                continue
            clean[f.name] = number
    return clean, errors


def to_model_row(values: dict) -> dict:
    """Encode validated user inputs into model columns."""
    return {
        "is_math": int(values["subject"] == "math"),
        "period1_score": float(values["period1_score"]),
        "period2_score": float(values["period2_score"]),
        "studytime": study_hours_to_band(float(values["study_hours"])),
        "absences": float(values["absences"]),
        # The dataset caps failures at 3 ("3 or more")
        "failures": min(float(values["failures"]), 3.0),
        "goout": float(values["goout"]),
        "health": float(values["health"]),
        "higher": int(values["higher"] == "yes"),
        "internet": int(values["internet"] == "yes"),
    }
