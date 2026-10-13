import numpy as np
import pytest

from linear_regression import LinearRegression, fit_least_squares, fit_simple, fit_until_match


def test_fit_simple_recovers_a_perfect_line():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    m, b = fit_simple(x, 3 * x + 2)
    assert m == pytest.approx(3)
    assert b == pytest.approx(2)


def test_fit_simple_matches_the_hand_worked_example():
    m, b = fit_simple([0.30, 0.35, 0.40, 0.45, 0.50], [8.1, 9.0, 10.2, 10.9, 12.0])
    assert m == pytest.approx(19.4)
    assert b == pytest.approx(2.28)


def test_fit_simple_refuses_when_x_never_changes():
    with pytest.raises(ValueError):
        fit_simple([5, 5, 5], [1, 2, 3])


def test_gradient_descent_matches_exact_solution():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    y = X @ np.array([1.5, -2.0, 0.5]) + 4 + rng.normal(0, 0.1, size=200)
    model = LinearRegression(learning_rate=0.1, epochs=2000).fit(X, y)
    slopes, intercept = model.original_units()
    exact_slopes, exact_intercept = fit_least_squares(X, y)
    np.testing.assert_allclose(slopes, exact_slopes, atol=1e-6)
    assert intercept == pytest.approx(exact_intercept, abs=1e-6)


def test_loss_goes_down():
    x = np.linspace(0, 1, 50)
    model = LinearRegression(learning_rate=0.1, epochs=200).fit(x, 2 * x + 1)
    assert model.loss_history_[-1] < model.loss_history_[0] / 1000


def test_too_big_learning_rate_is_reported_as_diverged():
    x = np.linspace(0, 1, 50)
    model = LinearRegression(learning_rate=5.0, epochs=500).fit(x, 2 * x + 1)
    assert model.diverged_


def test_fit_until_match_keeps_training_until_it_matches():
    x = np.linspace(0, 1, 30)
    model, attempts = fit_until_match(x, 4 * x - 1, learning_rate=0.1, start_epochs=2, match_within=1e-6)
    assert len(attempts) > 1  # the first try was not good enough
    assert attempts[-1][1] <= 1e-6
    assert [a[0] for a in attempts] == sorted(a[0] for a in attempts)  # epochs only grow


def test_from_exact_and_save_load_give_same_predictions():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(40, 2))
    y = X @ np.array([1.0, 2.0]) + 3
    exact = LinearRegression.from_exact(X, y)
    np.testing.assert_allclose(exact.predict(X), y, atol=1e-9)
    trained = LinearRegression(0.1, 3000).fit(X, y)
    reloaded = LinearRegression.from_dict(trained.to_dict())
    np.testing.assert_allclose(reloaded.predict(X), trained.predict(X))
