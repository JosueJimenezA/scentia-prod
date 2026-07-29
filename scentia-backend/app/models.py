import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    collections = relationship("UserCollection", back_populates="user", cascade="all, delete-orphan")
    ai_profile = relationship("UserAIProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserAIProfile(Base):
    __tablename__ = "user_ai_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    dominant_notes = Column(JSONB, default=[])
    preferred_accords = Column(JSONB, default=[])
    preferred_seasons = Column(JSONB, default=[])
    embedding_vector = Column(JSONB, default=[])
    summary_text = Column(Text, nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="ai_profile")


class Fragrance(Base):
    __tablename__ = "fragrances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fragrantica_url = Column(Text, unique=True, nullable=False)
    bottle_image_url = Column(Text, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    designer = Column(String(150), nullable=True, index=True)
    global_rating = Column(Numeric(3, 2), nullable=True)
    global_rating_count = Column(Integer, default=0)
    
    top_notes = Column(ARRAY(Text), default=[])
    heart_notes = Column(ARRAY(Text), default=[])
    base_notes = Column(ARRAY(Text), default=[])
    perfumers = Column(ARRAY(Text), default=[])
    accords = Column(ARRAY(Text), default=[])

    vibe_reactions_dist = Column(JSONB, default={})
    seasons_dist = Column(JSONB, default={})
    time_of_day_dist = Column(JSONB, default={})
    longevity_dist = Column(JSONB, default={})
    sillage_dist = Column(JSONB, default={})
    price_value_dist = Column(JSONB, default={})
    gender_voted_dist = Column(JSONB, default={})
    
    reviews_corpus = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserCollection(Base):
    __tablename__ = "user_collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fragrance_id = Column(UUID(as_uuid=True), ForeignKey("fragrances.id", ondelete="CASCADE"), nullable=False)
    acquisition_status = Column(String(30), default="owned")
    user_rating = Column(Numeric(2, 1), nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="collections")
    fragrance = relationship("Fragrance")