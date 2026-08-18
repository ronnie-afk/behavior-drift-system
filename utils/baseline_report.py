"""
utils/baseline_report.py
=========================
PURPOSE: Print a formatted report of all student baselines.
         Helps you visually confirm drifting students have
         different baselines than healthy ones.

HOW TO RUN DIRECTLY:
    python utils/baseline_report.py
"""

from database.setup import SessionLocal
from models.student import Student
from models.activity import StudentBaseline

DRIFTING_STUDENTS = {
    "Vikram Das", "Kabir Singh", "Amit Gupta",
    "Sanjay Bhatt", "Tanya Chopra"
}


def print_baseline_report():
    
    db = SessionLocal()

    try:
        students  = db.query(Student).all()
        baselines = db.query(StudentBaseline).all()

       
        baseline_map = {b.student_id: b for b in baselines}

        print(f"\n{'=' * 78}")
        print(f"  BASELINE REPORT — what is 'normal' for each student")
        print(f"{'=' * 78}")
        print(
            f"  {'Name':<22} {'Avg Score':>9} {'±':>4} "
            f"{'Avg Mins':>8} {'±':>4} {'Sub %':>6}  Note"
        )
        print(f"  {'-' * 72}")

        for student in students:
            b = baseline_map.get(student.id)

            if b is None:
               
                print(f"  {student.name:<22}  (no baseline yet)")
                continue

           
            marker = " <- DRIFTING" if student.name in DRIFTING_STUDENTS else ""

            print(
                f"  {student.name:<22} "
                f"{b.avg_quiz_score:>9.1f} "
                f"{b.std_quiz_score:>4.1f} "
                f"{b.avg_session_minutes:>8.1f} "
                f"{b.std_session_minutes:>4.1f} "
                f"{b.submission_rate * 100:>5.0f}% "
                f"{marker}"
            )

        print(f"\n  Column guide:")
        print(f"  Avg Score = mean quiz score over last 30 days")
        print(f"  ± after score = std deviation (normal variation)")
        print(f"  Avg Mins  = mean session minutes per day")
        print(f"  Sub %     = percentage of assignments submitted\n")

    finally:
        db.close()


if __name__ == "__main__":
    print_baseline_report()