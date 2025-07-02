from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Table, TIMESTAMP
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from app.db.session import Base
from datetime import datetime

# Table d'association pour les participants aux événements
event_participants = Table(
    'event_participants',
    Base.metadata,
    Column('event_id', Integer, ForeignKey('events.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('joined_at', DateTime(timezone=True), default=datetime.utcnow),
    Column('status', String(20), default='confirmed')  # confirmed, pending, cancelled
)

class EventCategory(str, Enum):
    BIRTHDAY = "birthday"
    MUSIC = "music"
    SOCIAL = "social"
    CULTURE = "culture"
    WORKSHOP = "workshop"
    SPORT = "sport"
    FOOD = "food"
    BUSINESS = "business"

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    date = Column(TIMESTAMP(timezone=True), nullable=False) 
    location = Column(String(255), nullable=False)
    category = Column(String(20), nullable=False, index=True)
    price = Column(String(50), default="Gratuit")
    image = Column(String(500), nullable=True)
    
    is_public = Column(Boolean, default=True, index=True)
    allow_comments = Column(Boolean, default=True)
    allow_sharing = Column(Boolean, default=True)
    max_attendees = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    organizer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    organizer = relationship("User", back_populates="organized_events", lazy="joined")

    
    participants = relationship(
        "User",
        secondary=event_participants,
        back_populates="joined_events"
    )
    
    comments = relationship("EventComment", back_populates="event", cascade="all, delete-orphan")

    activities = relationship("EventActivity", back_populates="event", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Event(id={self.id}, title='{self.title}', date='{self.date}')>"
    
    @property
    def participant_count(self):
        return len(self.participants)
    
    @property
    def is_full(self):
        if self.max_attendees is None:
            return False
        return self.participant_count >= self.max_attendees

class EventComment(Base):
    __tablename__ = "event_comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    event = relationship("Event", back_populates="comments")

    author_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    author = relationship("User", back_populates="comments")

    parent_id = Column(Integer, ForeignKey('event_comments.id'), nullable=True)
    parent = relationship(
        "EventComment",
        remote_side=[id],
        back_populates="replies",
        foreign_keys=[parent_id]
    )
    replies = relationship(
        "EventComment",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
        lazy="selectin"
    )

    def __repr__(self):
        return f"<EventComment(id={self.id}, event_id={self.event_id}, author_id={self.author_id})>"

        
class EventActivity(Base):
    __tablename__ = "event_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    activity_type = Column(String(50), nullable=False)  # Ex: 'created', 'joined', 'commented', etc.
    data = Column(Text, nullable=True)  # Stockage JSON en texte (ex: {"event_title": "...", ...})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    event = relationship("Event", back_populates="activities")
    user = relationship("User")
    
    def __repr__(self):
        return f"<EventActivity(id={self.id}, type='{self.activity_type}', event_id={self.event_id})>"
