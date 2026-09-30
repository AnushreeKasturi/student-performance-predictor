"""Load the trained model and turn user inputs into an explained prediction."""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from .schema import FEATURES_BY_NAME, to_model_row

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "model.joblib"

# Model column -> user-facing input it comes from
COLUMN_TO_INPUT = {"is_math": "subject", "studytime": "study_hours"}

# Pass mark of 50/100 mirrors the 10/20 pass mark of the Portuguese grading scale
# Smallest what-if improvement worth suggesting, in points
MIN_GAIN = 0.3

GRADE_BANDS = ((90, "A"), (80, "B"), (70, "C"), (60, "D"), (50, "E"))


def grade_for(score: float) -> str:
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return "F"


@dataclass
class Impact:
    feature: str
    label: str
    value: float  # points added (+) or removed (-) vs. a typical student


@dataclass
class Recommendation:
    feature: str
    message: str
    gain: float
    new_score: float


@dataclass
class PredictionResult:
    score: float
    lower: float
    upper: float
    grade: str
    impacts: list[Impact] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "predicted_score": self.score,
            "grade": self.grade,
            "interval": {"lower": self.lower, "upper": self.upper, "coverage": 0.9},
            "impacts": [vars(i) for i in self.impacts],
            "recommendations": [vars(r) for r in self.recommendations],
        }


class Predictor:
    def __init__(self, artifact: dict):
        self.model = artifact["model"]
        self.columns = artifact["columns"]
        self.background = artifact["background"][self.columns]
        self.halfwidth = artifact["interval_halfwidth"]
        self.model_name = artifact["model_name"]

    def _predict_rows(self, rows: pd.DataFrame):
        return self.model.predict(rows[self.columns]).clip(0, 100)

    def _score(self, values: dict) -> float:
        return float(self._predict_rows(pd.DataFrame([to_model_row(values)]))[0])

    def explain(self, row: dict, score: float) -> list[Impact]:
        """Per-feature impact: how much the prediction changes when that one
        feature is replaced by values from typical (background) students."""
        frames = []
        for col in self.columns:
            swapped = pd.DataFrame([row] * len(self.background))
            swapped[col] = self.background[col].to_numpy()
            frames.append(swapped)
        preds = self._predict_rows(pd.concat(frames, ignore_index=True))
        n = len(self.background)
        impacts = []
        for i, col in enumerate(self.columns):
            name = COLUMN_TO_INPUT.get(col, col)
            delta = score - float(preds[i * n:(i + 1) * n].mean())
            impacts.append(Impact(name, FEATURES_BY_NAME[name].label, round(delta, 2)))
        return sorted(impacts, key=lambda imp: -abs(imp.value))

    def recommend(self, values: dict, score: float) -> list[Recommendation]:
        """What-if analysis over the inputs a student can actually change."""
        candidates = []
        hours = values["study_hours"]
        for target in (3.5, 7.5, 12):  # representative hours for each study band
            if target > hours:
                candidates.append(("study_hours", target,
                                   f"Study about {target:g} hours a week (currently {hours:g})"))
        absences = values["absences"]
        if absences >= 2:
            fewer = int(absences // 2)
            candidates.append(("absences", fewer,
                               f"Cut absences from {absences:g} to {fewer}"))
        if values["goout"] > 2:
            candidates.append(("goout", values["goout"] - 1,
                               "Spend a little less time going out"))
        if values["higher"] == "no":
            candidates.append(("higher", "yes", "Set a goal of continuing to higher education"))

        best_per_feature: dict[str, Recommendation] = {}
        for feature, new_value, message in candidates:
            new_score = self._score({**values, feature: new_value})
            gain = round(new_score - score, 2)
            if gain >= MIN_GAIN and gain > getattr(best_per_feature.get(feature), "gain", 0):
                best_per_feature[feature] = Recommendation(
                    feature, message, gain, round(new_score, 1))
        return sorted(best_per_feature.values(), key=lambda r: -r.gain)[:3]

    def predict(self, values: dict) -> PredictionResult:
        row = to_model_row(values)
        score = float(self._predict_rows(pd.DataFrame([row]))[0])
        return PredictionResult(
            score=round(score, 1),
            lower=round(max(0.0, score - self.halfwidth), 1),
            upper=round(min(100.0, score + self.halfwidth), 1),
            grade=grade_for(score),
            impacts=self.explain(row, score),
            recommendations=self.recommend(values, score),
        )


@lru_cache(maxsize=1)
def get_predictor(path: Path = MODEL_PATH) -> Predictor:
    return Predictor(joblib.load(path))
