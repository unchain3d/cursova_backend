from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone
import enum


class UserRole(str, enum.Enum):
    CLIENT = "client"
    TRAINER = "trainer"
    ADMIN = "admin"


class SubscriptionType(str, enum.Enum):
    SINGLE = "single"
    MONTH_CLASSIC = "month_classic"
    YEAR_GOLD = "year_gold"


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default=UserRole.CLIENT.value)
    
    subscription_type = Column(String, nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)
    subscription_active = Column(Boolean, default=False)
    
    bookings = relationship("Sessions", back_populates="client")
    visit_history = relationship("VisitHistory", back_populates="user")


class Trainers(Base):
    __tablename__ = "trainers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    specialization = Column(String)
    photo_url = Column(String, nullable=True)
    rating = Column(Float, default=0.0)
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    experience_years = Column(Integer, default=0)
    price_per_session = Column(Float, default=0.0)
    
    sessions = relationship("Sessions", back_populates="trainer")


class Subscriptions(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    subscription_type = Column(String)
    price = Column(Float)
    duration_days = Column(Integer)
    visits_limit = Column(Integer, nullable=True)


class SubscriptionPurchases(Base):
    __tablename__ = "subscription_purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"))
    price = Column(Float)
    purchased_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("Users")
    subscription = relationship("Subscriptions")

