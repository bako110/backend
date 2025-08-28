from fastapi import APIRouter, HTTPException, Query
from typing import List
from bson import ObjectId
from app.users.models import UserProfile
from app.db.mongo import client
from pydantic import ValidationError
import json
import re
import traceback

router = APIRouter()
db = client["Annivdb"]
profiles_collection = db["profiles"]

# ────────────────────────────────
# Nettoyage d'un document MongoDB
# ────────────────────────────────
def clean_doc(doc: dict) -> dict:
    """
    Nettoie un document MongoDB pour compatibilité avec Pydantic.
    """
    if "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])

    if "user_id" in doc and doc["user_id"] is None:
        doc.pop("user_id", None)

    for key, value in list(doc.items()):
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif value is None and key.endswith("_id"):
            doc.pop(key, None)
        elif isinstance(value, list) and key in ["follow", "friend_ids", "blocked_users"]:
            doc[key] = [str(v) for v in value]

    return doc
# ────────────────────────────────
# Obtenir la liste des amis d’un utilisateur
# ────────────────────────────────
@router.get("/{user_id}/friends", response_model=List[UserProfile])
async def get_user_friends(user_id: int):
    print(f"\n📥 Requête reçue pour user_id={user_id}")

    user = await profiles_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    follow_ids = user.get("follow", [])
    print(f"🧾 Liste des IDs suivis : {follow_ids}")

    if not follow_ids:
        return []

    cursor = profiles_collection.find({"user_id": {"$in": follow_ids}})
    friends = []
    count = 0

    async for doc in cursor:
        count += 1
        cleaned = clean_doc(doc)
        try:
            user_obj = UserProfile(**cleaned)
            serialized = user_obj.model_dump()
            print(f"\n👤 Ami {count} trouvé :\n{json.dumps(serialized, indent=2, ensure_ascii=False, default=str)}")
            friends.append(user_obj)
        except ValidationError as e:
            print(f"❌ Erreur de validation Pydantic pour user_id={doc.get('user_id')}: {e}")
            continue

    print(f"\n📤 Total d'amis renvoyés : {len(friends)}\n")
    return friends
# ────────────────────────────────
# Recherche stricte (commence par...)
# ────────────────────────────────
@router.get("/search", response_model=List[UserProfile])
async def search_users(q: str = Query(..., min_length=1, description="Terme de recherche")):
    try:
        q_clean = q.strip()
        if not q_clean:
            raise HTTPException(status_code=400, detail="Terme de recherche vide")

        try:
            escaped_q = re.escape(q_clean)
            regex_pattern = {"$regex": f"^{escaped_q}", "$options": "i"}
        except Exception as e:
            print(f"❌ Erreur dans regex : {e}")
            raise HTTPException(status_code=400, detail="Mot-clé invalide")

        # Construction de la requête Mongo
        filter_query = {
            "$or": [
                {"first_name": regex_pattern},
                {"last_name": regex_pattern},
                {"email": regex_pattern},
                {"username": regex_pattern}
            ]
        }

        if q_clean:
            filter_query["$or"].append({"phone": regex_pattern})

        if q_clean.isdigit():
            try:
                user_id_int = int(q_clean)
                filter_query["$or"].append({"user_id": user_id_int})
            except ValueError:
                pass

        print(f"🔍 Recherche avec pattern: {escaped_q}")
        print(f"📝 Requête MongoDB: {filter_query}")

        # Projection optionnelle pour améliorer les performances
        projection = {
            "_id": 1,
            "user_id": 1,
            "email": 1,
            "phone": 1,
            "first_name": 1,
            "last_name": 1,
            "username": 1,
            "avatar_url": 1,
            "bio": 1,
            "location": 1,
            "online_status": 1,
            "level": 1,
            "points": 1,
            "friends_count": 1,
            "registered_at": 1
        }

        cursor = profiles_collection.find(filter_query, projection).limit(50)

        results = []
        documents_count = 0

        async for doc in cursor:
            documents_count += 1
            try:
                cleaned = clean_doc(doc)
                print(f"✅ {cleaned.get('first_name')} {cleaned.get('last_name')} (ID: {cleaned.get('user_id')})")
                user = UserProfile(**cleaned)
                results.append(user)
            except ValidationError as ve:
                print(f"❌ Erreur de validation : {ve}")
                continue
            except Exception as e:
                print(f"❌ Erreur inattendue : {e}")
                continue

        print(f"🎯 Résultats : {len(results)} utilisateurs trouvés sur {documents_count} documents")
        return results

    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Erreur dans search_users : {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")

# ────────────────────────────────
# Recherche flexible (contient...)
# ────────────────────────────────
@router.get("/search/flexible", response_model=List[UserProfile])
async def search_users_flexible(q: str = Query(..., min_length=1, description="Terme de recherche")):
    try:
        q_clean = q.strip()
        if not q_clean:
            raise HTTPException(status_code=400, detail="Terme de recherche vide")

        escaped_q = re.escape(q_clean)
        regex_pattern = {"$regex": escaped_q, "$options": "i"}

        filter_query = {
            "$or": [
                {"first_name": regex_pattern},
                {"last_name": regex_pattern},
                {"email": regex_pattern},
                {"username": regex_pattern},
                {"phone": regex_pattern},
            ]
        }

        if q_clean.isdigit():
            filter_query["$or"].append({"user_id": int(q_clean)})

        print(f"🔍 Recherche flexible avec pattern: {escaped_q}")
        print(f"📝 Requête MongoDB: {filter_query}")

        cursor = profiles_collection.find(filter_query).limit(50)
        results = []
        documents_count = 0

        async for doc in cursor:
            documents_count += 1
            try:
                cleaned_doc = clean_doc(doc)
                print(f"✅ Document {documents_count}: {cleaned_doc.get('first_name')} {cleaned_doc.get('last_name')} (ID: {cleaned_doc.get('user_id')})")
                user = UserProfile(**cleaned_doc)
                results.append(user)
            except ValidationError as ve:
                print(f"❌ Erreur de validation pour document {documents_count}: {ve}")
                continue
            except Exception as e:
                print(f"❌ Erreur inattendue pour document {documents_count}: {e}")
                continue

        print(f"🎯 Résultats: {len(results)} utilisateurs trouvés sur {documents_count} documents traités")
        return results

    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Erreur dans search_users_flexible: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")
