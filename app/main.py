import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.auth.api import router as auth_router
from app.users.api import router as users_router
from app.friends.apifriends import router as friends_router
from app.events.api import router as event_router

logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

# Création dossier statique uploads
upload_dir = Path("static/upload")
upload_dir.mkdir(parents=True, exist_ok=True)

# Monture des fichiers statiques
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ajout des routers avec préfixes
app.include_router(auth_router, prefix="/auth")
app.include_router(users_router)
app.include_router(friends_router)
app.include_router(event_router)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Bienvenue sur mon API FastAPI déployée sur Render !"}
