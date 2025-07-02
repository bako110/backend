from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime
import logging
import json
import os
import shutil
from pydantic import ValidationError

from app.db.session import get_db
from app.events.services import EventService, EventNotFoundError, EventFullError, PermissionError
from .schemas import (
    EventCreate, EventUpdate, EventFilters, EventResponse, OrganizerOut,
    EventListResponse, ParticipationResponse, ErrorResponse, EventCommentResponse, EventCommentCreate
)
from app.auth.schemas import UserSchema
from app.auth.dependencies import get_current_user, get_current_user_optional
from app.events.models import Event, EventComment
from app.db.mongo import profiles_collection

logger = logging.getLogger(__name__)
router = APIRouter()

# Retrieve an event with its relations (organizer and participants)
async def get_event_with_relations(db: AsyncSession, event_id: int):
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.organizer), selectinload(Event.participants))
        .filter(Event.id == event_id)
    )
    return result.scalars().first()

# ===============================
# EVENT CREATION
# ===============================
@router.post("/api/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: str = Form(...),
    image: UploadFile = File(None),
    current_user: UserSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new event with an optional image
    - **event_data**: JSON string representing the event
    - **image**: Optional image of the event
    """
    try:
        logger.info(f"Received event_data: {event_data}")

        # Load the JSON data sent
        event_dict = json.loads(event_data)
        logger.info(f"Parsed event_dict: {event_dict}")

        # Pydantic validation
        event = EventCreate(**event_dict)
        logger.info(f"Validated event: {event}")

        # Image processing
        image_path = None
        if image and image.filename:
            upload_dir = "static/uploads/events"
            os.makedirs(upload_dir, exist_ok=True)
            timestamp = int(datetime.now().timestamp())
            ext = image.filename.split('.')[-1] if '.' in image.filename else 'jpg'
            filename = f"event_{current_user.id}_{timestamp}.{ext}"
            image_path = os.path.join(upload_dir, filename)
            image_path = image_path.replace("\\", "/")

            with open(image_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)

            logger.info(f"Image saved: {image_path}")

        # Prepare final data
        event_data_dict = event.dict()
        if image_path:
            event_data_dict['image'] = image_path

        # Creation via service
        event_service = EventService(db)
        db_event = await event_service.create_event(event_data_dict, current_user.id)
        db_event = await get_event_with_relations(db, db_event.id)

        # Retrieve avatar from MongoDB profile
        profile = await profiles_collection.find_one({"user_id": current_user.id}, {"_id": 0, "avatar_url": 1})
        avatar_url = profile["avatar_url"] if profile and "avatar_url" in profile else None

        return EventResponse(
            id=db_event.id,
            title=db_event.title,
            description=db_event.description,
            date=db_event.date,
            location=db_event.location,
            category=db_event.category,
            price=db_event.price,
            image=db_event.image,
            is_public=db_event.is_public,
            allow_comments=db_event.allow_comments,
            allow_sharing=db_event.allow_sharing,
            max_attendees=db_event.max_attendees,
            created_at=db_event.created_at or datetime.utcnow(),
            updated_at=db_event.updated_at or datetime.utcnow(),
            organizer_id=db_event.organizer.id,
            organizer=OrganizerOut(
                id=db_event.organizer.id,
                email=db_event.organizer.email,
                first_name=db_event.organizer.first_name,
                last_name=db_event.organizer.last_name,
                full_name=db_event.organizer.full_name,
                avatar_url=avatar_url
            ),
            participant_count=len(db_event.participants),
            is_full=len(db_event.participants) >= db_event.max_attendees if db_event.max_attendees else False,
        )

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}, raw data: {event_data}")
        raise HTTPException(status_code=422, detail=f"Invalid JSON format: {str(e)}")

    except ValidationError as e:
        logger.error(f"Pydantic validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e.errors()}")

    except Exception as e:
        logger.exception("Error creating event:")
        raise HTTPException(status_code=500, detail="Internal error while creating the event")

# ===============================
# GET EVENTS
# ===============================
@router.get("/events", response_model=EventListResponse)
async def get_events(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    organizer_id: Optional[int] = Query(None, description="Organizer ID"),
    search: Optional[str] = Query(None, description="Text search"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[UserSchema] = Depends(get_current_user_optional)
):
    try:
        service = EventService(db)
        user_id = current_user.id if current_user else None

        filters = None
        if any([category, location, date_from, date_to, organizer_id, search]):
            filters = EventFilters(
                category=category,
                location=location,
                date_from=date_from,
                date_to=date_to,
                organizer_id=organizer_id,
                search=search
            )

        result = await service.get_events(page, per_page, filters, user_id)

        return EventListResponse(**result)

    except Exception as e:
        logger.error(f"Error retrieving event list: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving events"
        )
# 🔹 Créer un commentaire
@router.post("/events/{event_id}/comments/", response_model=EventCommentResponse)
async def create_comment(
    event_id: int,
    comment: EventCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    try:
        # Vérifier que l'événement existe
        event = await db.get(Event, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Créer le commentaire
        db_comment = EventComment(
            content=comment.content,
            parent_id=comment.parent_id,
            event_id=event_id,
            author_id=current_user.id,
        )
        db.add(db_comment)
        await db.commit()
        await db.refresh(db_comment)

        # Recharger avec les relations
        result = await db.execute(
            select(EventComment)
            .where(EventComment.id == db_comment.id)
            .options(
                selectinload(EventComment.replies),
                selectinload(EventComment.parent)
            )
        )
        db_comment_full = result.scalars().first()
        return db_comment_full

    except Exception as e:
        logger.error(f"Error creating comment: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal error while creating the comment"
        )


def build_comment_response(comment: EventComment) -> EventCommentResponse:
    return EventCommentResponse(
        id=comment.id,
        event_id=comment.event_id,
        author_id=comment.author_id,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        replies=[build_comment_response(reply) for reply in comment.replies] if comment.replies else []
    )

@router.get("/events/{event_id}/comments/", response_model=List[EventCommentResponse])
async def read_comments(event_id: int, db: AsyncSession = Depends(get_db)):
    # Vérifie que l'événement existe
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Récupère uniquement les commentaires racines (sans parent)
    result = await db.execute(
        select(EventComment)
        .where(EventComment.event_id == event_id, EventComment.parent_id == None)
        .options(selectinload(EventComment.replies))
        .order_by(EventComment.created_at.asc())
    )
    root_comments = result.scalars().all()

    # Fonction récursive pour construire le schema avec replies
    def to_response(comment: EventComment) -> EventCommentResponse:
        return EventCommentResponse(
            id=comment.id,
            event_id=comment.event_id,
            author_id=comment.author_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            replies=[to_response(reply) for reply in comment.replies] if comment.replies else []
        )

    return [to_response(c) for c in root_comments]