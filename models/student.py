from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Student(Base):
    
    __tablename__ = "students"         

    id        = Column(Integer, primary_key=True, autoincrement=True)  
    name      = Column(String, nullable=False)                          
    email     = Column(String, unique=True, nullable=False)           
    course    = Column(String, nullable=False)                          
    enrolled  = Column(DateTime, default=datetime.utcnow)             

    def __repr__(self):
    
        return f"<Student id={self.id} name={self.name} course={self.course}>"