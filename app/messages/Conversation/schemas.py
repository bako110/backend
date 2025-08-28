from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MessageBase(BaseModel):
    text: Optional[str] = None
    message_type: str = 'text'

class MessageCreate(MessageBase):
    pass

class MessageRead(MessageBase):
    id: int
    conversation_id: int
    sender_id: int
    timestamp: datetime
    is_read: bool

    class Config:
        orm_mode = True
