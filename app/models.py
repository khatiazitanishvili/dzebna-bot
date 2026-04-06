from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean,
    Text, Date, DateTime, Numeric, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    chat_id               = Column(BigInteger, nullable=False, unique=True)
    username              = Column(String(255))
    is_active             = Column(Boolean, default=True)
    notify_interval_hours = Column(Integer, default=6)
    created_at            = Column(DateTime, server_default=func.now())
    updated_at            = Column(DateTime, server_default=func.now(), onupdate=func.now())

    search_configs = relationship("SearchConfig", back_populates="user", cascade="all, delete")
    notifications  = relationship("Notification", back_populates="user", cascade="all, delete")


class SearchConfig(Base):
    __tablename__ = "search_configs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    search_term     = Column(String(255), nullable=False)
    location        = Column(String(255))
    is_remote       = Column(Boolean, default=False)
    results_wanted  = Column(Integer, default=20)
    site_names      = Column(String(255), default="linkedin,indeed,glassdoor")
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="search_configs")


class Job(Base):
    __tablename__ = "jobs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    job_id      = Column(String(512), nullable=False)
    site        = Column(String(50), nullable=False)
    title       = Column(String(512))
    company     = Column(String(255))
    location    = Column(String(255))
    is_remote   = Column(Boolean)
    job_type    = Column(String(100))
    salary_min  = Column(Numeric(10, 2))
    salary_max  = Column(Numeric(10, 2))
    currency    = Column(String(10))
    description = Column(Text)
    job_url     = Column(String(1024))
    date_posted = Column(Date)
    scraped_at  = Column(DateTime, server_default=func.now())

    notifications = relationship("Notification", back_populates="job", cascade="all, delete")

    __table_args__ = (
        UniqueConstraint("job_id", "site", name="uq_job"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id  = Column(Integer, ForeignKey("jobs.id",  ondelete="CASCADE"), nullable=False)
    sent_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="notifications")
    job  = relationship("Job",  back_populates="notifications")

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_notification"),
    )