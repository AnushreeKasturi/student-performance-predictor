import pytest

from predictor.ml.inference import MIN_GAIN, get_predictor, grade_for
from predictor.ml.schema import parse_inputs, study_hours_to_band

from .conftest import VALID_INPUT


@pytest.fixture(scope="module")
def predictor():
    return get_predictor()


def clean(**overrides):
    values, errors = parse_inputs({**VALID_INPUT, **overrides})
    assert not errors
    return values


@pytest.mark.parametrize("score, grade", [(95, "A"), (90, "A"), (85, "B"), (72, "C"),
                                          (65, "D"), (50, "E"), (49.9, "F"), (0, "F")])
def test_grade_bands(score, grade):
    assert grade_for(score) == grade


@pytest.mark.parametrize("hours, band",
                         [(0, 1), (1.9, 1), (2, 2), (5, 2), (7, 3), (10, 3), (11, 4)])
def test_study_hours_bands(hours, band):
    assert study_hours_to_band(hours) == band


def test_parse_inputs_rejects_bad_values():
    _, errors = parse_inputs({**VALID_INPUT, "period2_score": "abc", "goout": "9", "higher": ""})
    assert set(errors) == {"period2_score", "goout", "higher"}


def test_parse_inputs_rejects_nan():
    _, errors = parse_inputs({**VALID_INPUT, "absences": "nan"})
    assert "absences" in errors


@pytest.mark.parametrize("p1, p2", [(0, 0), (100, 100), (50, 50)])
def test_predictions_stay_in_range(predictor, p1, p2):
    result = predictor.predict(clean(period1_score=p1, period2_score=p2))
    assert 0 <= result.lower <= result.score <= result.upper <= 100


def test_better_recent_grades_predict_higher(predictor):
    low = predictor.predict(clean(period2_score=40)).score
    high = predictor.predict(clean(period2_score=90)).score
    assert high > low + 20


def test_impacts_cover_every_input(predictor):
    impacts = predictor.predict(clean()).impacts
    assert {i.feature for i in impacts} == set(VALID_INPUT)
    assert max(impacts, key=lambda i: abs(i.value)).feature in {"period2_score", "period1_score"}


def test_recommendations_are_improvements(predictor):
    values = clean(absences=30, study_hours=1, goout=5, period2_score=55)
    result = predictor.predict(values)
    for rec in result.recommendations:
        assert rec.gain >= MIN_GAIN
        assert rec.new_score > result.score
