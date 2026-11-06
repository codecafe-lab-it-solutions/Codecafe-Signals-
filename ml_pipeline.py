"""System 2.C & 2.H: Machine Learning Training & Barrier Odds Pipeline.
Extracts chronological technical features, labels barriers via Triple Barrier Method,
trains HistGradientBoostingClassifier / RandomForest without lookahead bias,
and predicts calibrated barrier-touch probabilities.
"""
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any
import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score

from signals import atr_series, ema, rsi_series

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODEL_FILE = MODELS_DIR / "barrier_classifier.joblib"


def extract_features(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Extract chronological statistical and technical features from price series."""
    n = len(close)
    if n < 10:
        return np.empty((0, 7))

    warmup = min(20, n // 2)
    e10 = ema(close, min(10, warmup))
    e20 = ema(close, min(20, warmup))
    e50 = ema(close, min(50, warmup))
    atrs = atr_series(high, low, close, min(14, warmup))
    rsis = rsi_series(close, min(14, warmup))

    features = []
    start_idx = max(5, warmup)
    for i in range(start_idx, n):
        c = close[i]
        ret_1 = (c - close[i - 1]) / close[i - 1]
        ret_5 = (c - close[i - min(5, i)]) / close[i - min(5, i)]
        ema_ratio_1 = (e10[i] - e20[i]) / c
        ema_ratio_2 = (e20[i] - e50[i]) / c
        vol_ratio = (atrs[i] / c) if not np.isnan(atrs[i]) else 0.01
        rsi_val = (rsis[i] / 100.0) if not np.isnan(rsis[i]) else 0.5
        range_norm = (high[i] - low[i]) / c

        features.append([ret_1, ret_5, ema_ratio_1, ema_ratio_2, vol_ratio, rsi_val, range_norm])

    return np.array(features)


def label_triple_barrier(high: np.ndarray, low: np.ndarray, close: np.ndarray, horizon: int = 10, rr_ratio: float = 2.0) -> np.ndarray:
    """Triple Barrier Labeling:
    1 if Take-Profit barrier (+2.0 * ATR) is touched before Stop-Loss (-1.0 * ATR).
    0 otherwise.
    """
    n = len(close)
    atrs = atr_series(high, low, close, 14)
    labels = []

    for i in range(50, n):
        if i + horizon >= n:
            break
        entry = close[i]
        atr = atrs[i] if not np.isnan(atrs[i]) else (high[i] - low[i])
        tp = entry + rr_ratio * atr
        sl = entry - 1.0 * atr

        label = 0
        for step in range(1, horizon + 1):
            future_idx = i + step
            if high[future_idx] >= tp:
                label = 1
                break
            if low[future_idx] <= sl:
                label = 0
                break
        labels.append(label)

    return np.array(labels)


@dataclass
class ModelEvaluation:
    train_samples: int
    test_samples: int
    accuracy: float
    roc_auc: float
    brier_score: float
    model_version: str


def train_barrier_model(candles: dict, horizon: int = 10, test_split: float = 0.3) -> ModelEvaluation:
    """Train ML classifier with strict chronological out-of-sample split (no lookahead bias)."""
    close = np.asarray(candles["close"], dtype=float)
    high = np.asarray(candles["high"], dtype=float)
    low = np.asarray(candles["low"], dtype=float)

    X_all = extract_features(high, low, close)
    y_all = label_triple_barrier(high, low, close, horizon=horizon)

    min_len = min(len(X_all), len(y_all))
    X = X_all[:min_len]
    y = y_all[:min_len]

    if min_len < 40:
        raise ValueError(f"Insufficient samples to train ML model: {min_len} < 40")

    # Chronological split (first 70% train, last 30% out-of-sample test)
    split_idx = int(min_len * (1.0 - test_split))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    model = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.05, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1] if len(model.classes_) > 1 else np.zeros(len(X_test))

    acc = round(float(accuracy_score(y_test, preds)), 3)
    auc = round(float(roc_auc_score(y_test, probs)), 3) if len(np.unique(y_test)) > 1 else 0.50
    brier = round(float(brier_score_loss(y_test, probs)), 3)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_FILE)

    return ModelEvaluation(
        train_samples=len(X_train),
        test_samples=len(X_test),
        accuracy=acc,
        roc_auc=auc,
        brier_score=brier,
        model_version="HistGradientBoost-v1",
    )


def predict_barrier_probability(candles: dict) -> dict[str, Any]:
    """Inference: Predict probability of reaching profit barrier on latest candle."""
    close = np.asarray(candles["close"], dtype=float)
    high = np.asarray(candles["high"], dtype=float)
    low = np.asarray(candles["low"], dtype=float)

    if not MODEL_FILE.exists():
        # Auto-train default model if not exists
        try:
            train_barrier_model(candles)
        except Exception:
            return {"barrier_win_probability": 0.50, "is_high_probability_setup": False, "model_loaded": False}

    try:
        model = joblib.load(MODEL_FILE)
        X = extract_features(high, low, close)
        if len(X) == 0:
            return {"barrier_win_probability": 0.50, "is_high_probability_setup": False, "model_loaded": True}

        latest_features = X[-1].reshape(1, -1)
        probs = model.predict_proba(latest_features)[0]
        win_prob = float(probs[1]) if len(probs) > 1 else 0.50

        return {
            "barrier_win_probability": round(win_prob, 3),
            "is_high_probability_setup": bool(win_prob >= 0.60),
            "model_loaded": True,
        }
    except Exception:
        return {"barrier_win_probability": 0.50, "is_high_probability_setup": False, "model_loaded": False}
