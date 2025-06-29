# ===== MISE À JOUR DU MAIN.PY =====

# main.py - VERSION CORRIGÉE
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.auth.api import router as auth_router
from app.users.api import router as users_router
from app.friends.apifriends import router as friends_router



app = FastAPI()

# Créer le dossier static/uploads s'il n'existe pas
upload_dir = Path("static/uploads")
upload_dir.mkdir(parents=True, exist_ok=True)

# Servir les fichiers statiques
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(friends_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À limiter en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)