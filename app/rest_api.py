# app/rest_api.py
import time
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.auth.jwt_handler import decode_access_token

router = APIRouter()

# Cache en mémoire pour tickets : ticket -> {user_id, expires}
session_tickets = {}

OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="auth/token")

TICKET_EXPIRATION_SECONDS = 300  # 5 minutes

@router.post("/get-socket-ticket")
async def get_socket_ticket(token: str = Depends(OAUTH2_SCHEME)):
    """
    Génère un ticket temporaire utilisable pour socket.io à partir d'un JWT valide.
    """
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User ID absent dans token")

    ticket = secrets.token_urlsafe(32)
    session_tickets[ticket] = {
        "user_id": user_id,
        "expires": time.time() + TICKET_EXPIRATION_SECONDS,
    }

    return {"ticket": ticket}
