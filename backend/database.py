from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os

# Create data directory if it doesn't exist
os.makedirs("/app/data", exist_ok=True)

SQLITE_URL = "sqlite:////app/data/parking.db"

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    plate = Column(String, index=True)
    entry_time = Column(DateTime, default=datetime.datetime.now)
    exit_time = Column(DateTime, nullable=True)
    is_paid = Column(Boolean, default=False)
    amount_due = Column(Float, default=0.0)
    image_path = Column(String, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
