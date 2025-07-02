from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from datetime import datetime
import traceback
import time
import requests
import logging

from app.auth import models, schemas, password, jwt_handler
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.db.session import get_db
from app.db.mongo import profiles_collection

from app.utils.code import generate_verification_code
from app.utils.email import send_email_async
from app.utils.avatar import generate_default_avatar_url

logger = logging.getLogger(__name__)

router = APIRouter()

# Stock temporaire des codes de réinitialisation
reset_codes = {}

# Blacklist en mémoire pour tokens invalidés (logout)
blacklist = set()

GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
FACEBOOK_TOKEN_INFO_URL = "https://graph.facebook.com/me"


async def get_user_by_identifier(db: AsyncSession, identifier: str):
    """Récupère un utilisateur par email ou téléphone"""
    result = await db.execute(
        select(models.User).filter(
            or_(
                models.User.email == identifier,
                models.User.phone == identifier
            )
        )
    )
    return result.scalars().first()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: schemas.UserRegister, db: AsyncSession = Depends(get_db)):
    try:
        if not user.email and not user.phone:
            raise HTTPException(status_code=400, detail="Email ou téléphone requis")

        if user.email:
            result = await db.execute(select(models.User).filter(models.User.email == user.email))
            if result.scalars().first():
                raise HTTPException(status_code=400, detail="Email déjà enregistré")

        if user.phone:
            result = await db.execute(select(models.User).filter(models.User.phone == user.phone))
            if result.scalars().first():
                raise HTTPException(status_code=400, detail="Téléphone déjà enregistré")

        hashed = password.hash_password(user.password)

        avatar_url = getattr(user, 'avatar_url', None)
        if not avatar_url:
            avatar_url = generate_default_avatar_url(user.first_name, user.last_name)

        new_user = models.User(
            email=user.email,
            phone=user.phone,
            hashed_password=hashed,
            first_name=user.first_name,
            last_name=user.last_name,
            role="user"
            
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        user_id_int = int(new_user.id)

        profile_doc = {
            "user_id": user_id_int,
            "email": new_user.email,
            "phone": new_user.phone,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": None,
            "birthDate": None,
            "avatar_url": avatar_url,
            "coverPhoto": None,
            "bio": "",
            "location": "",
            "website": None,
            "online_status": False,
            "last_seen": None,
            "level": 1,
            "points": 0,
            "registered_at": datetime.utcnow(),
            "interests": [],
            "friends_count": 0,
            "friend_ids": [],
            "blocked_users": [],
            "notifications": []
        }

        profiles_collection.insert_one(profile_doc)

        return {"msg": "Utilisateur enregistré avec succès", "user_id": user_id_int}

    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


@router.post("/login")
async def login(user: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    try:
        db_user = await get_user_by_identifier(db, user.identifier)
        if not db_user or not password.verify_password(user.password, db_user.hashed_password):
            raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect")

        access_token = jwt_handler.create_access_token({
            "sub": db_user.email if db_user.email else db_user.phone,
            "role": db_user.role,
            "user_id": db_user.id
        })

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": db_user.id,
                "email": db_user.email,
                "phone": db_user.phone,
                "role": db_user.role
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


@router.post("/logout")
async def logout(request: Request, token: str = Depends(oauth2_scheme)):
    try:
        blacklist.add(token)
        return {"msg": "Déconnecté avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la déconnexion : {str(e)}")


@router.post("/forgot-password")
async def forgot_password(data: schemas.ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        db_user = await get_user_by_identifier(db, data.identifier)
        if not db_user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        code = generate_verification_code()
        expires_at = time.time() + 600

        reset_codes[data.identifier] = {
            "code": code,
            "expires": expires_at,
            "verified": False
        }

        if '@' in data.identifier:
            subject = "Réinitialisation de mot de passe"
            body = f"Voici votre code de réinitialisation : {code}\nIl expire dans 10 minutes."
            await send_email_async(subject, data.identifier, body)
        else:
            logger.info(f"[SMS] Code pour {data.identifier} : {code}")

        return {"msg": "Code de réinitialisation envoyé"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Erreur interne")


@router.post("/verify-code")
async def verify_code(data: schemas.VerifyCodeRequest):
    try:
        found_identifier = None
        for identifier, entry in reset_codes.items():
            if entry["code"] == data.code:
                found_identifier = identifier
                break

        if not found_identifier:
            raise HTTPException(status_code=400, detail="Code invalide")

        entry = reset_codes[found_identifier]

        if time.time() > entry["expires"]:
            reset_codes.pop(found_identifier, None)
            raise HTTPException(status_code=400, detail="Code expiré")

        reset_codes[found_identifier]["verified"] = True

        return {"msg": "Code vérifié avec succès", "identifier": found_identifier}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


@router.post("/reset-password")
async def reset_password(data: schemas.ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        verified_identifier = None
        for identifier, entry in reset_codes.items():
            if entry.get("verified", False):
                verified_identifier = identifier
                break

        if not verified_identifier:
            raise HTTPException(status_code=400, detail="Aucun code vérifié trouvé. Veuillez d'abord vérifier votre code.")

        code_entry = reset_codes[verified_identifier]
        if time.time() > code_entry["expires"]:
            reset_codes.pop(verified_identifier, None)
            raise HTTPException(status_code=400, detail="Code expiré")

        db_user = await get_user_by_identifier(db, verified_identifier)

        if not db_user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        hashed = password.hash_password(data.new_password)
        db_user.hashed_password = hashed
        await db.commit()

        reset_codes.pop(verified_identifier, None)

        return {"msg": "Mot de passe réinitialisé avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


async def cleanup_expired_codes():
    current_time = time.time()
    expired_keys = [identifier for identifier, entry in reset_codes.items() if current_time > entry["expires"]]
    for key in expired_keys:
        reset_codes.pop(key, None)
    return len(expired_keys)


@router.get("/me")
async def get_me(token: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        db_user = await get_user_by_identifier(db, token["sub"])

        if not db_user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")

        profile_query = {}
        if db_user.email:
            profile_query["email"] = db_user.email
        elif db_user.phone:
            profile_query["phone"] = db_user.phone
        else:
            profile_query["user_id"] = db_user.id

        profile = await profiles_collection.find_one(profile_query, {"_id": 0})

        return {
            "user": {
                "id": db_user.id,
                "email": db_user.email,
                "phone": db_user.phone,
                "first_name": db_user.first_name,
                "last_name": db_user.last_name,
                "role": db_user.role
            },
            "profile": profile
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


@router.post("/social-login")
async def social_login(request: schemas.SocialLoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        if request.platform not in ["google", "facebook"]:
            raise HTTPException(status_code=400, detail="Plateforme non supportée")

        user_data = {}

        if request.platform == "google":
            response = requests.get(GOOGLE_TOKEN_INFO_URL, params={"id_token": request.access_token})
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Token Google invalide")

            data = response.json()
            user_data = {
                "email": data.get("email"),
                "first_name": data.get("given_name"),
                "last_name": data.get("family_name")
            }

        elif request.platform == "facebook":
            fields = "id,email,first_name,last_name"
            response = requests.get(FACEBOOK_TOKEN_INFO_URL, params={"access_token": request.access_token, "fields": fields})
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Token Facebook invalide")

            data = response.json()
            user_data = {
                "email": data.get("email"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name")
            }

        email = user_data.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Impossible de récupérer l'email utilisateur")

        result = await db.execute(select(models.User).filter(models.User.email == email))
        user = result.scalars().first()

        if not user:
            user = models.User(
                email=email,
                hashed_password="",
                first_name=user_data.get("first_name", ""),
                last_name=user_data.get("last_name", ""),
                role=request.platform
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            profiles_collection.insert_one({
                "user_id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "level": 1,
                "points": 0,
                "online_status": False,
                "registered_at": datetime.utcnow(),
                "avatar_url": None
            })

        token_jwt = jwt_handler.create_access_token({
            "sub": user.email,
            "user_id": user.id,
            "role": user.role
        })

        return {
            "access_token": token_jwt,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")
