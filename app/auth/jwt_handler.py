from datetime import datetime, timedelta
from jose import jwt, JWTError
from typing import Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crée un token JWT signé avec les informations fournies.

    :param data: Dictionnaire avec les données à encoder (ex: {"user_id": 5})
    :param expires_delta: Durée de validité du token (timedelta)
    :return: Token JWT encodé
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})

    if "user_id" in to_encode:
        to_encode["sub"] = str(to_encode["user_id"])


    token = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    # logger.info(f"✅ Token généré pour sub={to_encode.get('sub')}, expire à {expire}")
    logger.info(f"✅ Token généré pour user_id={data.get('user_id')} : {token}")
    return token


def decode_access_token(token: str) -> Optional[dict]:
    """
    🔐 Décode et vérifie un token JWT.
    
    Retourne le payload si le token est valide, sinon None.
    Vérifie aussi la présence du champ 'sub' (subject) recommandé dans le standard JWT.

    :param token: JWT à décoder
    :return: Dictionnaire du payload ou None si le token est invalide ou mal formé
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])

        sub = payload.get("sub")
        if not sub:
            logger.warning("⚠️ Token valide mais champ 'sub' manquant dans le payload.")
            return None

        return payload

    except JWTError as e:
        logger.warning(f"❌ Échec de décodage du token : {e}")
        return None


def verify_access_token(token: str) -> Optional[dict]:
    """
    Vérifie le token et retourne son contenu si valide, sinon None.

    :param token: JWT à vérifier
    :return: Payload du token ou None
    """
    return decode_access_token(token)
