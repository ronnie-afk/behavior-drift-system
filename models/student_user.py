"""
models/student_user.py
=======================
PURPOSE: Stores login credentials for students so they can access
         the student portal and view their own data.

Each Student already exists in the students table.
This table stores their login details separately — cleaner design.
"""

import hashlib
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from models.student import Base


class StudentUser(Base):
    __tablename__ = "student_users"

    id            = Column(Integer, primary_key=True, autoincrement=True)

    # Links to the students table
    student_id    = Column(Integer, ForeignKey("students.id"),
                           unique=True, nullable=False)

    # Login credentials
    username      = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    def check_password(self, password: str) -> bool:
        return self.password_hash == hashlib.sha256(
            password.encode()
        ).hexdigest()

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()