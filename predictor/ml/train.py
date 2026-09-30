"""Train, compare and export the score-prediction model.

Usage:
    python -m predictor.ml.train

Writes models/model.joblib (used by the web app) and models/metrics.json
(model comparison + held-out test metrics, shown on the dashboard/README).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GridSearchCV, KFold, cross_val_predict, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .dataset import build_features, load_raw

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
RANDOM_STATE = 42
INTERVAL_COVERAGE = 0.90
CV = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

# Domain knowledge: better earlier grades / more study never lower the
# prediction; more absences / past failures never raise it.
MONOTONIC = {"period1_score": 1, "period2_score": 1, "studytime": 1,
             "absences": -1, "failures": -1}


def candidate_models() -> dict:
    return {
        "Linear Regression": LinearRegression(),
        "Ridge Regression": GridSearchCV(
            make_pipeline(StandardScaler(), Ridge()),
            {"ridge__alpha": [0.1, 1, 10, 100]},
            cv=CV, scoring="neg_root_mean_squared_error",
        ),
        "Random Forest": GridSearchCV(
            RandomForestRegressor(n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1),
            {"min_samples_leaf": [1, 3, 5], "max_features": [0.5, 1.0]},
            cv=CV, scoring="neg_root_mean_squared_error",
        ),
        "Gradient Boosting": GridSearchCV(
            GradientBoostingRegressor(subsample=0.8, random_state=RANDOM_STATE),
            {"n_estimators": [100, 300], "learning_rate": [0.03, 0.1], "max_depth": [2, 3]},
            cv=CV, scoring="neg_root_mean_squared_error", n_jobs=-1,
        ),
        "Monotonic Gradient Boosting": GridSearchCV(
            HistGradientBoostingRegressor(monotonic_cst=MONOTONIC, random_state=RANDOM_STATE),
            {"learning_rate": [0.03, 0.05, 0.1], "max_iter": [100, 300],
             "min_samples_leaf": [10, 20]},
            cv=CV, scoring="neg_root_mean_squared_error", n_jobs=-1,
        ),
    }


def scores(y_true, y_pred) -> dict:
    return {
        "r2": round(float(r2_score(y_true, y_pred)), 3),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 2),
        "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 2),
    }


def unwrap(model):
    """Return the tuned estimator if the model is a search object."""
    return model.best_estimator_ if isinstance(model, GridSearchCV) else model


def global_importance(model, X_background: pd.DataFrame, X_eval: pd.DataFrame) -> dict:
    """Mean |SHAP| per feature. Falls back to permutation importance without shap."""
    try:
        import shap

        # Picks the exact TreeExplainer / LinearExplainer for the model type
        explainer = shap.Explainer(model, X_background)
        values = explainer(X_eval).values
        importance = np.abs(values).mean(axis=0)
        method = "mean |SHAP value|"
    except ImportError:
        from sklearn.inspection import permutation_importance

        result = permutation_importance(model, X_eval, model.predict(X_eval),
                                        n_repeats=10, random_state=RANDOM_STATE)
        importance = result.importances_mean
        method = "permutation importance"
    ranked = sorted(zip(X_eval.columns, importance, strict=True), key=lambda kv: -kv[1])
    return {"method": method, "values": {k: round(float(v), 3) for k, v in ranked}}


def main() -> None:
    raw = load_raw()
    X, y = build_features(raw)
    non_sitters = len(raw) - len(X)
    print(f"Excluded {non_sitters} students who did not sit the final exam (grade 0)")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )
    print(f"Dataset: {len(X)} students ({len(X_train)} train / {len(X_test)} test)")

    # Naive baseline: "final score = period 2 score"
    baseline = scores(y_test, X_test["period2_score"])
    print(f"{'Baseline (final = period 2)':<28} test {baseline}")

    comparison, fitted = [], {}
    for name, model in candidate_models().items():
        oof = cross_val_predict(model, X_train, y_train, cv=CV)
        cv_scores = scores(y_train, oof)
        model.fit(X_train, y_train)
        fitted[name] = (model, oof)
        params = model.best_params_ if isinstance(model, GridSearchCV) else {}
        comparison.append({"model": name, "cv": cv_scores, "params": params})
        print(f"{name:<28} 5-fold CV {cv_scores} {params}")

    best = min(comparison, key=lambda row: row["cv"]["rmse"])
    best_model, best_oof = fitted[best["model"]]
    estimator = unwrap(best_model)
    test_scores = scores(y_test, np.clip(estimator.predict(X_test), 0, 100))
    print(f"\nSelected: {best['model']} -> held-out test {test_scores}")

    # Split-conformal style interval: 90th percentile of out-of-fold |residuals|
    interval_halfwidth = float(np.quantile(np.abs(y_train - best_oof), INTERVAL_COVERAGE))
    test_pred = estimator.predict(X_test)
    coverage = float(np.mean(np.abs(y_test - test_pred) <= interval_halfwidth))
    print(f"Prediction interval: +/-{interval_halfwidth:.1f} points "
          f"(target {INTERVAL_COVERAGE:.0%}, test coverage {coverage:.1%})")

    background = X_train.sample(100, random_state=RANDOM_STATE)
    importance = global_importance(estimator, background, X_test)
    print(f"Feature importance ({importance['method']}): {importance['values']}")

    # Refit the chosen configuration on all data for serving
    final_model = sklearn.base.clone(estimator).fit(X, y)

    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump({
        "model": final_model,
        "columns": list(X.columns),
        "background": background.reset_index(drop=True),
        "interval_halfwidth": interval_halfwidth,
        "model_name": best["model"],
        "sklearn_version": sklearn.__version__,
    }, MODELS_DIR / "model.joblib", compress=3)

    metrics = {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": {"rows": len(X), "train": len(X_train), "test": len(X_test),
                    "excluded_non_sitters": non_sitters},
        "baseline": {"name": "final = period 2 score", "test": baseline},
        "comparison": comparison,
        "selected": {"model": best["model"], "test": test_scores},
        "interval": {"coverage_target": INTERVAL_COVERAGE,
                     "halfwidth": round(interval_halfwidth, 2),
                     "test_coverage": round(coverage, 3)},
        "feature_importance": importance,
    }
    (MODELS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nSaved model and metrics to {MODELS_DIR}")


if __name__ == "__main__":
    main()
