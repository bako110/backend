from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
from typing import ForwardRef

# ===========================
# UTILISATEUR LÉGER (Organisateur)
# ===========================
class OrganizerOut(BaseModel):
    id: int
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str]
    model_config = ConfigDict(from_attributes=True)

# ===========================
# ENUMS
# ===========================
class EventCategory(str, Enum):
    BIRTHDAY = "birthday"
    MUSIC = "music"
    SOCIAL = "social"
    CULTURE = "culture"
    WORKSHOP = "workshop"
    SPORT = "sport"
    FOOD = "food"
    BUSINESS = "business"

class ActivityType(str, Enum):
    JOINED = "joined"
    LEFT = "left"
    COMMENTED = "commented"
    UPDATED = "updated"
    CREATED = "created"

# ===========================
# COMMENTAIRES
# ===========================
class EventCommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    parent_id: Optional[int] = None

class EventCommentCreate(EventCommentBase):
    pass

class EventCommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)

EventCommentResponse = ForwardRef('EventCommentResponse')

class EventCommentResponse(EventCommentBase):
    id: int
    event_id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    avatar_url: Optional[str] = None
    full_name: Optional[str] = None
    replies: List['EventCommentResponse'] = []
    model_config = ConfigDict(from_attributes=True)

# ===========================
# ÉVÉNEMENTS
# ===========================
class EventBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=2000)
    date: datetime
    location: str = Field(..., min_length=1, max_length=255)
    category: EventCategory
    price: str = Field(default="Gratuit", max_length=50)
    is_public: bool = Field(default=True)
    allow_comments: bool = Field(default=True)
    allow_sharing: bool = Field(default=True)
    max_attendees: Optional[int] = Field(default=None, gt=0)

class EventCreate(EventBase):
    image: Optional[str] = None

    @validator('date')
    def validate_date(cls, v):
        if v <= datetime.now(timezone.utc):
            raise ValueError("La date de l'événement doit être dans le futur")
        return v

    @validator('price')
    def validate_price(cls, v):
        if v != "Gratuit":
            if not (v.endswith('€') and v[:-1].replace('.', '').replace(',', '').isdigit()):
                raise ValueError("Format de prix invalide")
        return v

class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    date: Optional[datetime] = None
    location: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[EventCategory] = None
    price: Optional[str] = Field(None, max_length=50)
    image: Optional[str] = None
    is_public: Optional[bool] = None
    allow_comments: Optional[bool] = None
    allow_sharing: Optional[bool] = None
    max_attendees: Optional[int] = Field(None, gt=0)

    @validator('date')
    def validate_date(cls, v):
        if v is not None and v <= datetime.now(timezone.utc):
            raise ValueError("La date de l'événement doit être dans le futur")
        return v

class EventResponse(BaseModel):
    id: int
    title: str
    description: str
    date: datetime
    location: str
    category: str
    price: Optional[str]
    image: Optional[str]
    is_public: bool
    allow_comments: bool
    allow_sharing: bool
    max_attendees: Optional[int]
    created_at: datetime
    updated_at: datetime
    organizer_id: int
    organizer: OrganizerOut
    participant_count: int
    is_full: bool

    model_config = ConfigDict(from_attributes=True)

class EventWithDetails(EventResponse):
    participants: List[OrganizerOut] = []
    comments: List[EventCommentResponse] = []

class EventListResponse(BaseModel):
    events: List[EventResponse]
    total: int
    page: int
    per_page: int
    pages: int

class EventFilters(BaseModel):
    category: Optional[EventCategory] = None
    location: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_public: Optional[bool] = True
    organizer_id: Optional[int] = None
    search: Optional[str] = None

# ===========================
# PARTICIPATION & STATS
# ===========================
class ParticipationResponse(BaseModel):
    success: bool
    message: str
    participant_count: int
    userId: int

class EventAnalyticsResponse(BaseModel):
    event_id: int
    total_views: int
    total_participants: int
    participant_growth: List[dict]
    comment_count: int
    engagement_rate: float

class UserStatsResponse(BaseModel):
    user_id: int
    total_events_organized: int
    total_events_attended: int
    total_comments: int
    upcoming_events: int

# ===========================
# ACTIVITÉS
# ===========================
class EventActivityBase(BaseModel):
    event_id: int
    user_id: int
    activity_type: ActivityType
    data: Optional[dict] = None

class EventActivityCreate(EventActivityBase):
    pass

class EventActivity(EventActivityBase):
    id: int
    created_at: datetime
    user: OrganizerOut

    model_config = ConfigDict(from_attributes=True)

# ===========================
# WEBSOCKETS
# ===========================
class WebSocketMessage(BaseModel):
    type: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.now)

class UserJoinedMessage(BaseModel):
    type: str = "USER_JOINED"
    eventId: int
    userId: int
    user: OrganizerOut
    timestamp: datetime = Field(default_factory=datetime.now)

class UserLeftMessage(BaseModel):
    type: str = "USER_LEFT"
    eventId: int
    userId: int
    user: OrganizerOut
    timestamp: datetime = Field(default_factory=datetime.now)

class NewCommentMessage(BaseModel):
    type: str = "NEW_COMMENT"
    eventId: int
    comment: EventCommentResponse
    timestamp: datetime = Field(default_factory=datetime.now)

class EventUpdatedMessage(BaseModel):
    type: str = "EVENT_UPDATED"
    event: EventResponse
    timestamp: datetime = Field(default_factory=datetime.now)

class EventDeletedMessage(BaseModel):
    type: str = "EVENT_DELETED"
    eventId: int
    timestamp: datetime = Field(default_factory=datetime.now)

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime = Field(default_factory=datetime.now)

# ===========================
# RÉFÉRENCES CIRCULAIRES
# ===========================
EventCommentResponse.update_forward_refs()
