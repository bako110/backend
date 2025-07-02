from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL")  # Exemple: "postgresql+asyncpg://users:6277bako@localhost/Annivdb"

Base = declarative_base()

# Créer le moteur async
engine = create_async_engine(POSTGRES_URL, echo=True)

# Session async
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dépendance FastAPI pour obtenir la session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


