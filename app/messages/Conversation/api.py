from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from models import Message, Conversation
from schemas import MessageRead
from dependencies import get_db, get_current_user

router = APIRouter()

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageRead])
async def get_messages(conversation_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    # Vérifier que l'utilisateur est dans la conversation
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or current_user.id not in [p.id for p in conversation.participants]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.timestamp)
    )
    messages = result.scalars().all()
    return messages
from schemas import MessageCreate, MessageRead

@router.post("/conversations/{conversation_id}/messages", response_model=MessageRead)
async def send_message(conversation_id: int, message: MessageCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    # Vérifier que l'utilisateur est participant
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or current_user.id not in [p.id for p in conversation.participants]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    new_message = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        text=message.text,
        message_type=message.message_type,
        timestamp=datetime.utcnow(),
    )
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    return new_message
