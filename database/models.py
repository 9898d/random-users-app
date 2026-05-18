from sqlalchemy import Column, Integer, String
from database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    gender = Column(String, index=True)
    first_name = Column(String)
    last_name = Column(String)
    phone = Column(String)
    email = Column(String, unique=True, index=True)
    city = Column(String)  # место проживания
    external_id = Column(String, unique=True)  # ID из внешнего API