"""
models/notes.py
===============
PURPOSE: Stores teacher notes on individual students.
One row = one note written by the teacher about one student.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from models.student import Base


class TeacherNote(Base):
    """
    Represents the 'teacher_notes' table.
    A teacher can write multiple notes on the same student over time.
    """
    __tablename__ = "teacher_notes"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    note       = Column(String, nullable=False)       # The note text
    created_at = Column(DateTime, default=datetime.utcnow)  # When it was written