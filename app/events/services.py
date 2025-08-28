import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import json
from app.db.mongo import profiles_collection
from app.auth.schemas import UserSchema
from app.events.models import Event, EventCategory, EventActivity, EventComment
from app.events.schemas import (
    EventCreate,
    EventFilters,
    EventResponse,
    ActivityType,
    OrganizerOut,
    EventCommentResponse,
    EventCommentCreate
)

logger = logging.getLogger(__name__)

class EventNotFoundError(Exception):
    pass

class EventFullError(Exception):
    pass

class PermissionError(Exception):
    pass

class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, event_data: EventCreate | dict, organizer_id: str) -> Event:
        try:
            if isinstance(event_data, dict):
                event_dict = event_data
            elif hasattr(event_data, 'dict'):
                event_dict = event_data.dict()
            else:
                event_dict = event_data.__dict__

            if 'category' in event_dict and event_dict['category']:
                if event_dict['category'] not in [cat.value for cat in EventCategory]:
                    raise ValueError(f"Invalid category: {event_dict['category']}")

            required_fields = ['title', 'description', 'date', 'location', 'category']
            for field in required_fields:
                if field not in event_dict or event_dict[field] is None:
                    raise ValueError(f"The field {field} is required")

            if isinstance(event_dict['date'], str):
                try:
                    event_dict['date'] = datetime.fromisoformat(event_dict['date'].replace('Z', '+00:00'))
                except ValueError:
                    raise ValueError("Invalid date format")

            if event_dict['date'] <= datetime.now(timezone.utc):
                raise ValueError("Event date must be in the future")

            if 'price' not in event_dict or event_dict['price'] is None:
                event_dict['price'] = "Gratuit"

            if 'max_attendees' in event_dict and event_dict['max_attendees'] is not None:
                if event_dict['max_attendees'] <= 0:
                    raise ValueError("Max attendees must be positive")

            db_event = Event(
                title=event_dict['title'][:100],
                description=event_dict['description'],
                date=event_dict['date'],
                location=event_dict['location'][:255],
                category=event_dict['category'],
                price=event_dict.get('price', 'Gratuit')[:50],
                image=event_dict.get('image', None),
                is_public=event_dict.get('is_public', True),
                allow_comments=event_dict.get('allow_comments', True),
                allow_sharing=event_dict.get('allow_sharing', True),
                max_attendees=event_dict.get('max_attendees', None),
                organizer_id=int(organizer_id)
            )

            self.db.add(db_event)
            await self.db.flush()

            logger.info(f"Event created: id={db_event.id}, title={db_event.title}, by organizer_id={organizer_id}")
            await self._create_activity(
                event_id=db_event.id,
                user_id=organizer_id,
                activity_type=ActivityType.CREATED,
                data={"event_title": db_event.title}
            )

            await self.db.commit()
            await self.db.refresh(db_event)
            logger.info(f"Event created: {db_event.id} by user {organizer_id}")
            return db_event

        except ValueError as ve:
            await self.db.rollback()
            logger.error(f"Validation error creating event: {ve}")
            raise ve
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating event: {e}")
            raise e

    @staticmethod
    async def serialize_event(event: Event) -> EventResponse:
        return EventResponse.from_orm(event)

    async def get_events(
        self,
        page: int = 1,
        per_page: int = 20,
        filters: Optional[EventFilters] = None,
        current_user_id: Optional[int] = None
    ) -> dict:
        offset = (page - 1) * per_page

        # Sous-requête qui compte les commentaires par event_id
        comment_count_subq = (
            select(
                EventComment.event_id,
                func.count(EventComment.id).label("comments_count")
            )
            .group_by(EventComment.event_id)
            .subquery()
        )

        # Join entre Event et cette sous-requête
        query = (
            select(Event, comment_count_subq.c.comments_count)
            .outerjoin(comment_count_subq, Event.id == comment_count_subq.c.event_id)
            .options(
                selectinload(Event.organizer),
                selectinload(Event.participants)
            )
        )

        # Appliquer filtres existants
        if filters:
            if filters.category:
                query = query.where(Event.category == filters.category)
            if filters.location:
                query = query.where(Event.location.ilike(f"%{filters.location}%"))
            if filters.date_from:
                query = query.where(Event.date >= filters.date_from)
            if filters.date_to:
                query = query.where(Event.date <= filters.date_to)
            if filters.organizer_id:
                query = query.where(Event.organizer_id == filters.organizer_id)
            if filters.search:
                search = f"%{filters.search}%"
                query = query.where(
                    or_(
                        Event.title.ilike(search),
                        Event.description.ilike(search)
                    )
                )

        count_query = query.with_only_columns(func.count(Event.id)).order_by(None)
        total_result = await self.db.execute(count_query)
        total_events = total_result.scalar_one()

        query = query.offset(offset).limit(per_page)
        result = await self.db.execute(query)

        # Chaque résultat est un tuple (Event, comments_count)
        rows = result.all()
        total_pages = (total_events + per_page - 1) // per_page
        serialized = []

        for event, comments_count in rows:
            print(f"Event {event.id} has {comments_count or 0} comments")
            profile = await profiles_collection.find_one(
                {"user_id": event.organizer.id},
                {"_id": 0, "avatar_url": 1}
            )
            avatar_url = profile["avatar_url"] if profile and "avatar_url" in profile else None
            organizer_data = {
                "id": event.organizer.id,
                "email": event.organizer.email or "",
                "first_name": event.organizer.first_name,
                "last_name": event.organizer.last_name,
                "full_name": f"{event.organizer.first_name} {event.organizer.last_name}",
                "phone": getattr(event.organizer, 'phone', None),
                "avatar_url": avatar_url
            }
            participant_count = len(event.participants)
            is_full = (
                event.max_attendees is not None and
                participant_count >= event.max_attendees
            )
            image_path = event.image
            if image_path and image_path.startswith("static/"):
                image_path = image_path[len("static/"):]

            event_data = {
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "date": event.date,
                "location": event.location,
                "category": event.category,
                "price": event.price,
                "image": image_path,
                "is_public": event.is_public,
                "allow_comments": event.allow_comments,
                "allow_sharing": event.allow_sharing,
                "max_attendees": event.max_attendees,
                "created_at": event.created_at,
                "updated_at": event.updated_at,
                "organizer_id": event.organizer.id,
                "organizer": organizer_data,
                "organizer_name": organizer_data["full_name"],
                "participant_count": participant_count,
                "is_full": is_full,
                "comments_count": comments_count or 0,
            }
            serialized.append(event_data)

        return {
            "events": serialized,
            "total": total_events,
            "pages": total_pages,
            "page": page,
            "per_page": per_page,
        }

    async def _create_activity(self, event_id: int, user_id: str, activity_type: ActivityType, data: dict):
        json_data = json.dumps(data) if data is not None else None
        activity = EventActivity(
            event_id=event_id,
            user_id=int(user_id),
            activity_type=activity_type,
            data=json_data
        )
        self.db.add(activity)
        await self.db.flush()

    async def get_comments(self, event_id: int) -> List[EventCommentResponse]:
        logger.info(f"Start loading comments for event_id={event_id}")

        # 1. Récupérer les commentaires parents (parent_id is None), avec auteur chargé
        result = await self.db.execute(
            select(EventComment)
            .where(
                EventComment.event_id == event_id,
                EventComment.parent_id.is_(None)
            )
            .order_by(EventComment.created_at.asc())
            .options(selectinload(EventComment.author))
        )
        parents = result.scalars().all()
        logger.info(f"Step 1: Found {len(parents)} parent comments")

        if not parents:
            logger.warning(f"No parent comments found for event_id={event_id}")
            return []

        parent_ids = [c.id for c in parents]

        # 2. Récupérer toutes les réponses associées, avec auteur aussi
        result = await self.db.execute(
            select(EventComment)
            .where(EventComment.parent_id.in_(parent_ids))
            .options(selectinload(EventComment.author))
        )
        replies = result.scalars().all()
        logger.info(f"Step 2: Found {len(replies)} reply comments")

        # 3. Construire un dictionnaire parent_id -> liste de réponses
        replies_by_parent = {}
        for reply in replies:
            replies_by_parent.setdefault(reply.parent_id, []).append(reply)

        # 4. Récupérer tous les user_id des auteurs (parents + replies)
        user_ids = {comment.author_id for comment in parents + replies if comment.author_id is not None}
        logger.info(f"Step 3: Extracted user_ids from comments: {user_ids}")

        # 5. Charger en une seule requête les avatars depuis MongoDB
        avatar_map = {}
        cursor = profiles_collection.find(
            {"user_id": {"$in": list(user_ids)}},
            {"_id": 0, "user_id": 1, "avatar_url": 1}
        )
        async for profile in cursor:
            avatar_map[profile["user_id"]] = profile.get("avatar_url")

        logger.info(f"Step 4: Loaded avatar map for users: {list(avatar_map.keys())}")

        # 6. Vérification détaillée des parents et auteurs
        logger.info("Step 5: Inspecting parent comments and their authors:")
        for c in parents:
            if c.author is None:
                logger.error(f"Parent comment ID {c.id} has no author loaded! author_id={c.author_id}")
            else:
                logger.debug(f"Parent comment ID {c.id} author: id={c.author.id}, first_name='{c.author.first_name}', last_name='{c.author.last_name}'")

        logger.info("Step 6: Inspecting reply comments and their authors:")
        for r in replies:
            if r.author is None:
                logger.error(f"Reply comment ID {r.id} has no author loaded! author_id={r.author_id}")
            else:
                logger.debug(f"Reply comment ID {r.id} author: id={r.author.id}, first_name='{r.author.first_name}', last_name='{r.author.last_name}'")

        logger.info(f"Step 7: Avatar map keys: {list(avatar_map.keys())}")

        # 7. Fonction récursive pour construire la hiérarchie, avec avatar_url (Mongo) et full_name (PostgreSQL)
        def build_tree(comment: EventComment):
            author = comment.author
            avatar_url = None
            full_name = "Utilisateur supprimé"  # fallback si auteur supprimé
            if author:
                first_name = author.first_name or ""
                last_name = author.last_name or ""
                full_name = f"{first_name} {last_name}".strip() or "Anonyme"
                avatar_url = avatar_map.get(author.id)

            # Logs détaillés pour debug
            logger.debug(f"Building comment id={comment.id}:")
            logger.debug(f"  author_id={comment.author_id}")
            logger.debug(f"  full_name='{full_name}'")
            logger.debug(f"  avatar_url='{avatar_url}'")

            return EventCommentResponse(
                id=comment.id,
                content=comment.content,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                event_id=comment.event_id,
                author_id=comment.author_id,
                parent_id=comment.parent_id,
                avatar_url=avatar_url,
                full_name=full_name,
                replies=[build_tree(child) for child in replies_by_parent.get(comment.id, [])]
            )

        # 8. Retourner la liste complète avec hiérarchie
        comments_tree = [build_tree(parent) for parent in parents]
        logger.info(f"Loaded {len(comments_tree)} top-level comments for event_id={event_id}")
        return comments_tree
