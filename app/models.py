from sqlalchemy import Column, Integer, String, Float
from .db import Base

class Vacancy(Base):
    __tablename__ = "vacancies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    city = Column(String)
    specialization = Column(String)
    salary_min = Column(Float)
    salary_max = Column(Float)
    currency = Column(String)
    url = Column(String)
