"""
========================
PURPOSE: Compare each student's recent activity against their baseline
         and calculate a drift score between 0 (fine) and 1 (severe drift).
         Save results to the drift_records table.
         Flag students whose drift score exceeds the alert threshold.

KEY CONCEPT — Z-SCORE:
  z = (recent_average - baseline_mean) / baseline_std_dev
  A large negative z means the student dropped far below their normal.
  We cap and convert z into a 0-1 scale so scores are easy to compare.
"""

import statistics
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.student import Student
from models.activity import DailyActivity, StudentBaseline, DriftRecord


# ── Configuration ──────────────────────────────────────────────────────

RECENT_WINDOW_DAYS = 7


ALERT_THRESHOLD = 0.35


WEIGHTS = {
    "score":      0.40,   # 40% — quiz performance
    "session":    0.35,   # 35% — time spent studying
    "submission": 0.25,   # 25% — assignment completion
}


# ── Helper functions ────────────────────────────────────────────────────

def compute_z_score(recent_avg: float, baseline_mean: float, baseline_std: float) -> float:
    
    if baseline_std == 0:
        return 0.0
    return (recent_avg - baseline_mean) / baseline_std


def z_to_drift(z: float) -> float:
 
    return min(1.0, max(0.0, -z / 4.0))


def get_recent_averages(db: Session, student_id: int) -> dict | None:
    
    cutoff = datetime.utcnow() - timedelta(days=RECENT_WINDOW_DAYS)

    activities = (
        db.query(DailyActivity)
        .filter(
            DailyActivity.student_id == student_id,
            DailyActivity.date >= cutoff
        )
        .order_by(DailyActivity.date)
        .all()
    )

   
    if len(activities) < 3:
        return None

    scores   = [a.quiz_score      for a in activities if a.quiz_score is not None]
    minutes  = [a.session_minutes for a in activities]
    submits  = [a.submitted       for a in activities]

    return {
        "avg_score":    statistics.mean(scores)            if scores   else 0.0,
        "avg_minutes":  statistics.mean(minutes)           if minutes  else 0.0,
        "sub_rate":     sum(submits) / len(submits)        if submits  else 0.0,
        "days_counted": len(activities),
    }


# ── Core detection function ─────────────────────────────────────────────

def detect_drift_for_student(
    db: Session,
    student: Student,
    baseline: StudentBaseline
) -> dict | None:
    

    recent = get_recent_averages(db, student.id)
    if recent is None:
        return None

    
    z_score   = compute_z_score(
        recent["avg_score"],
        baseline.avg_quiz_score,
        baseline.std_quiz_score
    )
    score_drift = z_to_drift(z_score)


    z_session = compute_z_score(
        recent["avg_minutes"],
        baseline.avg_session_minutes,
        baseline.std_session_minutes
    )
    session_drift = z_to_drift(z_session)

  
    baseline_sub  = baseline.submission_rate
    recent_sub    = recent["sub_rate"]
    if baseline_sub > 0:
        
        raw_drop = (baseline_sub - recent_sub) / baseline_sub
        submission_drift = min(1.0, max(0.0, raw_drop))
    else:
        submission_drift = 0.0

    final_drift = (
        WEIGHTS["score"]      * score_drift      +
        WEIGHTS["session"]    * session_drift     +
        WEIGHTS["submission"] * submission_drift
    )


    signals = []
    if score_drift   > 0.4:  signals.append(f"score dropped (z={z_score:.1f})")
    if session_drift > 0.4:  signals.append(f"study time dropped (z={z_session:.1f})")
    if submission_drift > 0.4: signals.append(f"missing submissions")
    notes = "; ".join(signals) if signals else "within normal range"

    return {
        "drift_score":       round(final_drift,      3),
        "score_drift":       round(score_drift,       3),
        "session_drift":     round(session_drift,     3),
        "submission_drift":  round(submission_drift,  3),
        "alert_triggered":   1 if final_drift >= ALERT_THRESHOLD else 0,
        "notes":             notes,
    }


def save_drift_record(db: Session, student: Student, result: dict) -> None:
  
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    existing = (
        db.query(DriftRecord)
        .filter(
            DriftRecord.student_id == student.id,
            DriftRecord.date == today
        )
        .first()
    )

    if existing:
        
        existing.drift_score      = result["drift_score"]
        existing.score_drift      = result["score_drift"]
        existing.session_drift    = result["session_drift"]
        existing.submission_drift = result["submission_drift"]
        existing.alert_triggered  = result["alert_triggered"]
        existing.notes            = result["notes"]
    else:
    
        record = DriftRecord(
            student_id       = student.id,
            date             = today,
            drift_score      = result["drift_score"],
            score_drift      = result["score_drift"],
            session_drift    = result["session_drift"],
            submission_drift = result["submission_drift"],
            alert_triggered  = result["alert_triggered"],
            notes            = result["notes"],
        )
        db.add(record)

    db.commit()


# ── Main function ───────────────────────────────────────────────────────

def run_drift_detection(db: Session) -> None:
    """
    Runs drift detection for ALL students who have a baseline.
    Prints a results table and highlights students who need attention.
    Called from main.py.
    """

   
    students  = db.query(Student).all()
    baselines = db.query(StudentBaseline).all()

   
    baseline_map = {b.student_id: b for b in baselines}

    print(f"  Running drift detection for {len(students)} students...\n")
    print(
        f"  {'Name':<22} {'Drift':>6} {'Score':>6} "
        f"{'Session':>8} {'Submit':>7}  Status"
    )
    print(f"  {'-' * 68}")

    alerted = []   

    for student in students:
        baseline = baseline_map.get(student.id)

        if baseline is None:
            print(f"  {student.name:<22}  (no baseline — skipping)")
            continue

       
        result = detect_drift_for_student(db, student, baseline)

        if result is None:
            print(f"  {student.name:<22}  (not enough recent data)")
            continue

    
        save_drift_record(db, student, result)

    
        if result["alert_triggered"]:
            status = "*** ALERT ***"
            alerted.append(student.name)
        elif result["drift_score"] > 0.25:
            status = "watch"
        else:
            status = "ok"

        print(
            f"  {student.name:<22} "
            f"{result['drift_score']:>6.3f} "
            f"{result['score_drift']:>6.3f} "
            f"{result['session_drift']:>8.3f} "
            f"{result['submission_drift']:>7.3f}  "
            f"{status}"
        )


    print(f"\n{'=' * 55}")
    if alerted:
        print(f"  STUDENTS NEEDING ATTENTION ({len(alerted)} found):")
        for name in alerted:
            print(f"    - {name}")
    else:
        print(f"  No students currently above alert threshold.")
    print(f"{'=' * 55}\n")