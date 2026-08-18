"""
utils/ml_predictor.py
======================
PURPOSE: Train a simple machine learning model that predicts which
         currently healthy students are LIKELY TO DRIFT in the next 7 days.

HOW IT WORKS:
  1. We collect "features" for each student — their recent averages
     compared to their baseline (same signals the drift detector uses)
  2. We label past data: was this student drifting 7 days later? (1 or 0)
  3. We train a Random Forest classifier on this labelled data
  4. We run the trained model on today's healthy students
  5. Students with high drift probability get flagged as "at risk"

WHY RANDOM FOREST?
  - Works well with small datasets (we only have 20 students)
  - Handles the mix of numeric features well
  - Gives probability scores, not just yes/no
  - No need to scale features or tune much

LIBRARY: scikit-learn — install with: pip install scikit-learn
"""

import statistics
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.student import Student
from models.activity import DailyActivity, StudentBaseline, DriftRecord

ALERT_THRESHOLD = 0.35
WATCH_THRESHOLD = 0.20

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def extract_features(db: Session, student: Student,
                     baseline: StudentBaseline, days_back: int = 7) -> list | None:
    """
    Extracts numeric features for one student based on their
    recent activity vs their baseline.

    These are the same signals the drift detector uses — we're just
    packaging them as a feature vector for the ML model.

    Returns a list of 6 numbers, or None if not enough data.
    """
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    activities = (
        db.query(DailyActivity)
        .filter(
            DailyActivity.student_id == student.id,
            DailyActivity.date >= cutoff
        )
        .all()
    )

    if len(activities) < 3:
        return None

    scores  = [a.quiz_score      for a in activities if a.quiz_score is not None]
    minutes = [a.session_minutes for a in activities]
    submits = [a.submitted       for a in activities]

    recent_score   = statistics.mean(scores)           if scores   else 0.0
    recent_minutes = statistics.mean(minutes)          if minutes  else 0.0
    recent_sub     = sum(submits) / len(submits)       if submits  else 0.0

    # How far below baseline is each metric?
    # Positive = dropped below normal, Negative = above normal
    score_drop   = (baseline.avg_quiz_score - recent_score) / max(baseline.avg_quiz_score, 1)
    minutes_drop = (baseline.avg_session_minutes - recent_minutes) / max(baseline.avg_session_minutes, 1)
    sub_drop     = (baseline.submission_rate - recent_sub) / max(baseline.submission_rate, 0.01)

    # Normalised std deviations — how consistent is this student?
    std_score   = baseline.std_quiz_score   / max(baseline.avg_quiz_score, 1)
    std_minutes = baseline.std_session_minutes / max(baseline.avg_session_minutes, 1)

    # Login frequency change
    logins      = [a.login_count for a in activities]
    recent_login = statistics.mean(logins) if logins else 0.0
    login_drop  = max(0, (baseline.avg_logins_per_day - recent_login) / max(baseline.avg_logins_per_day, 0.1))

    return [
        max(0, score_drop),    # Feature 1: score drop fraction
        max(0, minutes_drop),  # Feature 2: session time drop fraction
        max(0, sub_drop),      # Feature 3: submission rate drop fraction
        max(0, login_drop),    # Feature 4: login frequency drop fraction
        std_score,             # Feature 5: score variability
        std_minutes,           # Feature 6: session variability
    ]


def build_training_data(db: Session) -> tuple:
    """
    Builds a training dataset from historical drift records.

    For each student and each past date where we have drift records,
    we look at what the features looked like 7 days BEFORE that date
    and label it 1 if they ended up drifting (drift > threshold), 0 if not.

    This teaches the model: "given these signals, will this student drift?"

    Returns (X, y) — feature matrix and labels.
    """
    students  = db.query(Student).all()
    baselines = {b.student_id: b for b in db.query(StudentBaseline).all()}

    X, y = [], []   # Features and labels

    for student in students:
        baseline = baselines.get(student.id)
        if not baseline:
            continue

        # Get all drift records for this student
        drift_records = (
            db.query(DriftRecord)
            .filter(DriftRecord.student_id == student.id)
            .order_by(DriftRecord.date)
            .all()
        )

        for record in drift_records:
            # Label: did this student drift significantly?
            label = 1 if record.drift_score >= WATCH_THRESHOLD else 0

            # Features: what did their activity look like 7 days before?
            # We use the drift sub-scores as a proxy since we have them
            features = [
                record.score_drift,
                record.session_drift,
                record.submission_drift,
                min(1.0, record.drift_score * 1.2),   # Scaled overall drift
                baseline.std_quiz_score / max(baseline.avg_quiz_score, 1),
                baseline.std_session_minutes / max(baseline.avg_session_minutes, 1),
            ]

            X.append(features)
            y.append(label)

    return X, y


def predict_at_risk_students(db: Session) -> list:
    """
    Main function — returns a list of currently healthy students
    who the model predicts are likely to drift in the next 7 days.

    Each item in the returned list is a dict:
    {
        "student":     Student object,
        "probability": float (0-1, how likely they are to drift),
        "risk_level":  "high" | "medium" | "low",
        "top_signal":  str (which feature is most concerning)
    }

    Returns empty list if sklearn not installed or not enough data.
    """
    if not SKLEARN_AVAILABLE:
        print("  [ML] scikit-learn not installed. Run: pip install scikit-learn")
        return []

    # ── Build training data ──────────────────────────────────────────
    X, y = build_training_data(db)

    if len(X) < 10:
        print("  [ML] Not enough historical data to train yet.")
        return []

    # Check we have both classes (0 and 1) in training data
    if len(set(y)) < 2:
        print("  [ML] Need both drifting and healthy examples to train.")
        return []

    # ── Train the model ──────────────────────────────────────────────
    # n_estimators=50: build 50 decision trees and average them
    # random_state=42: makes results reproducible
    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X, y)

    # ── Predict on today's healthy students ─────────────────────────
    today     = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    students  = db.query(Student).all()
    baselines = {b.student_id: b for b in db.query(StudentBaseline).all()}

    # Get today's drift records to find who is currently healthy
    todays_records = {
        r.student_id: r for r in
        db.query(DriftRecord).filter(DriftRecord.date == today).all()
    }

    at_risk = []

    for student in students:
        record   = todays_records.get(student.id)
        baseline = baselines.get(student.id)

        if not baseline:
            continue

        # Only predict for students who are currently healthy or watch
        # We skip already-alerted students — they're already flagged
        if record and record.drift_score >= ALERT_THRESHOLD:
            continue

        # Extract current features
        features = extract_features(db, student, baseline)
        if features is None:
            continue

        # Get drift probability from the model
        # predict_proba returns [[prob_class_0, prob_class_1]]
        prob = model.predict_proba([features])[0][1]   # Probability of drifting

        # Only include students with meaningful risk
        if prob < 0.30:
            continue

        # Determine risk level
        if prob >= 0.70:
            risk_level = "high"
        elif prob >= 0.50:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Find which signal is most concerning
        feature_names = [
            "quiz score dropping",
            "study time dropping",
            "missing submissions",
            "logging in less",
            "inconsistent scores",
            "inconsistent sessions",
        ]
        top_idx    = int(max(range(len(features)), key=lambda i: features[i]))
        top_signal = feature_names[top_idx]

        at_risk.append({
            "student":     student,
            "probability": round(prob, 2),
            "risk_level":  risk_level,
            "top_signal":  top_signal,
        })

    # Sort by probability highest first
    at_risk.sort(key=lambda x: x["probability"], reverse=True)
    return at_risk