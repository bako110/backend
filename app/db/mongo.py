from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

# Client MongoDB asynchrone
client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.MONGO_DB]

# Collections
profiles_collection = db["profiles"]
friendships_collection = db["friendships"]
events_collection = db["events"]
posts_collection = db["posts"]
notifications_collection = db["notifications"]
wishlists_collection = db["wishlists"]
media_collection = db["media"]
reminders_collection = db["reminders"]
