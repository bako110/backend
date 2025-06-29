from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from datetime import datetime
import random
import string
import traceback
import requests
import traceback, time

from app.utils.code import generate_verification_code
from app.utils.email import send_email_async
from app.utils.avatar import generate_default_avatar_url



from app.auth import models, schemas, password, jwt_handler
from app.db.session import get_db
from app.db.mongo import profiles_collection

router = APIRouter(prefix="/auth", tags=["auth"])

# Stock temporaire des codes de réinitialisation
reset_codes = {}

# Blacklist en mémoire pour tokens invalidés (logout)
blacklist = set()

# OAuth2 scheme pour extraire le token Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# URLs pour la vérification des tokens sociaux
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
FACEBOOK_TOKEN_INFO_URL = "https://graph.facebook.com/me"


# 🔐 Fonction utilitaire pour récupérer un utilisateur par email ou téléphone
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


# 🔐 Enregistrement d'un utilisateur
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: schemas.UserRegister, db: AsyncSession = Depends(get_db)):
    try:
        # Vérifier qu'au moins email ou phone est fourni
        if not user.email and not user.phone:
            raise HTTPException(status_code=400, detail="Email ou téléphone requis")

        # Vérifier si email existe déjà
        if user.email:
            result = await db.execute(select(models.User).filter(models.User.email == user.email))
            existing_user_email = result.scalars().first()
            if existing_user_email:
                raise HTTPException(status_code=400, detail="Email déjà enregistré")

        # Vérifier si téléphone existe déjà
        if user.phone:
            result = await db.execute(select(models.User).filter(models.User.phone == user.phone))
            existing_user_phone = result.scalars().first()
            if existing_user_phone:
                raise HTTPException(status_code=400, detail="Téléphone déjà enregistré")

        # Hash du mot de passe
        hashed = password.hash_password(user.password)

        # Générer avatar par défaut si aucun avatar fourni
        avatar_url = getattr(user, 'avatar_url', None)
        if not avatar_url:
            avatar_url = generate_default_avatar_url(user.first_name, user.last_name)

        new_user = models.User(
            email=user.email,
            phone=user.phone,
            hashed_password=hashed,
            first_name=user.first_name,
            last_name=user.last_name,
            role="user"  # Par défaut
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        # Créer le profil MongoDB avec avatar_url
        profile_doc = {
            "user_id": new_user.id,
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

        return {"msg": "Utilisateur enregistré avec succès", "user_id": new_user.id}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


# 🔐 Connexion d'un utilisateur
@router.post("/login")
async def login(user: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    try:
        # Rechercher l'utilisateur par email ou téléphone
        db_user = await get_user_by_identifier(db, user.identifier)
        
        if not db_user or not password.verify_password(user.password, db_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Identifiant ou mot de passe incorrect"
            )

        # Créer le token avec l'identifiant principal (email si disponible, sinon téléphone)
        token_subject = db_user.email if db_user.email else db_user.phone
        access_token = jwt_handler.create_access_token({
            "sub": token_subject,
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


# 🔐 Déconnexion (logout)
@router.post("/logout")
async def logout(request: Request, token: str = Depends(oauth2_scheme)):
    try:
        blacklist.add(token)
        return {"msg": "Déconnecté avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la déconnexion : {str(e)}")


# 🔐 Demander un code de réinitialisation
reset_codes = {}  # Ex: { "email@ex.com": { "code": "123456", "expires": 1723201723 } }

@router.post("/forgot-password")
async def forgot_password(data: schemas.ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        db_user = await get_user_by_identifier(db, data.identifier)
        if not db_user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        code = generate_verification_code()
        expires_at = time.time() + 600  # 10 minutes
        
        # Stocker le code avec l'identifiant et marquer comme non vérifié
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
            print(f"[SMS] Code pour {data.identifier} : {code}")

        return {"msg": "Code de réinitialisation envoyé"}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur interne")


@router.post("/verify-code")
async def verify_code(data: schemas.VerifyCodeRequest):
    try:
        # Parcourir tous les codes pour trouver celui qui correspond
        found_identifier = None
        for identifier, entry in reset_codes.items():
            if entry["code"] == data.code:
                found_identifier = identifier
                break
        
        if not found_identifier:
            raise HTTPException(status_code=400, detail="Code invalide")
        
        entry = reset_codes[found_identifier]
        
        # Vérifier l'expiration
        if time.time() > entry["expires"]:
            # Supprimer le code expiré
            reset_codes.pop(found_identifier, None)
            raise HTTPException(status_code=400, detail="Code expiré")
        
        # Marquer le code comme vérifié
        reset_codes[found_identifier]["verified"] = True
        
        return {"msg": "Code vérifié avec succès", "identifier": found_identifier}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


@router.post("/reset-password")
async def reset_password(data: schemas.ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Trouver l'identifiant correspondant au code vérifié
        verified_identifier = None
        for identifier, entry in reset_codes.items():
            if entry.get("verified", False):
                verified_identifier = identifier
                break
        
        if not verified_identifier:
            raise HTTPException(status_code=400, detail="Aucun code vérifié trouvé. Veuillez d'abord vérifier votre code.")
        
        # Vérifier que le code n'a pas expiré
        code_entry = reset_codes[verified_identifier]
        if time.time() > code_entry["expires"]:
            reset_codes.pop(verified_identifier, None)
            raise HTTPException(status_code=400, detail="Code expiré")
        
        # Rechercher l'utilisateur par email ou téléphone
        db_user = await get_user_by_identifier(db, verified_identifier)
        
        if not db_user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        # Mettre à jour le mot de passe (utiliser newPassword au lieu de new_password)
        hashed = password.hash_password(data.newPassword)
        db_user.hashed_password = hashed
        await db.commit()

        # Supprimer le code utilisé
        reset_codes.pop(verified_identifier, None)

        return {"msg": "Mot de passe réinitialisé avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


# Fonction optionnelle pour nettoyer les codes expirés
async def cleanup_expired_codes():
    """Nettoie les codes expirés du dictionnaire"""
    current_time = time.time()
    expired_keys = [
        identifier for identifier, entry in reset_codes.items() 
        if current_time > entry["expires"]
    ]
    for key in expired_keys:
        reset_codes.pop(key, None)
    
    return len(expired_keys)

# 🔐 Obtenir les informations du profil connecté
@router.get("/me")
async def get_me(request: Request, token: dict = Depends(jwt_handler.get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        # Récupérer le token depuis l'en-tête Authorization
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Token manquant")
        
        token_str = auth_header.split(" ")[1]
        
        # Vérifier si le token est blacklisté (déconnecté)
        if token_str in blacklist:
            raise HTTPException(status_code=401, detail="Token invalide (déconnecté)")

        # Rechercher l'utilisateur par l'identifiant du token
        db_user = await get_user_by_identifier(db, token["sub"])
        
        if not db_user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")

        # Récupérer le profil MongoDB
        profile_query = {}
        if db_user.email:
            profile_query["email"] = db_user.email
        elif db_user.phone:
            profile_query["phone"] = db_user.phone
        else:
            profile_query["user_id"] = db_user.id

        profile = profiles_collection.find_one(profile_query, {"_id": 0})

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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")


# 🔐 Connexion via les réseaux sociaux (Google/Facebook)
@router.post("/social-login")
async def social_login(
    request: schemas.SocialLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Gère la connexion via Google ou Facebook
    Paramètres:
    - platform: 'google' ou 'facebook'
    - access_token: token reçu depuis le frontend
    """
    try:
        if request.platform not in ["google", "facebook"]:
            raise HTTPException(status_code=400, detail="Plateforme non supportée")

        user_data = {}

        if request.platform == "google":
            # Vérification du token Google
            response = requests.get(
                GOOGLE_TOKEN_INFO_URL,
                params={"id_token": request.access_token}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Token Google invalide")
            
            data = response.json()
            user_data = {
                "email": data.get("email"),
                "first_name": data.get("given_name"),
                "last_name": data.get("family_name")
            }

        elif request.platform == "facebook":
            # Vérification du token Facebook
            fields = "id,email,first_name,last_name"
            response = requests.get(
                FACEBOOK_TOKEN_INFO_URL,
                params={
                    "access_token": request.access_token,
                    "fields": fields
                }
            )
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Token Facebook invalide")
            
            data = response.json()
            user_data = {
                "email": data.get("email"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name")
            }

        # Vérifie que l'email est présent
        email = user_data.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Impossible de récupérer l'email utilisateur")

        # Rechercher ou créer l'utilisateur dans PostgreSQL
        result = await db.execute(select(models.User).filter(models.User.email == email))
        user = result.scalars().first()

        if not user:
            # Création d'un nouvel utilisateur
            user = models.User(
                email=email,
                hashed_password="",  # Pas de mot de passe pour login social
                first_name=user_data.get("first_name", ""),
                last_name=user_data.get("last_name", ""),
                role=request.platform  # "google" ou "facebook"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            # Créer le profil dans MongoDB
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

        # Générer le token JWT
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")