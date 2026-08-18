from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from datetime import datetime
from models.student import Base


class DailyActivity(Base):
    """
    One row = one day of activity for one student.
    This is the raw data we collect every day.
    """
    __tablename__ = "daily_activities"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    student_id      = Column(Integer, ForeignKey("students.id"), nullable=False) 
    date            = Column(DateTime, nullable=False)                            
    login_count     = Column(Integer, default=0)    
    session_minutes = Column(Float,   default=0.0)  
    quiz_score      = Column(Float,   nullable=True) 
    submitted       = Column(Integer, default=0)    


class StudentBaseline(Base):
    """
    One row per student = their 'normal' calculated from recent history.
    I update this regularly. Used to compare against new data.
    """
    __tablename__ = "student_baselines"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    student_id              = Column(Integer, ForeignKey("students.id"), unique=True)
    avg_session_minutes     = Column(Float, default=0.0)   
    avg_quiz_score          = Column(Float, default=0.0)   
    avg_logins_per_day      = Column(Float, default=0.0)   
    submission_rate         = Column(Float, default=0.0)   
    std_session_minutes     = Column(Float, default=0.0)  
    std_quiz_score          = Column(Float, default=0.0)   
    last_updated            = Column(DateTime, default=datetime.utcnow)


class DriftRecord(Base):
    """
    One row = one drift detection result for one student on one day.
    Stores the drift score and which signals triggered it.
    """
    __tablename__ = "drift_records"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    student_id      = Column(Integer, ForeignKey("students.id"), nullable=False)
    date            = Column(DateTime, nullable=False)
    drift_score     = Column(Float, default=0.0)    
    score_drift     = Column(Float, default=0.0)    
    session_drift   = Column(Float, default=0.0)    
    submission_drift= Column(Float, default=0.0)    
    alert_triggered = Column(Integer, default=0)    
    notes           = Column(String, nullable=True) 