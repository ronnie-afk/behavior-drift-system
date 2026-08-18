

import io
from datetime import datetime
from sqlalchemy.orm import Session
from models.student import Student
from models.activity import DailyActivity

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def import_from_bytes(file_bytes: bytes, filename: str, db: Session) -> dict:
    

    if not PANDAS_AVAILABLE:
        return {
            "success": False,
            "error": "pandas is not installed. Run: pip install pandas openpyxl"
        }

    # ── Read the file into a DataFrame ──────────────────────────────────
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            return {"success": False, "error": "Only .csv and .xlsx files are supported."}
    except Exception as e:
        return {"success": False, "error": f"Could not read file: {str(e)}"}

    # ── Normalise column names ───────────────────────────────────────────
   
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required = {"name", "email", "course", "date",
                "login_count", "session_minutes", "submitted"}
    missing = required - set(df.columns)
    if missing:
        return {
            "success": False,
            "error": f"Missing required columns: {', '.join(missing)}"
        }

    # ── Import rows ──────────────────────────────────────────────────────
    students_created = 0
    rows_imported    = 0
    rows_skipped     = 0
    errors           = []

    student_cache: dict[str, Student] = {}

    for i, row in df.iterrows():
        try:
        
            try:
                date = pd.to_datetime(row["date"]).to_pydatetime()
                date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            except Exception:
                errors.append(f"Row {i+2}: invalid date '{row['date']}'")
                continue

            email = str(row["email"]).strip().lower()

        
            if email not in student_cache:
                existing = db.query(Student).filter(Student.email == email).first()
                if existing:
                    student_cache[email] = existing
                else:
                    new_student = Student(
                        name   = str(row["name"]).strip(),
                        email  = email,
                        course = str(row["course"]).strip(),
                    )
                    db.add(new_student)
                    db.flush()   
                    student_cache[email] = new_student
                    students_created += 1

            student = student_cache[email]

            already = (
                db.query(DailyActivity)
                .filter(
                    DailyActivity.student_id == student.id,
                    DailyActivity.date == date
                )
                .first()
            )
            if already:
                rows_skipped += 1
                continue

            quiz_score = None
            if "quiz_score" in df.columns:
                val = row.get("quiz_score")
                if pd.notna(val):
                    quiz_score = float(val)

            activity = DailyActivity(
                student_id      = student.id,
                date            = date,
                login_count     = int(row.get("login_count", 0)),
                session_minutes = float(row.get("session_minutes", 0.0)),
                quiz_score      = quiz_score,
                submitted       = int(row.get("submitted", 0)),
            )
            db.add(activity)
            rows_imported += 1

        except Exception as e:
            errors.append(f"Row {i+2}: {str(e)}")
            continue

    db.commit()

    return {
        "success":          True,
        "students_created": students_created,
        "rows_imported":    rows_imported,
        "rows_skipped":     rows_skipped,
        "errors":           errors,
    }