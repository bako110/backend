from typing import List
from pydantic import BaseModel, Field
from datetime import datetime

# ---------- Message pour création (sans id, timestamp, etc.) ----------
class MessageCreate(BaseModel):
    text: str
    sender_id: int
    receiver_id: int
    conversation_id: str

    model_config = {
        "extra": "forbid"
    }

# ---------- Message intégré dans une conversation ----------
class MessageEmbedded(BaseModel):
    message_id: str = Field(..., alias="id")
    text: str
    sender_id: int
    receiver_id: int
    timestamp: datetime
    is_read: bool = False
    is_delivered: bool = False

    model_config = {
        "populate_by_name": True  # équivaut à allow_population_by_field_name en v1
    }

# ---------- Participants ----------
class Participants(BaseModel):
    sender: int
    receiver: int

# ---------- Conversation Models ----------
class ConversationBase(BaseModel):
    conversation_id: str
    participants: Participants

class ConversationCreate(ConversationBase):
    pass

class Conversation(ConversationBase):
    messages: List[MessageEmbedded] = []
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True  # équivaut à orm_mode=True en v1
    }
