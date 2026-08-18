
from database.setup import SessionLocal
from models.student import Student
from models.activity import DailyActivity


def print_summary():
    """
    Prints a summary of everything currently in the database.
    """
    db = SessionLocal()

    try:
        students = db.query(Student).all()
        print(f"\n{'='*55}")
        print(f"  DATABASE SUMMARY")
        print(f"{'='*55}")
        print(f"  Total students : {len(students)}")

        total_activities = db.query(DailyActivity).count()
        print(f"  Total activity rows: {total_activities}")
        print(f"{'='*55}\n")

        print(f"  {'Name':<22} {'Course':<18} {'Days':<6} {'Avg Score':<12} {'Avg Mins'}")
        print(f"  {'-'*70}")

        for student in students:
            activities = (
                db.query(DailyActivity)
                .filter(DailyActivity.student_id == student.id)
                .all()
            )

            if not activities:
                continue

            scores  = [a.quiz_score for a in activities if a.quiz_score is not None]
            minutes = [a.session_minutes for a in activities]

            avg_score = sum(scores)  / len(scores)  if scores  else 0
            avg_mins  = sum(minutes) / len(minutes) if minutes else 0

            print(
                f"  {student.name:<22} {student.course:<18} "
                f"{len(activities):<6} {avg_score:<12.1f} {avg_mins:.1f}"
            )

        print()

    finally:
        db.close()


if __name__ == "__main__":
    print_summary()