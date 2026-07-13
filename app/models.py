from datetime import date, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    writing_records = relationship("WritingRecord", back_populates="user")
    speaking_records = relationship("SpeakingRecord", back_populates="user")
    vocabulary_records = relationship("UserVocabulary", back_populates="user")
    listening_records = relationship("ListeningRecord", back_populates="user")

    reading_records = relationship("ReadingRecord", back_populates="user")


class WritingRecord(Base):
    __tablename__ = "writing_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_type = Column(String, nullable=False)
    task_response = Column(Float, nullable=True)
    coherence_cohesion = Column(Float, nullable=True)
    lexical_resource = Column(Float, nullable=True)
    grammatical_range = Column(Float, nullable=True)
    overall = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="writing_records")


class SpeakingRecord(Base):
    __tablename__ = "speaking_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    topic_card = Column(Text, nullable=False)
    user_response = Column(Text, nullable=False)
    score_fluency = Column(Float, nullable=True)
    score_lexical = Column(Float, nullable=True)
    score_grammar = Column(Float, nullable=True)
    score_pronunciation = Column(Float, nullable=True)
    overall = Column(Float, nullable=True)
    feedback_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="speaking_records")


class Vocabulary(Base):
    __tablename__ = "vocabulary"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, unique=True, nullable=False, index=True)
    pos = Column(String, nullable=False)
    definition_cn = Column(String, nullable=False)
    example_sentence = Column(String, nullable=False)
    synonyms = Column(Text, nullable=False, default="[]")
    topic = Column(String, nullable=False, index=True)
    difficulty = Column(Integer, nullable=False, default=1)

    user_records = relationship("UserVocabulary", back_populates="word")


class UserVocabulary(Base):
    __tablename__ = "user_vocabulary"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    word_id = Column(Integer, ForeignKey("vocabulary.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="new")
    next_review_at = Column(DateTime, nullable=True)
    review_count = Column(Integer, nullable=False, default=0)
    last_review_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="vocabulary_records")
    word = relationship("Vocabulary", back_populates="user_records")


class ReadingRecord(Base):
    __tablename__ = "reading_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    topic = Column(String, nullable=False)
    passage = Column(Text, nullable=False)
    questions_json = Column(Text, nullable=False)
    user_answers_json = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    total = Column(Integer, nullable=True)
    feedback_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reading_records")


class ListeningRecord(Base):
    __tablename__ = "listening_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scene_type = Column(String, nullable=False)
    voice = Column(String, nullable=True)
    script = Column(Text, nullable=False)
    questions_json = Column(Text, nullable=False)
    user_answers_json = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    total = Column(Integer, nullable=True)
    audio_path = Column(String, nullable=True)
    feedback_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="listening_records")
