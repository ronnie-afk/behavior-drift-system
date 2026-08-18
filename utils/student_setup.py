"""
utils/student_setup.py
=======================
PURPOSE: Creates student login accounts for the student portal.
         Generates one login per student using their first name
         as the username and a simple default password.

HOW TO RUN (once):
    python utils/student_setup.py

DEFAULT CREDENTIALS (change after first login):
    Username: student's first name in lowercase (e.g. arjun, priya)
    Password: student123

After running, students can log in at:
    http://127.0.0.1:8000/student-login
"""

from database.setup import SessionLocal, create_tables
from models.student import Student
from models.student_user import StudentUser

DEFAULT_PASSWORD = "student123"


def create_student_accounts():
    create_tables()
    db = SessionLocal()
    try:
        students = db.query(Student).all()

        if not students:
            print("  No students found. Run python main.py first.")
            return

        created = 0
        for student in students:
            # Check if account already exists
            existing = db.query(StudentUser).filter(
                StudentUser.student_id == student.id
            ).first()
            if existing:
                continue

            # Username = first name lowercase
            username = student.name.split()[0].lower()

            # If username already taken add a number
            base_username = username
            counter = 1
            while db.query(StudentUser).filter(
                StudentUser.username == username
            ).first():
                username = f"{base_username}{counter}"
                counter += 1

            account = StudentUser(
                student_id    = student.id,
                username      = username,
                password_hash = StudentUser.hash_password(DEFAULT_PASSWORD),
            )
            db.add(account)
            created += 1
            print(f"  {student.name:<22} → username: {username:<15} password: {DEFAULT_PASSWORD}")

        db.commit()
        print(f"\n  {created} student accounts created.")
        print(f"  Students can log in at: http://127.0.0.1:8000/student-login\n")

    finally:
        db.close()


if __name__ == "__main__":
    create_student_accounts()