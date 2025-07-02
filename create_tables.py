import asyncio
from app.db.session import Base, engine

# IMPORTER TOUS LES MODULES DE MODÈLES pour enregistrer toutes les tables dans metadata
import app.auth.models
import app.events.models

async def create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Toutes les tables ont été créées")

if __name__ == "__main__":
    asyncio.run(create_all())
