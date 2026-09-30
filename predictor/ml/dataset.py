"""Load the UCI Student Performance dataset and map it onto model columns.

Source: P. Cortez and A. Silva, "Using Data Mining to Predict Secondary School
Student Performance", 2008. https://archive.ics.uci.edu/dataset/320
"""

from pathlib import Path

import pandas as pd

from .schema import MODEL_COLUMNS

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TARGET = "final_score"


def load_raw(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    math = pd.read_csv(data_dir / "student-mat.csv", sep=";").assign(subject="math")
    port = pd.read_csv(data_dir / "student-por.csv", sep=";").assign(subject="portuguese")
    return pd.concat([math, port], ignore_index=True)


def build_features(raw: pd.DataFrame, drop_non_sitters: bool = True
                   ) -> tuple[pd.DataFrame, pd.Series]:
    """Grades are 0-20 in the source data; rescale to 0-100 to match the UI.

    A final grade of 0 means the student did not sit the final exam (their
    period grades are non-zero). Those rows describe dropout, not exam
    performance, and they distort the model: e.g. dropouts have almost no
    recorded absences, so absences would appear to *raise* scores. We predict
    the score of students who sit the exam and drop those rows by default.
    """
    if drop_non_sitters:
        raw = raw[raw["G3"] > 0]
    X = pd.DataFrame({
        "is_math": (raw["subject"] == "math").astype(int),
        "period1_score": raw["G1"].astype(float) * 5,
        "period2_score": raw["G2"].astype(float) * 5,
        "studytime": raw["studytime"].astype(int),
        "absences": raw["absences"].astype(float),
        "failures": raw["failures"].astype(float),
        "goout": raw["goout"].astype(float),
        "health": raw["health"].astype(float),
        "higher": (raw["higher"] == "yes").astype(int),
        "internet": (raw["internet"] == "yes").astype(int),
    })[MODEL_COLUMNS]
    y = (raw["G3"].astype(float) * 5).rename(TARGET)
    return X, y
