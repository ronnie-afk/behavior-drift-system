import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.student import Student
from models.activity import DailyActivity


random.seed(42)



STUDENT_PROFILES = [
    ("Arjun Sharma",     "arjun@school.edu",    "Data Science"),
    ("Priya Patel",      "priya@school.edu",    "Data Science"),
    ("Rohan Mehta",      "rohan@school.edu",    "Data Science"),
    ("Sneha Iyer",       "sneha@school.edu",    "Machine Learning"),
    ("Vikram Das",       "vikram@school.edu",   "Machine Learning"),
    ("Ananya Roy",       "ananya@school.edu",   "Machine Learning"),
    ("Kabir Singh",      "kabir@school.edu",    "Web Development"),
    ("Divya Nair",       "divya@school.edu",    "Web Development"),
    ("Aditya Kumar",     "aditya@school.edu",   "Web Development"),
    ("Meera Joshi",      "meera@school.edu",    "Web Development"),
    ("Ravi Verma",       "ravi@school.edu",     "Data Science"),
    ("Pooja Reddy",      "pooja@school.edu",    "Machine Learning"),
    ("Amit Gupta",       "amit@school.edu",     "Data Science"),
    ("Sunita Rao",       "sunita@school.edu",   "Web Development"),
    ("Deepak Nambiar",   "deepak@school.edu",   "Machine Learning"),
    ("Lakshmi Pillai",   "lakshmi@school.edu",  "Data Science"),
    ("Nikhil Banerjee",  "nikhil@school.edu",   "Web Development"),
    ("Geeta Mishra",     "geeta@school.edu",    "Machine Learning"),
    ("Sanjay Bhatt",     "sanjay@school.edu",   "Data Science"),
    ("Tanya Chopra",     "tanya@school.edu",    "Web Development"),
]


DRIFTING_STUDENTS = {
    "Vikram Das", "Kabir Singh", "Amit Gupta", "Sanjay Bhatt", "Tanya Chopra"
}

def normal_day(student_name: str) -> dict:
    """
    Returns a dictionary of realistic activity numbers for a healthy student.
    I use random.gauss() which gives a "bell curve" distribution —
    most values cluster around the average, with natural variation.
    """

    
    logins   = max(1, round(random.gauss(1.5, 0.5)))      
    minutes  = max(10, random.gauss(45, 10))               
    score    = min(100, max(40, random.gauss(78, 8)))      
    submitted = 1 if random.random() > 0.15 else 0        
    return {
        "login_count":     logins,
        "session_minutes": round(minutes, 1),
        "quiz_score":      round(score, 1),
        "submitted":       submitted,
    }


def drifting_day(day_number: int) -> dict:
    """
    Returns activity numbers for a student who is drifting.
    The drift gets WORSE over time — day 45 is mild, day 60 is severe.
    This makes the pattern more realistic (students don't crash overnight).

    day_number is 0-based from the start of the 60 days.
    Drift starts at day 44 (the 45th day, 0-indexed).
    """

  
    drift_depth = max(0, day_number - 44)         
    severity    = drift_depth / 15                 

    
    logins   = max(0, round(random.gauss(1.5 - severity, 0.5)))
    minutes  = max(0, random.gauss(45 - 35 * severity, 8))  
    score    = max(20, random.gauss(78 - 40 * severity, 10)) 
    submitted = 1 if random.random() > (0.15 + 0.6 * severity) else 0 

    return {
        "login_count":     logins,
        "session_minutes": round(minutes, 1),
        "quiz_score":      round(score, 1),
        "submitted":       submitted,
    }

def create_students(db: Session) -> list:
    """
    Inserts all 20 fake students into the database.
    Returns the list of Student objects so we can use their IDs next.
    """
    students = []

    for name, email, course in STUDENT_PROFILES:
       
        existing = db.query(Student).filter(Student.email == email).first()
        if existing:
            students.append(existing)
            continue

        student = Student(name=name, email=email, course=course)
        db.add(student)       
        students.append(student)

    db.commit()               
    for s in students:
        db.refresh(s)

    print(f"Created {len(students)} students.")
    return students


def create_activities(db: Session, students: list) -> None:
    """
    For each student, generates 60 days of activity data.
    Starts 60 days ago and goes up to today.
    Drifting students get normal data for days 0-44,
    then deteriorating data for days 45-59.
    """
    today      = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = today - timedelta(days=60)   

    total_rows = 0

    for student in students:
        is_drifting = student.name in DRIFTING_STUDENTS

        for day_index in range(60):
            date = start_date + timedelta(days=day_index)

            
            existing = (
                db.query(DailyActivity)
                .filter(
                    DailyActivity.student_id == student.id,
                    DailyActivity.date == date
                )
                .first()
            )
            if existing:
                continue

           
            if is_drifting and day_index >= 44:
                activity_data = drifting_day(day_index)
            else:
                activity_data = normal_day(student.name)

        
            activity = DailyActivity(
                student_id      = student.id,
                date            = date,
                login_count     = activity_data["login_count"],
                session_minutes = activity_data["session_minutes"],
                quiz_score      = activity_data["quiz_score"],
                submitted       = activity_data["submitted"],
            )
            db.add(activity)
            total_rows += 1

        
        db.commit()
        status = "DRIFTING" if is_drifting else "healthy"
        print(f"  {student.name:<20} [{status}] — 60 days inserted")

    print(f"\nTotal activity rows created: {total_rows}")