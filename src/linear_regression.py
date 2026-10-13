"""Linear regression written from scratch, so every step of y = mx + b is visible.

Three ways to find the line are included, and progression.py checks they agree:
  1. fit_simple          - one feature, exact formula (closed form)
  2. LinearRegression    - many features, learned step by step (gradient descent)
  3. fit_least_squares   - many features, exact answer from NumPy (used as the referee)
"""
import numpy as np


def fit_simple(x, y):
    """Best straight line y = m*x + b through the points (least squares). Returns (m, b)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    x_mean, y_mean = x.mean(), y.mean()
    spread = ((x - x_mean) ** 2).sum()
    if spread == 0:
        raise ValueError("Every x is the same, so no slope can be learned.")
    m = ((x - x_mean) * (y - y_mean)).sum() / spread
    b = y_mean - m * x_mean
    return float(m), float(b)


def fit_least_squares(X, y):
    """Exact multi-feature answer from NumPy. Returns (slopes, intercept)."""
    X = np.asarray(X, dtype=np.float64)
    if X.ndim == 1:
        X = X[:, None]
    ones = np.ones((X.shape[0], 1))
    solution, *_ = np.linalg.lstsq(np.hstack([X, ones]), y, rcond=None)
    return solution[:-1], float(solution[-1])


class LinearRegression:
    """y = m1*x1 + m2*x2 + ... + b, trained by gradient descent on mean squared error."""

    def __init__(self, learning_rate=0.05, epochs=3000, tolerance=0.0):
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.tolerance = tolerance  # stop early once the loss improves by less than this

    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        if X.ndim == 1:
            X = X[:, None]

        # Standardise: every feature gets mean 0 and spread 1, so one learning rate suits all.
        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0)
        self.std_[self.std_ == 0] = 1.0
        Z = (X - self.mean_) / self.std_

        n, k = Z.shape
        w = np.zeros(k)
        b = 0.0
        self.loss_history_ = []
        self.diverged_ = False
        for _ in range(self.epochs):
            y_hat = Z @ w + b
            error = y_hat - y
            loss = float((error ** 2).mean())
            if not np.isfinite(loss) or loss > 1e12:
                self.diverged_ = True  # learning rate too big: each step overshoots further
                break
            if self.tolerance > 0 and self.loss_history_ and self.loss_history_[-1] - loss < self.tolerance:
                self.loss_history_.append(loss)
                break
            self.loss_history_.append(loss)
            grad_w = (2.0 / n) * (Z.T @ error)
            grad_b = (2.0 / n) * error.sum()
            w -= self.learning_rate * grad_w
            b -= self.learning_rate * grad_b

        self.w_ = w
        self.b_ = float(b)
        return self

    def predict(self, X):
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X[:, None]
        return ((X - self.mean_) / self.std_) @ self.w_ + self.b_

    def original_units(self):
        """Undo standardisation: slopes and intercept for the raw feature values."""
        slopes = self.w_ / self.std_
        intercept = self.b_ - float((self.w_ * self.mean_ / self.std_).sum())
        return slopes, intercept

    def to_dict(self):
        return {
            "mean": self.mean_.tolist(),
            "std": self.std_.tolist(),
            "w": self.w_.tolist(),
            "b": self.b_,
        }

    @classmethod
    def from_exact(cls, X, y):
        """Same kind of model, but solved exactly by fit_least_squares instead of gradient
        descent. Used for fast experiments once gradient descent is proven to match."""
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X[:, None]
        slopes, intercept = fit_least_squares(X, y)
        model = cls()
        model.mean_ = np.zeros(X.shape[1])
        model.std_ = np.ones(X.shape[1])
        model.w_ = slopes
        model.b_ = intercept
        model.loss_history_ = []
        return model

    @classmethod
    def from_dict(cls, d):
        model = cls()
        model.mean_ = np.array(d["mean"])
        model.std_ = np.array(d["std"])
        model.w_ = np.array(d["w"])
        model.b_ = float(d["b"])
        return model


def fit_until_match(X, y, learning_rate=0.05, start_epochs=100, max_epochs=1_000_000, match_within=0.01):
    """Train with gradient descent, test against the exact answer, and if it does not
    match yet, double the training time and try again. Returns (model, attempts)
    where attempts is a list of (epochs, largest prediction gap in g/dL)."""
    X = np.asarray(X, dtype=np.float64)
    if X.ndim == 1:
        X = X[:, None]
    exact_slopes, exact_intercept = fit_least_squares(X, y)
    exact_pred = X @ exact_slopes + exact_intercept
    attempts = []
    epochs = start_epochs
    while True:
        model = LinearRegression(learning_rate, epochs).fit(X, y)
        gap = float("inf") if model.diverged_ else float(np.abs(model.predict(X) - exact_pred).max())
        attempts.append((epochs, gap))
        if gap <= match_within or epochs >= max_epochs or model.diverged_:
            return model, attempts
        epochs *= 2
