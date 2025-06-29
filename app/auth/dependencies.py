from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from bson import ObjectId

from app.db.mongo import profiles_collection  # ✅ la bonne collection MongoDB
from app.users.models import UserProfile      # ✅ ton modèle principal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SECRET_KEY = "SUPER_SECRET"
ALGORITHM = "HS256"

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserProfile:
    try:
        # Déchiffrement du token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Token invalide (aucun ID)")

        # Récupération du document dans la collection Mongo
        profile_doc = await profiles_collection.find_one({"user_id": int(user_id)})

        if not profile_doc:
            raise HTTPException(status_code=404, detail="Profil utilisateur introuvable")

        return UserProfile(**profile_doc)

    except JWTError:
        raise HTTPException(status_code=403, detail="Jeton non valide")
