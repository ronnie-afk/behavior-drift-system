"""
utils/baseline_calculator.py
=============================
PURPOSE: Read each student's last 30 days of activity and calculate
         their personal "normal" baseline. Save the result into
         the student_baselines table.

WHY 30 DAYS?
  - Too few days (e.g. 7) → baseline is noisy, one bad week skews it
  - Too many days (e.g. 60) → old behavior dilutes recent patterns
  - 30 days is the sweet spot for detecting recent drift
"""

import statistics                         
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.student import Student
from models.activity import DailyActivity, StudentBaseline


BASELINE_WINDOW_DAYS = 30


def calculate_baseline_for_student(db: Session, student: Student) -> dict:
    """
    Reads the last 30 days of activity for ONE student and
    returns a dictionary of their baseline numbers.

    Returns None if the student has fewer than 7 days of data
    (not enough history to build a meaningful baseline).
    """


    cutoff_date = datetime.utcnow() - timedelta(days=BASELINE_WINDOW_DAYS)

    # Fetch all activity rows for this student in the last 30 days
    # .filter() narrows down which rows we want
    # .order_by() sorts them oldest to newest
    activities = (
        db.query(DailyActivity)
        .filter(
            DailyActivity.student_id == student.id,
            DailyActivity.date >= cutoff_date     
        )
        .order_by(DailyActivity.date)
        .all()
    )

    if len(activities) < 7:
        print(f"  Skipping {student.name} — not enough data ({len(activities)} days)")
        return None

    # ── Extract each metric into its own list ──────────────────────────
    # List comprehension: [expression for item in list if condition]
    # The 'if a.quiz_score is not None' skips days with no quiz

    scores   = [a.quiz_score      for a in activities if a.quiz_score is not None]
    minutes  = [a.session_minutes for a in activities]
    logins   = [a.login_count     for a in activities]
    submits  = [a.submitted       for a in activities]

    # ── Calculate mean (average) for each metric ───────────────────────
    # statistics.mean() adds up all values and divides by count
    avg_score   = statistics.mean(scores)   if scores   else 0.0
    avg_minutes = statistics.mean(minutes)  if minutes  else 0.0
    avg_logins  = statistics.mean(logins)   if logins   else 0.0

    sub_rate = sum(submits) / len(submits) if submits else 0.0

    std_score   = statistics.stdev(scores)   if len(scores)   >= 2 else 0.0
    std_minutes = statistics.stdev(minutes)  if len(minutes)  >= 2 else 0.0

    return {
        "avg_quiz_score":      round(avg_score,   2),
        "avg_session_minutes": round(avg_minutes, 2),
        "avg_logins_per_day":  round(avg_logins,  2),
        "submission_rate":     round(sub_rate,    3),
        "std_quiz_score":      round(std_score,   2),
        "std_session_minutes": round(std_minutes, 2),
    }


def save_baseline(db: Session, student: Student, baseline_data: dict) -> None:
    """
    Saves (or updates) the baseline for one student in the database.

    We use "upsert" logic:
      - If a baseline already exists for this student → UPDATE it
      - If no baseline exists yet → CREATE a new one
    This is safe to run multiple times.
    """
    existing = (
        db.query(StudentBaseline)
        .filter(StudentBaseline.student_id == student.id)
        .first()
    )

    if existing:
        existing.avg_quiz_score      = baseline_data["avg_quiz_score"]
        existing.avg_session_minutes = baseline_data["avg_session_minutes"]
        existing.avg_logins_per_day  = baseline_data["avg_logins_per_day"]
        existing.submission_rate     = baseline_data["submission_rate"]
        existing.std_quiz_score      = baseline_data["std_quiz_score"]
        existing.std_session_minutes = baseline_data["std_session_minutes"]
        existing.last_updated        = datetime.utcnow()
    else:
        baseline = StudentBaseline(
            student_id           = student.id,
            avg_quiz_score       = baseline_data["avg_quiz_score"],
            avg_session_minutes  = baseline_data["avg_session_minutes"],
            avg_logins_per_day   = baseline_data["avg_logins_per_day"],
            submission_rate      = baseline_data["submission_rate"],
            std_quiz_score       = baseline_data["std_quiz_score"],
            std_session_minutes  = baseline_data["std_session_minutes"],
            last_updated         = datetime.utcnow(),
        )
        db.add(baseline)

    db.commit()


def calculate_all_baselines(db: Session) -> None:

    students = db.query(Student).all()
    print(f"  Calculating baselines for {len(students)} students...\n")

    success_count = 0

    for student in students:

        baseline_data = calculate_baseline_for_student(db, student)

        if baseline_data is None:
            continue   

        save_baseline(db, student, baseline_data)
        success_count += 1


        print(
            f"  {student.name:<22} "
            f"avg score: {baseline_data['avg_quiz_score']:>5.1f}  "
            f"avg mins: {baseline_data['avg_session_minutes']:>5.1f}  "
            f"sub rate: {baseline_data['submission_rate'] * 100:>4.0f}%"
        )

    print(f"\n  Baselines saved for {success_count} students.")