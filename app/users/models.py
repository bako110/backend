from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Union
from datetime import datetime
from bson import ObjectId
from enum import Enum

# Contact simplifié
class ContactInfo(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None

# ────────────────────────────────
# PROFIL UTILISATEUR COMPLET (simplifié et complet)
# ────────────────────────────────
class UserProfile(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: Optional[Union[int, str]] = None
    email: Optional[EmailStr] = None

    # Infos personnelles
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    birthDate: Optional[str] = None

    # Profil visuel et visibilité
    bio: Optional[str] = ""
    location: Optional[str] = ""
    website: Optional[str] = None
    avatar_url: Optional[str] = None
    coverPhoto: Optional[str] = None
    online_status: Optional[bool] = False
    last_seen: Optional[datetime] = None

    # Métadonnées
    level: Optional[int] = 1
    points: Optional[int] = 0
    registered_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    # Relations et interactions
    interests: List[str] = Field(default_factory=list)
    friends_count: Optional[int] = 0
    friend_ids: List[str] = Field(default_factory=list)
    blocked_users: List[str] = Field(default_factory=list)
    notifications: List[dict] = Field(default_factory=list)

    followers: Optional[int] = 0               # compteur d'abonnés
    follow: List[str] = Field(default_factory=list)  # liste des IDs suivis

    views: Optional[int] = 0                   # nombre de vues

    # Données professionnelles simplifiées (texte)
    experience: Optional[str] = None
    education: Optional[str] = None
    skills: Optional[List[str]] = Field(default_factory=list)
    contact: Optional[ContactInfo] = Field(default_factory=ContactInfo)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        }
    )


# ────────────────────────────────
# MISE À JOUR DU PROFIL (option simplifiée pour update partiel)
# ────────────────────────────────
class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    birthDate: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    avatar_url: Optional[str] = None
    coverPhoto: Optional[str] = None
    online_status: Optional[bool] = None
    last_seen: Optional[datetime] = None
    interests: Optional[List[str]] = None

    # Données professionnelles simplifiées
    experience: Optional[str] = None
    education: Optional[str] = None
    skills: Optional[List[str]] = None

    # Nouveaux champs ajoutés
    title: Optional[str] = None
    company: Optional[str] = None

    contact: Optional[ContactInfo] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )


# ────────────────────────────────
# ENTRÉE ET SORTIE MINIMALE (pour certains endpoints spécifiques)
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
