from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from enum import Enum

# ────────────────────────────────
# PROFIL UTILISATEUR COMPLET
# ────────────────────────────────

class UserProfile(BaseModel):
    id: Optional[str] = Field(None, alias="_id")  # ID MongoDB
    user_id: Optional[int] = None                # ID numérique
    email: Optional[EmailStr] = None            # Email

    # Informations personnelles
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    birthDate: Optional[str] = None  # Format: 'YYYY-MM-DD'

    # Visibilité et activité
    bio: Optional[str] = ""
    location: Optional[str] = ""
    website: Optional[str] = None
    avatar_url: Optional[str] = None
    coverPhoto: Optional[str] = None
    online_status: Optional[bool] = False
    last_seen: Optional[datetime] = None

    # Données système
    level: Optional[int] = 1
    points: Optional[int] = 0
    registered_at: Optional[datetime] = None

    # Données sociales
    interests: List[str] = Field(default_factory=list)
    friends_count: Optional[int] = 0
    friend_ids: List[str] = Field(default_factory=list)
    blocked_users: List[str] = Field(default_factory=list)
    notifications: List[dict] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        }
    )

# ────────────────────────────────
# MISE À JOUR DU PROFIL
# ────────────────────────────────

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    birthDate: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    avatar_url: Optional[str] = None
    coverPhoto: Optional[str] = None
    online_status: Optional[bool] = None
    interests: Optional[List[str]] = None
    last_seen: Optional[datetime] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

# ────────────────────────────────
# ENTRÉE ET SORTIE MINIMALE
# ────────────────────────────────

class UserProfileIn(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    avatar_url: Optional[str]
    coverPhoto: Optional[str]
    bio: Optional[str]

class UserProfileOut(UserProfileIn):
    user_email: str

# ────────────────────────────────
# MODÈLE POUR LES AMITIÉS
# ────────────────────────────────

class FriendshipStatus(str, Enum):
    pending = "pending"     # En attente d'approbation
    accepted = "accepted"   # Acceptée
    rejected = "rejected"   # Refusée
    blocked = "blocked"     # Bloqué
    removed = "removed"     # Supprimée

class Friendship(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    sender_id: str           # ID de l'utilisateur qui envoie
    receiver_id: str         # ID du destinataire
    status: FriendshipStatus = FriendshipStatus.pending
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None
        }
    )
