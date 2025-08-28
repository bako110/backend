from typing import List, Optional, Union
from app.messages.models import MessageEmbedded
from app.db.mongo import messages_collection, conversations_collection
from datetime import datetime
from bson import ObjectId
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ✅ Ajouter un message et l'inclure dans la conversation
async def add_message(message_data: dict) -> MessageEmbedded:
    try:
        message_data["timestamp"] = datetime.utcnow()
        message_data["is_read"] = False
        message_data["is_delivered"] = False

        # Insérer dans messages_collection (optionnel mais utile pour recherche indépendante)
        result = await messages_collection.insert_one(message_data)
        new_message = await messages_collection.find_one({"_id": result.inserted_id})

        if not new_message:
            raise HTTPException(status_code=500, detail="Échec de création du message")

        # Ajouter dans la conversation (stockage embarqué)
        embedded_message = {
            "message_id": str(new_message["_id"]),
            "text": new_message["text"],
            "sender_id": new_message["sender_id"],
            "receiver_id": new_message["receiver_id"],
            "timestamp": new_message["timestamp"],
            "is_read": new_message["is_read"],
            "is_delivered": new_message["is_delivered"],
        }

        update_result = await conversations_collection.update_one(
            {"conversation_id": message_data["conversation_id"]},
            {
                "$push": {"messages": embedded_message},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        if update_result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Conversation non trouvée")

        return MessageEmbedded(**embedded_message)

    except Exception as e:
        logger.exception("Erreur lors de l'ajout du message")
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Récupérer un message depuis messages_collection
async def get_message(id: str) -> Union[MessageEmbedded, None]:
    try:
        if not ObjectId.is_valid(id):
            return None
        message = await messages_collection.find_one({"_id": ObjectId(id)})
        if not message:
            return None

        return MessageEmbedded(
            id=str(message["_id"]),
            text=message["text"],
            sender_id=message["sender_id"],
            receiver_id=message["receiver_id"],
            timestamp=message["timestamp"],
            is_read=message["is_read"],
            is_delivered=message["is_delivered"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Créer ou retourner une conversation
async def get_or_create_conversation(
    conversation_id: str,
    user_id: int,
    other_participant_id: Optional[int] = None
) -> dict:
    try:
        conversation = await conversations_collection.find_one({"conversation_id": conversation_id})
        if not conversation:
            conversation = {
                "conversation_id": conversation_id,
                "participants": {
                    "sender": user_id,
                    "receiver": other_participant_id
                },
                "messages": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await conversations_collection.insert_one(conversation)
        return conversation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Marquer un message comme lu (dans messages_collection)
async def mark_message_read(id: str) -> bool:
    try:
        if not ObjectId.is_valid(id):
            return False
        result = await messages_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"is_read": True}}
        )
        return result.modified_count == 1
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Marquer un message comme livré
async def mark_message_delivered(id: str) -> bool:
    try:
        if not ObjectId.is_valid(id):
            return False
        result = await messages_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"is_delivered": True}}
        )
        return result.modified_count == 1
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Supprimer un message uniquement de messages_collection
async def delete_message(id: str) -> bool:
    try:
        if not ObjectId.is_valid(id):
            return False
        result = await messages_collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count == 1
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Récupérer les messages d'une conversation (déjà stockés dedans)
async def get_conversation_messages(conversation_id: str) -> List[MessageEmbedded]:
    try:
        conversation = await conversations_collection.find_one({"conversation_id": conversation_id})
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation non trouvée")
        return [MessageEmbedded(**msg) for msg in conversation.get("messages", [])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
