import socketio
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime
from bson import ObjectId
from app.db.mongo import messages_collection, conversations_collection

# Création serveur Socket.IO async
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# App FastAPI
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adapter selon besoins
    allow_methods=["*"],
    allow_headers=["*"],
)

# ASGI application combinée
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Dictionnaire user_id -> sid
connected_users = {}

# Quand un client se connecte
@sio.event
async def connect(sid, environ, auth):
    user_id = auth.get("user_id") if auth else None
    if not user_id:
        await sio.disconnect(sid)
        return
    connected_users[str(user_id)] = sid
    print(f"User {user_id} connecté avec SID {sid}")

# Quand un client se déconnecte
@sio.event
async def disconnect(sid):
    user_id = None
    for uid, socket_id in connected_users.items():
        if socket_id == sid:
            user_id = uid
            break
    if user_id:
        del connected_users[user_id]
        print(f"User {user_id} déconnecté")

# Recevoir un message envoyé par un client
@sio.event
async def send_message(sid, data):
    """
    data = {
        "conversation_id": str,
        "text": str,
        "sender_id": int,
        "receiver_id": int
    }
    """
    message_data = {
        "conversation_id": data["conversation_id"],
        "text": data["text"],
        "sender_id": data["sender_id"],
        "receiver_id": data["receiver_id"],
        "timestamp": datetime.utcnow(),
        "is_read": False,
        "is_delivered": False
    }
    result = await messages_collection.insert_one(message_data)
    message_data["_id"] = result.inserted_id

    # Ajouter message à la conversation
    await conversations_collection.update_one(
        {"conversation_id": data["conversation_id"]},
        {
            "$push": {
                "messages": {
                    "message_id": str(result.inserted_id),
                    "text": data["text"],
                    "sender_id": data["sender_id"],
                    "receiver_id": data["receiver_id"],
                    "timestamp": message_data["timestamp"],
                    "is_read": False,
                    "is_delivered": False,
                }
            },
            "$set": {"updated_at": datetime.utcnow()}
        },
        upsert=True
    )

    # Accusé de réception au client expéditeur
    await sio.emit("message_delivered", {"message_id": str(result.inserted_id)}, room=sid)

    # Envoyer le message au destinataire si connecté
    receiver_sid = connected_users.get(str(data["receiver_id"]))
    if receiver_sid:
        await sio.emit("new_message", {
            "message_id": str(result.inserted_id),
            "conversation_id": data["conversation_id"],
            "text": data["text"],
            "sender_id": data["sender_id"],
            "receiver_id": data["receiver_id"],
            "timestamp": message_data["timestamp"].isoformat(),
            "is_read": False,
            "is_delivered": True,
        }, room=receiver_sid)

# Marquer message comme lu
@sio.event
async def mark_read(sid, data):
    """
    data = {
        "message_id": str,
        "user_id": int
    }
    """
    message_id = data.get("message_id")
    if not ObjectId.is_valid(message_id):
        return
    await messages_collection.update_one({"_id": ObjectId(message_id)}, {"$set": {"is_read": True}})

    # Informer l'expéditeur que le message a été lu
    message = await messages_collection.find_one({"_id": ObjectId(message_id)})
    if message:
        sender_sid = connected_users.get(str(message["sender_id"]))
        if sender_sid:
            await sio.emit("message_read", {"message_id": message_id}, room=sender_sid)
