from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from your_project.database import Base

class Conversation(Base):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    participants = relationship('User', secondary='conversation_participants', back_populates='conversations')
    messages = relationship('Message', back_populates='conversation', order_by='Message.timestamp')

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    message_type = Column(String, default='text')  # text, voice, location, etc.

    conversation = relationship('Conversation', back_populates='messages')
    sender = relationship('User')
