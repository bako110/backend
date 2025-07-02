from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging

from app.db.session import get_db
from app.db.mongo import profiles_collection
from app.auth.models import User  # PostgreSQL
from app.users.models import UserProfile  # MongoDB (facultatif)
from app.config import settings  # Utilisation de settings importé depuis config.py

# Initialiser le logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Utilisé pour extraire le token depuis le header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# 🔒 Récupération obligatoire de l'utilisateur PostgreSQL
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    🔐 Récupère l'utilisateur courant à partir du token JWT.
    """
    logger.info(f"🔐 Token reçu du frontend : {token}")

    if not token:
        logger.warning("⛔ Accès refusé : token manquant")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        logger.warning(f"⛔ Token invalide ou expiré. Erreur : {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub: Optional[str] = payload.get("sub")
    if not sub:
        logger.warning("⚠️ Token valide mais champ 'sub' manquant")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide : 'sub' manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(payload.get("user_id"))
    except (ValueError, TypeError) as e:
        logger.warning(f"⚠️ Champ 'user_id' mal formé dans token : {payload.get('user_id')} ({e})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide : 'user_id' mal formé",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id_int))
    user = result.scalars().first()
    if not user:
        logger.warning(f"❌ Utilisateur introuvable : id={user_id_int}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"✅ Utilisateur authentifié : id={user.id}, email={user.email}")
    return user

# 🔓 Version optionnelle avec MongoDB (utile pour les profils, facultatif)
async def get_current_user_optional(
    token: str = Depends(oauth2_scheme)
) -> Optional[UserProfile]:
    """
    Version non bloquante. Retourne le profil utilisateur MongoDB si token valide,
    sinon retourne None.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            return None

        profile_doc = await profiles_collection.find_one({"user_id": str(sub)})
        if not profile_doc:
            return None

        profile_doc["_id"] = str(profile_doc["_id"])  # convertir l'ObjectId
        return UserProfile(**profile_doc)

    except JWTError:
        logger.warning("⚠️ Token optionnel invalide (version profil)")
        return None
