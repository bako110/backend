from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Security, status, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pathlib import Path
import aiofiles
import logging
import urllib.parse
import uuid  # ← AJOUT DE L'IMPORT MANQUANT
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from app.users import services
from app.users.models import UserProfile, UserProfileUpdate
from app.auth.dependencies import get_current_user  
from app.users.services import format_profile_for_frontend
from fastapi.security import HTTPBearer
from fastapi import Security, Header
from app.db.mongo import profiles_collection


security = HTTPBearer()

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# Configuration
BASE_UPLOAD_DIR = Path("static/upload")
PROFILE_IMAGE_DIR = BASE_UPLOAD_DIR / "profileImage"
COVER_IMAGE_DIR = BASE_UPLOAD_DIR / "coverImage"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Créer les répertoires s'ils n'existent pas
BASE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
COVER_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def validate_image_file(file: UploadFile) -> None:
    """Valide le fichier image uploadé"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant")
    
    ext = file.filename.split('.')[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Extension non autorisée. Extensions autorisées: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Le fichier doit être une image")


async def cleanup_old_image(identifier: str, image_type: str) -> None:
    """Supprime l'ancienne image si elle existe"""
    try:
        profile = await services.get_profile_by_identifier(identifier)
        if not profile:
            return
        
        old_url = None
        if image_type == "avatar" and hasattr(profile, 'avatar_url'):
            old_url = profile.avatar_url
        elif image_type == "cover" and hasattr(profile, 'coverPhoto'):
            old_url = profile.coverPhoto
        
        if old_url and _is_local_upload(old_url):
            filepath = _get_file_path_from_url(old_url)
            if filepath and filepath.exists():
                filepath.unlink()
                logger.info(f"Ancienne image supprimée: {filepath}")
    except Exception as e:
        logger.warning(f"Erreur lors de la suppression de l'ancienne image: {e}")


def _is_local_upload(url: str) -> bool:
    """Vérifie si l'URL correspond à un fichier uploadé localement"""
    if not url:
        return False
    return (
        url.startswith('/static/upload/') and 
        not url.startswith('https://ui-avatars.com') and 
        not url.startswith('https://images.unsplash.com')
    )


def _get_file_path_from_url(url: str) -> Path | None:
    """Extrait le chemin du fichier à partir de l'URL"""
    if '/static/upload/' in url:
        filename = url.split('/static/upload/')[-1]
        return BASE_UPLOAD_DIR / filename
    return None


def _create_safe_filename(identifier: str, prefix: str, extension: str) -> str:
    """Crée un nom de fichier sécurisé"""
    safe_id = identifier.replace('@', '_').replace('.', '_').replace('+', '_')
    return f"{prefix}_{safe_id}_{uuid.uuid4().hex[:8]}.{extension}"


