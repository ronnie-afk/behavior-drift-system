"""
HOW TO RUN:
    python utils/teacher_setup.py

Default accounts created:
  admin     / admin2024    → sees ALL students
  teacher1  / pass1234     → sees Data Science only
  teacher2  / pass1234     → sees Machine Learning only
  teacher3  / pass1234     → sees Web Development only
"""

from database.setup import SessionLocal, create_tables
from models.teacher import Teacher


DEFAULT_TEACHERS = [
    ("admin",    "admin2024", "Admin Teacher",    "all"),
    ("teacher1", "pass1234",  "Data Science Lead", "Data Science"),
    ("teacher2", "pass1234",  "ML Instructor",     "Machine Learning"),
    ("teacher3", "pass1234",  "Web Dev Coach",     "Web Development"),
]


def create_default_teachers():
    create_tables()  
    db = SessionLocal()
    try:
        for username, password, full_name, course in DEFAULT_TEACHERS:
            existing = db.query(Teacher).filter(
                Teacher.username == username
            ).first()

            if existing:
                print(f"  {username} already exists — skipped.")
                continue

            teacher = Teacher(
                username      = username,
                password_hash = Teacher.hash_password(password),
                full_name     = full_name,
                course        = course,
            )
            db.add(teacher)
            print(f"  Created: {username} / {password}  [{course}]")

        db.commit()
        print("\nAll teacher accounts ready.")
    finally:
        db.close()


if __name__ == "__main__":
    create_default_teachers()