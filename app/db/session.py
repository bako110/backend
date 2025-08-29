# app/db/session.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

# URL PostgreSQL Aiven format asyncpg
POSTGRES_URL = os.getenv(
    "POSTGRES_URL"
)  # "postgresql+asyncpg://avnadmin:password@host:port/dbname?sslmode=require"

# Base pour les modèles
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
