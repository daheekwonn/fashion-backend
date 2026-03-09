"""
tests/test_scorer.py
─────────────────────
Unit tests for the trend scoring engine.
Run with: pytest tests/ -v
"""
import pytest
from app.services.trend_scorer import (
    compute_composite_score,
    compute_trend_delta,
    _normalise_linear,
    _normalise_log,
    _clamp,
)


# ── _normalise_linear ─────────────────────────────────────────────────────────

def test_normalise_linear_basic():
    assert _normalise_linear(50, 100) == 50.0

def test_normalise_linear_max():
    assert _normalise_linear(100, 100) == 100.0

def test_normalise_linear_zero_max():
    assert _normalise_linear(50, 0) == 0.0

def test_normalise_linear_clamps():
    assert _normalise_linear(200, 100) == 100.0


# ── _normalise_log ────────────────────────────────────────────────────────────

def test_normalise_log_zero():
    assert _normalise_log(0) == 0.0

def test_normalise_log_positive():
    score = _normalise_log(100)
    assert 0 < score < 100

def test_normalise_log_clamps():
    assert _normalise_log(1_000_000) == 100.0


# ── _clamp ────────────────────────────────────────────────────────────────────

def test_clamp_low():
    assert _clamp(-5.0) == 0.0

def test_clamp_high():
    assert _clamp(105.0) == 100.0

def test_clamp_in_range():
    assert _clamp(55.0) == 55.0


# ── compute_composite_score ───────────────────────────────────────────────────

def test_composite_even_weights():
    score = compute_composite_score(
        runway_score=60,
        search_score=80,
        social_score=40,
        weights=(1/3, 1/3, 1/3),
    )
    assert abs(score - 60.0) < 0.1

def test_composite_runway_heavy():
    score = compute_composite_score(
        runway_score=100,
        search_score=0,
        social_score=0,
        weights=(1.0, 0.0, 0.0),
    )
    assert score == 100.0

def test_composite_zero():
    score = compute_composite_score(0, 0, 0)
    assert score == 0.0

def test_composite_clamps():
    score = compute_composite_score(120, 110, 105)
    assert score <= 100.0

def test_composite_default_weights():
    """With default weights (0.5/0.3/0.2), verify formula."""
    score = compute_composite_score(80, 60, 40)
    expected = 0.5 * 80 + 0.3 * 60 + 0.2 * 40
    assert abs(score - expected) < 0.1


# ── compute_trend_delta ───────────────────────────────────────────────────────

def test_delta_increase():
    delta = compute_trend_delta(current=60, previous=50)
    assert delta == 20.0

def test_delta_decrease():
    delta = compute_trend_delta(current=40, previous=50)
    assert delta == -20.0

def test_delta_zero_previous():
    delta = compute_trend_delta(current=50, previous=0)
    assert delta == 100.0

def test_delta_no_change():
    delta = compute_trend_delta(current=50, previous=50)
    assert delta == 0.0

def test_delta_from_zero():
    delta = compute_trend_delta(current=0, previous=0)
    assert delta == 0.0
