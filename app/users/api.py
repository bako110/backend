from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from app.users import services
from app.users.models import UserProfile, UserProfileUpdate
import uuid
from pathlib import Path
import aiofiles
import logging
from app.auth.dependencies import get_current_user  
import urllib.parse
from fastapi import APIRouter, Depends  # ✅ ajoute Depends ici


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
        elif image_type == "cover" and hasattr(profile, 'cover_photo_url'):
            old_url = profile.cover_photo_url
        
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


# ✏️ PUT /users/profile/{identifier} - Mettre à jour un profil
@router.put("/profile/{identifier}", response_model=UserProfile)
async def update_profile(identifier: str, updates: UserProfileUpdate):
    """Mettre à jour un profil utilisateur par email, téléphone ou ID"""
    try:
        decoded_identifier = urllib.parse.unquote(identifier)
        update_data = updates.model_dump(exclude_unset=True, exclude_none=True)
        updated = await services.update_profile_by_identifier(decoded_identifier, update_data)
        
        if not updated:
            raise HTTPException(status_code=404, detail="Profil non trouvé")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur mise à jour profil: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


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
            {"cover_photo_url": url}
        )

        if not profile:
            filepath.unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Profil non trouvé")

        return {
            "message": "Photo de couverture mise à jour ✅", 
            "cover_photo_url": url, 
            "profile": profile
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur changement couverture: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")

        from fastapi import APIRouter, Depends

# ➤ Met à jour le statut en ligne de l'utilisateur
@router.post("/onligne")
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