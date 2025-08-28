from app.db.mongo import profiles_collection
from app.users.models import UserProfile
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
from bson import ObjectId
import urllib.parse

logger = logging.getLogger(__name__)


async def create_user_profile(profile: UserProfile) -> UserProfile:
    """Créer un nouveau profil utilisateur"""
    try:
        profile_dict = profile.model_dump()
        profile_dict["created_at"] = datetime.utcnow()
        profile_dict["updated_at"] = datetime.utcnow()
        
        # Initialiser les champs d'images par défaut
        if not profile_dict.get("avatar_url"):
            name = f"{profile_dict.get('first_name', '')} {profile_dict.get('last_name', '')}".strip()
            if not name:
                name = profile_dict.get("username", "User")
            profile_dict["avatar_url"] = f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=667eea&color=fff&size=150"
        
        if not profile_dict.get("cover_photo_url"):
            profile_dict["cover_photo_url"] = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=200&fit=crop"
        
        result = await profiles_collection.insert_one(profile_dict)
        
        if result.inserted_id:
            created_profile = await profiles_collection.find_one({"_id": result.inserted_id})
            if created_profile:
                created_profile["_id"] = str(created_profile["_id"])

                # ✅ Correction du type des valeurs dans follow
                if "follow" in created_profile and isinstance(created_profile["follow"], list):
                    created_profile["follow"] = [str(f) for f in created_profile["follow"] if f is not None]

                return UserProfile(**created_profile)
        
        raise Exception("Échec de la création du profil")
        
    except Exception as e:
        logger.error(f"Erreur création profil: {e}")
        raise


async def get_profile_by_identifier(identifier: str) -> Optional[UserProfile]:
    """Récupérer un profil par email, téléphone ou MongoDB ID"""
    try:
        profile_data = None
        
        # 1. Essayer par MongoDB ID
        try:
            if len(identifier) == 24:  # Longueur typique d'un ObjectId
                object_id = ObjectId(identifier)
                profile_data = await profiles_collection.find_one({"_id": object_id})
        except:
            pass  # Pas un ObjectId valide, continuer
        
        # 2. Essayer par email
        if not profile_data:
            profile_data = await profiles_collection.find_one({"email": identifier})
        
        # 3. Essayer par téléphone (décodé si encodé URL)
        if not profile_data:
            decoded_phone = urllib.parse.unquote(identifier)
            profile_data = await profiles_collection.find_one({"phone": decoded_phone})
        
        if profile_data:
            profile_data["_id"] = str(profile_data["_id"])

            # ✅ Correction du type des valeurs dans follow
            if "follow" in profile_data and isinstance(profile_data["follow"], list):
                profile_data["follow"] = [str(f) for f in profile_data["follow"] if f is not None]

            return UserProfile(**profile_data)
        
        return None
    except Exception as e:
        logger.error(f"Erreur récupération profil pour {identifier}: {e}")
        raise


async def update_profile_by_identifier(identifier: str, update_data: Dict[str, Any]) -> Optional[UserProfile]:
    """Mettre à jour un profil par email, téléphone ou MongoDB ID"""
    try:
        # Trouver le profil existant
        profile = await get_profile_by_identifier(identifier)
        if not profile:
            return None

        update_data["updated_at"] = datetime.utcnow()
        
        # Utiliser l'email comme clé unique pour la mise à jour
        result = await profiles_collection.update_one(
            {"email": profile.email},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return None
        
        # Récupérer le profil mis à jour
        updated_profile = await profiles_collection.find_one({"email": profile.email})
        
        if updated_profile:
            updated_profile["_id"] = str(updated_profile["_id"])

            # ✅ Correction du type des valeurs dans follow
            if "follow" in updated_profile and isinstance(updated_profile["follow"], list):
                updated_profile["follow"] = [str(f) for f in updated_profile["follow"] if f is not None]

            return UserProfile(**updated_profile)
        
        return None
    except Exception as e:
        logger.error(f"Erreur mise à jour profil pour {identifier}: {e}")
        raise


async def delete_profile_by_identifier(identifier: str) -> bool:
    """Supprimer un profil par email, téléphone ou MongoDB ID"""
    try:
        # Trouver le profil existant
        profile = await get_profile_by_identifier(identifier)
        if not profile:
            return False

        # Supprimer par email (clé unique)
        result = await profiles_collection.delete_one({"email": profile.email})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Erreur suppression profil pour {identifier}: {e}")
        raise


async def get_user_profiles(skip: int = 0, limit: int = 100) -> List[UserProfile]:
    """
    Récupère une liste paginée de profils utilisateur.
    """
    try:
        cursor = profiles_collection.find().skip(skip).limit(limit)
        profiles = []

        async for profile_data in cursor:
            profile_data["_id"] = str(profile_data["_id"])

            # ✅ Correction du type des valeurs dans follow
            if "follow" in profile_data and isinstance(profile_data["follow"], list):
                profile_data["follow"] = [str(f) for f in profile_data["follow"] if f is not None]

            profiles.append(UserProfile(**profile_data))

        return profiles
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des profils : {e}", exc_info=True)
        raise


def format_profile_for_frontend(user: dict, current_user_id: str = None) -> dict:
    """
    Formate un document de profil utilisateur brut en une structure lisible côté frontend.
    """
    user["_id"] = str(user.get("_id") or "")

    name = user.get("name")
    if not name or name.strip() == "":
        first = user.get("first_name") or ""
        last = user.get("last_name") or ""
        name = f"{first} {last}".strip()

    contact = user.get("contact") or {}
    contact_email = contact.get("email") or user.get("email") or ""
    contact_phone = contact.get("phone") or user.get("phone") or ""
    contact_website = contact.get("website") or user.get("website") or ""

    is_following = user.get("is_following", False)

    return {
        "id": user["_id"],
        "name": name or "Nom inconnu",
        "title": user.get("title") or "",
        "company": user.get("company") or "",
        "avatar_url": user.get("avatar_url") or "",
        "coverPhoto": user.get("coverPhoto") or user.get("cover_photo_url") or "",
        "about": user.get("about") or user.get("bio") or "",
        "contact": {
            "email": contact_email,
            "phone": contact_phone,
            "website": contact_website,
        },
        "education": user.get("education") or "",
        "experience": user.get("experience") or "",
        "skills": user.get("skills") or [],
        "connections": user.get("friends_count") or user.get("connections") or 0,
        "followers": user.get("followers") or 0,
        "views": user.get("views") or 0,
        "is_following": is_following,
    }


def parse_education(education_text: str):
    if not education_text or not isinstance(education_text, str):
        return []
    parts = education_text.split(" - ")
    if len(parts) == 2:
        degree, rest = parts
        school, _, year = rest.partition("(")
        return [{
            "degree": degree.strip(),
            "school": school.strip(),
            "year": year.strip(") ") if year else ""
        }]
    else:
        return [{
            "degree": education_text.strip(),
            "school": "",
            "year": ""
        }]


def parse_experience(experience_text: str):
    if not experience_text or not isinstance(experience_text, str):
        return []
    parts = experience_text.split(" - ")
    if len(parts) == 2:
        role, rest = parts
        company, _, duration = rest.partition("(")
        return [{
            "role": role.strip(),
            "company": company.strip(),
            "duration": duration.strip(") ") if duration else "",
            "description": f"Expérience dans le poste de {role.strip()} chez {company.strip()}"
        }]
    else:
        return [{
            "role": experience_text.strip(),
            "company": "",
            "duration": "",
            "description": experience_text.strip()
        }]
