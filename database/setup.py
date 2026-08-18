from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.student import Base
from models.activity import DailyActivity, StudentBaseline, DriftRecord
from models.notes import TeacherNote 
from models.teacher import Teacher
from models.student_user import StudentUser
DATABASE_URL = "sqlite:///./behavior_drift.db"


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():

    Base.metadata.create_all(bind=engine)
    print("All tables created successfully!")


def get_db():
    """
    This is a helper that gives us a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()