# 📋 GET /users/ - Lister les profils
@router.get("/userlist")
async def list_profiles(skip: int = 0, limit: int = 100):
    """Lister les profils utilisateurs"""
    try:
        profiles = await services.get_user_profiles(skip=skip, limit=limit)
        return {"profiles": profiles, "skip": skip, "limit": limit}
    except Exception as e:
        logger.error(f"Erreur liste profils: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


# 🔍 GET /users/profile/{identifier} - Récupérer un profil
@router.get("/profile/{identifier}", response_model=UserProfile)
async def get_profile(identifier: str):
    """Récupérer un profil utilisateur par email, téléphone ou ID"""
    try:
        decoded_identifier = urllib.parse.unquote(identifier)
        profile = await services.get_profile_by_identifier(decoded_identifier)
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profil non trouvé")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération profil: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


@router.put("/profile/{identifier}", response_model=UserProfile)
async def update_profile(identifier: str, updates: UserProfileUpdate, request: Request):
    logger.info(f"Route update_profile appelée avec identifier={identifier}")
    body = await request.json()
    logger.info(f"Données reçues côté backend: {body}")

    decoded_identifier = urllib.parse.unquote(identifier)
    update_data = updates.model_dump(exclude_unset=True, exclude_none=True)
    logger.info(f"Données validées et nettoyées: {update_data}")

    updated = await services.update_profile_by_identifier(decoded_identifier, update_data)
    
    if not updated:
        raise HTTPException(status_code=404, detail="Profil non trouvé")
    return updated


# 🗑️ DELETE /users/profile/{identifier} - Supprimer un profil
@router.delete("/profile/{identifier}")
async def delete_profile(identifier: str):
    """Supprimer un profil utilisateur par email, téléphone ou ID"""
    try:
        decoded_identifier = urllib.parse.unquote(identifier)
        
        # Nettoyer les images avant suppression
        await cleanup_old_image(decoded_identifier, "avatar")
        await cleanup_old_image(decoded_identifier, "cover")
        
        deleted = await services.delete_profile_by_identifier(decoded_identifier)
        if not deleted:
            raise HTTPException(status_code=404, detail="Profil non trouvé")
        
        return JSONResponse(status_code=204, content=None)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur suppression profil: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


# 📸 POST /users/avatar/change/{identifier} - Changer l'avatar
@router.post("/avatar/change/{identifier}")
async def change_avatar(identifier: str, file: UploadFile = File(...)):
    """Changer la photo de profil d'un utilisateur"""
    try:
        validate_image_file(file)
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux")

        decoded_identifier = urllib.parse.unquote(identifier)
        await cleanup_old_image(decoded_identifier, "avatar")

        ext = file.filename.split('.')[-1].lower()
        filename = _create_safe_filename(decoded_identifier, "avatar", ext)
        filepath = PROFILE_IMAGE_DIR / filename

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(content)

        url = f"/static/upload/profileImage/{filename}"
        profile = await services.update_profile_by_identifier(
            decoded_identifier, 
            {"avatar_url": url}
        )

        if not profile:
            filepath.unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Profil non trouvé")

        return {
            "message": "Avatar mis à jour avec succès ✅", 
            "avatar_url": url, 
            "profile": profile
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur changement avatar: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


# 🖼️ POST /users/cover/change/{identifier} - Changer la photo de couverture
@router.post("/cover/change/{identifier}")
async def change_cover(identifier: str, file: UploadFile = File(...)):
    """Changer la photo de couverture d'un utilisateur"""
    try:
        validate_image_file(file)
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux")

        decoded_identifier = urllib.parse.unquote(identifier)
        await cleanup_old_image(decoded_identifier, "cover")

        ext = file.filename.split('.')[-1].lower()
        filename = _create_safe_filename(decoded_identifier, "cover", ext)
        filepath = COVER_IMAGE_DIR / filename

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(content)

        url = f"/static/upload/coverImage/{filename}"
        profile = await services.update_profile_by_identifier(
            decoded_identifier, 
            {"coverPhoto": url}
        )

        if not profile:
            filepath.unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Profil non trouvé")

        return {
            "message": "Photo de couverture mise à jour ✅", 
            "coverPhoto": url, 
            "profile": profile
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur changement couverture: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


# ➤ Met à jour le statut en ligne de l'utilisateur
@router.post("/online")
async def ping(user: UserProfile = Depends(get_current_user)):
    """
    Marque l'utilisateur comme en ligne et met à jour le champ `last_seen`
    """
    result = await profiles_collection.update_one(
        {"user_id": user.user_id},
        {
            "$set": {
                "online_status": True,
                "last_seen": datetime.utcnow()
            }
        }
    )

    if result.modified_count == 1:
        return {"status": "online", "user_id": user.user_id}
    else:
        return {"status": "not_updated", "user_id": user.user_id}


# ➤ Met à jour les utilisateurs inactifs (déconnecte après 3 minutes)
async def mark_users_offline_if_inactive():
    timeout_limit = datetime.utcnow() - timedelta(minutes=3)
    await profiles_collection.update_many(
        {"last_seen": {"$lt": timeout_limit}},
        {"$set": {"online_status": False}}
    )


@router.get("/{user_id}")
async def get_user_profile(user_id: str, current_user=Depends(get_current_user)):
    try:
        if not current_user or not hasattr(current_user, "id"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentification requise pour accéder au profil"
            )

        # Identifier le profil cible
        if user_id.isdigit():
            query = {"user_id": int(user_id)}
        elif ObjectId.is_valid(user_id):
            query = {"_id": ObjectId(user_id)}
        else:
            raise HTTPException(status_code=400, detail="ID invalide")

        user = await profiles_collection.find_one(query)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        # Convertir l'ID Mongo en string pour le frontend
        user["_id"] = str(user["_id"])

        # Incrément des vues
        await profiles_collection.update_one(query, {"$inc": {"views": 1}})

        # Vérifie si l'utilisateur courant suit ce profil
        follow_list = user.get("follow", [])
        # Comparaison sécurisée des types (int si possible, sinon string)
        try:
            current_user_id = int(current_user.id)
            follow_list_int = [int(f) for f in follow_list if f is not None]
            is_following = current_user_id in follow_list_int
        except Exception:
            # fallback string comparison
            follow_list_str = [str(f) for f in follow_list if f is not None]
            is_following = str(current_user.id) in follow_list_str

        # LOG pour debug
        logger.info(f"DEBUG: follow_list = {follow_list}")
        logger.info(f"DEBUG: current_user.id = {current_user.id}")
        logger.info(f"DEBUG: is_following = {is_following}")

        user["is_following"] = is_following

        # Mise en forme finale pour le frontend
        formatted_user = format_profile_for_frontend(user)

        logger.info(f"✅ Profil récupéré pour user_id={user_id}")
        return formatted_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur récupération profil user_id={user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


@router.post("/{target_id}/follow", status_code=status.HTTP_200_OK)
async def follow_user(target_id: str, current_user=Depends(get_current_user)):
    try:
        # Interdire de se suivre soi-même
        if str(current_user.id) == target_id or (target_id.isdigit() and int(target_id) == current_user.id):
            raise HTTPException(status_code=400, detail="Impossible de se suivre soi-même.")

        # Construire la requête Mongo
        if ObjectId.is_valid(target_id):
            query = {"_id": ObjectId(target_id)}
        elif target_id.isdigit():
            query = {"user_id": int(target_id)}
        else:
            raise HTTPException(status_code=400, detail="ID cible invalide.")

        # Vérifier que l'utilisateur cible existe
        user_to_follow = await profiles_collection.find_one(query)
        if not user_to_follow:
            raise HTTPException(status_code=404, detail="Utilisateur à suivre introuvable.")

        # Ajout sécurisé à la liste "follow"
        update_result = await profiles_collection.update_one(
            query,
            {
                "$addToSet": {"follow": current_user.id},
                "$inc": {"followers": 1}
            }
        )

        if update_result.modified_count == 0:
            return {
                "detail": "Vous suivez déjà cet utilisateur.",
                "followers": user_to_follow.get("followers", 0)
            }

        # Récupérer le nouveau nombre de followers
        updated_profile = await profiles_collection.find_one(query, {"followers": 1})
        new_count = updated_profile.get("followers", 0)

        return {
            "detail": "Suivi avec succès.",
            "followers": new_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du suivi de l'utilisateur {target_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur.")


@router.post("/{target_id}/unfollow")
async def unfollow_user(target_id: str, current_user=Depends(get_current_user)):
    try:
        follower_user_id = current_user.id

        if target_id.isdigit():
            if int(target_id) == follower_user_id:
                raise HTTPException(status_code=400, detail="Impossible de se désabonner de soi-même")
            query = {"user_id": int(target_id)}
        elif ObjectId.is_valid(target_id):
            query = {"_id": ObjectId(target_id)}
        else:
            raise HTTPException(status_code=400, detail="ID cible invalide")

        result = await profiles_collection.update_one(
            query,
            {"$pull": {"follow": follower_user_id}, "$inc": {"followers": -1}}
        )

        if result.modified_count == 0:
            return {"detail": "Déjà non suivi ou aucune modification."}

        updated_profile = await profiles_collection.find_one(query, {"followers": 1})
        followers = max(0, updated_profile.get("followers", 0))
        if followers == 0:
            await profiles_collection.update_one(query, {"$set": {"followers": 0}})

        return {"detail": "Ne suit plus l'utilisateur.", "followers": followers}

    except Exception as e:
        logger.error(f"Erreur dans unfollow_user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


@router.get("/{user_id}/status")
async def get_user_status(
    user_id: str,
    cache_control: str = Header(default="no-cache")
):
    """
    Récupère online_status et last_seen en temps réel
    """
    # 1. Validation de l'ID
    try:
        if user_id.isdigit():
            query = {"user_id": int(user_id)}
        elif ObjectId.is_valid(user_id):
            query = {"_id": ObjectId(user_id)}
        else:
            raise ValueError("ID invalide")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Récupération avec projection optimisée
    profile = await profiles_collection.find_one(
        query,
        {
            "_id": 0,
            "online_status": 1,
            "last_seen": 1,
            "last_activity": 1  # Nouveau champ à suivre
        }
    )

    if not profile:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    # 3. Calcul du statut en temps réel
    now = datetime.now(timezone.utc)
    last_seen = profile.get("last_seen")
    last_activity = profile.get("last_activity", last_seen)

    # 4. Détermination dynamique du statut
    is_online = False
    if last_activity:
        # Solution 1: Ensure last_activity is timezone-aware
        if last_activity.tzinfo is None:
            # Assume UTC if no timezone info
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        elif last_activity.tzinfo != timezone.utc:
            # Convert to UTC if different timezone
            last_activity = last_activity.astimezone(timezone.utc)
        
        time_diff = (now - last_activity).total_seconds()
        is_online = time_diff < 300  # 5 minutes de tolérance

    # 5. Réponse avec headers pour éviter le caching
    return {
        "online_status": is_online or profile.get("online_status", False),
        "last_seen": last_activity.isoformat() if last_activity else None,
        "computed_at": now.isoformat(),
        "is_realtime": True
    }


@router.post("/{user_id}/status")
async def update_user_status(
    user_id: str,
    status: dict,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    online_status = status.get("online_status")

    if online_status is None:
        raise HTTPException(status_code=400, detail="'online_status' est requis")

    try:
        user_id_int = int(user_id)
        query = {"user_id": user_id_int}
    except ValueError:
        if ObjectId.is_valid(user_id):
            query = {"_id": ObjectId(user_id)}
        else:
            raise HTTPException(status_code=400, detail="ID utilisateur invalide")

    update_data = {
        "online_status": online_status
    }

    # Cas où l'utilisateur est mis hors ligne
    if online_status is False:
        # Use timezone-aware datetime for consistency
        update_data["last_seen"] = datetime.now(timezone.utc)
        update_data["last_activity"] = datetime.now(timezone.utc)

    # Cas où l'utilisateur est mis en ligne (optionnel : accepte une date envoyée)
    elif status.get("last_seen"):
        try:
            last_seen_dt = datetime.fromisoformat(status["last_seen"])
            # Ensure timezone awareness
            if last_seen_dt.tzinfo is None:
                last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
            update_data["last_seen"] = last_seen_dt
            update_data["last_activity"] = last_seen_dt
        except Exception:
            raise HTTPException(status_code=400, detail="Format de date invalide")
    else:
        # User is online, update last_activity
        update_data["last_activity"] = datetime.now(timezone.utc)

    result = await profiles_collection.update_one(query, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    return {
        "message": "Statut mis à jour",
        "online_status": online_status,
        "last_seen": update_data.get("last_seen").isoformat() if update_data.get("last_seen") else None
    }


async def mark_users_offline_if_inactive():
    """
    Marque offline tous les users inactifs depuis > 3 minutes
    """
    timeout_limit = datetime.utcnow() - timedelta(minutes=3)
    result = await profiles_collection.update_many(
        {"last_seen": {"$lt": timeout_limit}},
        {"$set": {"online_status": False}}
    )
    logger.info(f"Users offline updated: {result.modified_count}")