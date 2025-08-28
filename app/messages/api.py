from fastapi import APIRouter, HTTPException, status
from typing import List
from app.messages.models import MessageCreate, MessageEmbedded, Conversation, ConversationCreate
from app.db.mongo import messages_collection, conversations_collection
from bson import ObjectId
from datetime import datetime

router = APIRouter()

# ✅ Validation d'ObjectId
def validate_object_id(id_str: str):
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Mongo ID")

# ✅ Créer une conversation
@router.post("/conversations/", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(conv: ConversationCreate):
    existing = await conversations_collection.find_one({"conversation_id": conv.conversation_id})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation already exists")
    doc = conv.dict()
    doc.update({
        "messages": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    await conversations_collection.insert_one(doc)
    return Conversation(**doc)

# ✅ Récupérer une conversation avec tous ses messages embarqués
@router.get("/conversations/{conversation_id}/messages", response_model=Conversation)
async def get_conversation(conversation_id: str):
    conv = await conversations_collection.find_one({"conversation_id": conversation_id})
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return Conversation(**conv)

# ✅ Ajouter un message à une conversation (stocké dans messages_collection ET dans conversation.messages)
@router.post("/messages/", response_model=MessageEmbedded, status_code=status.HTTP_201_CREATED)
async def add_message(msg: MessageCreate):
    conv = await conversations_collection.find_one({"conversation_id": msg.conversation_id})
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Crée le message
    msg_doc = msg.dict()
    msg_doc.update({
        "timestamp": datetime.utcnow(),
        "is_read": False,
        "is_delivered": False,
    })

    # Insère dans messages_collection (utile pour recherche indépendante)
    result = await messages_collection.insert_one(msg_doc)
    new_msg = await messages_collection.find_one({"_id": result.inserted_id})
    if not new_msg:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating message")

    # Format embedded message
    embedded = {
        "message_id": str(new_msg["_id"]),
        "text": new_msg["text"],
        "sender_id": new_msg["sender_id"],
        "receiver_id": new_msg["receiver_id"],
        "timestamp": new_msg["timestamp"],
        "is_read": new_msg["is_read"],
        "is_delivered": new_msg["is_delivered"],
    }

    # Ajoute à la conversation
    await conversations_collection.update_one(
        {"conversation_id": msg.conversation_id},
        {
            "$push": {"messages": embedded},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    return MessageEmbedded(**embedded)

# ✅ Récupérer les messages d'une conversation (directement depuis conversation)
@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageEmbedded])
async def get_messages(conversation_id: str):
    conv = await conversations_collection.find_one({"conversation_id": conversation_id})
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return [MessageEmbedded(**msg) for msg in conv.get("messages", [])]

# ✅ Marquer un message comme lu (dans messages_collection uniquement)
@router.patch("/messages/{message_id}/read", response_model=bool)
async def mark_read(message_id: str):
    validate_object_id(message_id)
    result = await messages_collection.update_one({"_id": ObjectId(message_id)}, {"$set": {"is_read": True}})
    return result.modified_count == 1

# ✅ Marquer un message comme livré
@router.patch("/messages/{message_id}/delivered", response_model=bool)
async def mark_delivered(message_id: str):
    validate_object_id(message_id)
    result = await messages_collection.update_one({"_id": ObjectId(message_id)}, {"$set": {"is_delivered": True}})
    return result.modified_count == 1

# ✅ Supprimer un message uniquement dans messages_collection (pas dans la conversation)
@router.delete("/messages/{message_id}", response_model=bool)
async def delete_message(message_id: str):
    validate_object_id(message_id)
    result = await messages_collection.delete_one({"_id": ObjectId(message_id)})
    return result.deleted_count == 1
