from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
# Prefer explicit DATABASE_URL from environment (set by docker/.env). If missing,
# build from individual DB_* env vars for local/dev convenience.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    db_user = os.getenv("DB_USER", "tts_dataset_user")
    db_password = os.getenv("DB_PASSWORD", "changeme")
    db_host = os.getenv("DB_HOST", )
    db_port = os.getenv("DB_PORT", )
    db_name = os.getenv("DB_NAME", )
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class User(Base):
    __tablename__ = "users_meeting"
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    audios = relationship("Audio", back_populates="user")
    transcribes = relationship("TranscribeResult", back_populates="user")
    summaries = relationship("SummarizeResult", back_populates="user")

class Audio(Base):
    __tablename__ = "audios_meeting"
    id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    s3_url = Column(String, nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    user_id = Column(String, ForeignKey("users_meeting.id"))
    user = relationship("User", back_populates="audios")
    transcribes = relationship("TranscribeResult", back_populates="audio")

class TranscribeResult(Base):
    __tablename__ = "transcribes_meeting"
    id = Column(String, primary_key=True, index=True)
    audio_id = Column(String, ForeignKey("audios_meeting.id"))
    user_id = Column(String, ForeignKey("users_meeting.id"))
    segments = Column(Text)  # Keep for backward compatibility
    transcription = Column(Text)  # New field for direct transcription
    created_at = Column(DateTime, default=datetime.utcnow)
    audio = relationship("Audio", back_populates="transcribes")
    user = relationship("User", back_populates="transcribes")
    summaries = relationship("SummarizeResult", back_populates="transcribe")

class SummarizeResult(Base):
    __tablename__ = "summaries_meeting"
    id = Column(String, primary_key=True, index=True)
    transcribe_id = Column(String, ForeignKey("transcribes_meeting.id"))
    audio_id = Column(String, ForeignKey("audios_meeting.id"))
    user_id = Column(String, ForeignKey("users_meeting.id"))
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    transcribe = relationship("TranscribeResult", back_populates="summaries")
    user = relationship("User", back_populates="summaries")

# Create tables
Base.metadata.create_all(bind=engine)
