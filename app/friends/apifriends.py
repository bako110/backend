from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.db.mongo import profiles_collection, friendships_collection

router = APIRouter(prefix="/friends", tags=["friends"])

# ─────────────────────────────────────────────
# 1. Envoyer une demande d'amitié
# ─────────────────────────────────────────────
@router.post("/send-request")
async def send_friend_request(sender_id: str, receiver_id: str):
    if sender_id == receiver_id:
        raise HTTPException(status_code=400, detail="Impossible de s’ajouter soi-même")

    # Vérifier que le destinataire existe
    receiver_profile = await profiles_collection.find_one({"user_id": int(receiver_id)})
    if not receiver_profile:
        raise HTTPException(status_code=404, detail="Utilisateur destinataire introuvable")

    # Vérifier qu’une demande ou une relation n’existe pas déjà (dans un sens ou dans l’autre)
    existing = await friendships_collection.find_one({
        "$or": [
            {"sender_id": sender_id, "receiver_id": receiver_id},
            {"sender_id": receiver_id, "receiver_id": sender_id}
        ]
    })
    if existing:
        raise HTTPException(status_code=400, detail="Relation déjà existante")

    # Insérer la demande avec statut 'pending'
    await friendships_collection.insert_one({
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": None
    })

    return {"msg": "Demande d’amitié envoyée"}

# ─────────────────────────────────────────────
# 2. Accepter une demande d'amitié
# ─────────────────────────────────────────────
@router.post("/accept-request")
async def accept_friend_request(sender_id: str, receiver_id: str):
    # Met à jour le statut de la demande à "accepted"
    result = await friendships_collection.find_one_and_update(
        {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "status": "pending"
        },
        {
            "$set": {
                "status": "accepted",
                "updated_at": datetime.utcnow()
            }
        }
    )

    if not result:
        raise HTTPException(status_code=404, detail="Demande non trouvée")

    # Ajoute chacun dans la liste d'amis de l'autre dans profiles_collection
    await profiles_collection.update_one(
        {"user_id": int(sender_id)},
        {"$addToSet": {"friend_ids": receiver_id}}
    )
    await profiles_collection.update_one(
        {"user_id": int(receiver_id)},
        {"$addToSet": {"friend_ids": sender_id}}
    )

    return {"msg": "Demande acceptée"}

# ─────────────────────────────────────────────
# 3. Refuser une demande d'amitié
# ─────────────────────────────────────────────
@router.post("/reject-request")
async def reject_friend_request(sender_id: str, receiver_id: str):
    # Met à jour le statut de la demande à "rejected"
    result = await friendships_collection.find_one_and_update(
        {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "status": "pending"
        },
        {
            "$set": {
                "status": "rejected",
                "updated_at": datetime.utcnow()
            }
        }
    )

    if not result:
        raise HTTPException(status_code=404, detail="Demande non trouvée")

    return {"msg": "Demande refusée"}

# ─────────────────────────────────────────────
# 4. Voir la liste des amis d’un utilisateur
# ─────────────────────────────────────────────
@router.get("/my-friends/{user_id}")
async def get_my_friends(user_id: str):
    profile = await profiles_collection.find_one({"user_id": int(user_id)})

    if not profile:
        raise HTTPException(status_code=404, detail="Profil non trouvé")

    # Renvoie la liste d'amis (friend_ids) stockée dans le profil
    return {
        "friends": profile.get("friend_ids", [])
    }

# ─────────────────────────────────────────────
# 5. Bloquer un utilisateur
# ─────────────────────────────────────────────
@router.post("/block")
async def block_user(blocker_id: str, blocked_id: str):
    if blocker_id == blocked_id:
        raise HTTPException(status_code=400, detail="Action invalide")

    # Ajoute l'utilisateur bloqué dans la liste blocked_users du bloqueur
    await profiles_collection.update_one(
        {"user_id": int(blocker_id)},
        {"$addToSet": {"blocked_users": blocked_id}}
    )

    return {"msg": "Utilisateur bloqué"}

# ─────────────────────────────────────────────
# 6. Voir toutes les relations d’amitié (acceptées)
# ─────────────────────────────────────────────
@router.get("/all-friendships")
async def get_all_friendships():
    cursor = friendships_collection.find({"status": "accepted"})
    friendships = []
    async for doc in cursor:
        friendships.append({
            "sender_id": doc["sender_id"],
            "receiver_id": doc["receiver_id"],
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        })
    return {"friendships": friendships}

# ─────────────────────────────────────────────
# 7. Voir les abonnés (followers) d’un utilisateur
# ─────────────────────────────────────────────
@router.get("/my-followers/{user_id}")
async def get_my_followers(user_id: str):
    cursor = friendships_collection.find({
        "receiver_id": user_id,
        "type": "follow",
        "status": "active"
    })
    result = []
    async for doc in cursor:
        result.append(doc["sender_id"])
    return {"followers": result}

# ─────────────────────────────────────────────
# 8. Voir les abonnements (followings) d’un utilisateur
# ─────────────────────────────────────────────
@router.get("/my-followings/{user_id}")
async def get_my_followings(user_id: str):
    cursor = friendships_collection.find({
        "sender_id": user_id,
        "type": "follow",
        "status": "active"
    })
    result = []
    async for doc in cursor:
        result.append(doc["receiver_id"])
    return {"following": result}
