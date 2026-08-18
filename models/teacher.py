"""
PURPOSE: Stores teacher accounts in the database.
         Each teacher has a username, hashed password, and a course
         they are responsible for. Teachers only see students in their course.
"""

import hashlib
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from models.student import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    username     = Column(String, unique=True, nullable=False)
    password_hash= Column(String, nullable=False)
    full_name    = Column(String, nullable=False)

    course       = Column(String, nullable=False, default="all")
    created_at   = Column(DateTime, default=datetime.utcnow)

    def check_password(self, password: str) -> bool:
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def __repr__(self):
        return f"<Teacher {self.username} course={self.course}>"