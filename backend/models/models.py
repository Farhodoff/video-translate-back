from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    projects = relationship("Project", back_populates="owner")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, index=True)
    status = Column(String, default="Ready") # Ready, Processing, Completed
    video_url = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    error_message = Column(String, nullable=True) # For handling failed downloads
    transcript = Column(JSON, nullable=True) # Store segments as JSON
    translated_transcript = Column(JSON, nullable=True) # Store translated segments
    dubbed_audio_url = Column(String, nullable=True) # URL to dubbed audio
    final_video_url = Column(String, nullable=True) # URL to final merged video
    quality = Column(String, default="standard") # tiny, standard (base), high (small)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="projects")
