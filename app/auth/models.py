# app/auth/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone = Column(String, unique=True, nullable=True, index=True)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role = Column(String, default="user")

    comments = relationship("EventComment", back_populates="author")  # Garde juste celle-ci

    # Relation vers les événements organisés par l'utilisateur
    organized_events = relationship("Event", back_populates="organizer")

    # Relation vers les événements auxquels l'utilisateur participe
    joined_events = relationship(
        "Event",
        secondary="event_participants",
        back_populates="participants"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', first_name='{self.first_name}')>"
    
    @property
    def full_name(self):
        """Propriété calculée pour le nom complet"""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self):
        """Nom d'affichage pour l'interface utilisateur"""
        return self.full_name or self.email or self.phone
