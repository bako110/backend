from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Conversation, conversation_participants

async def get_user_conversations(db: AsyncSession, user_id: int):
    # Récupérer toutes les conversations où user_id est participant
    query = (
        select(Conversation)
        .join(conversation_participants, Conversation.id == conversation_participants.c.conversation_id)
        .where(conversation_participants.c.user_id == user_id)
    )
    result = await db.execute(query)
    conversations = result.scalars().unique().all()
    return conversations

async def create_conversation(db: AsyncSession, participant_ids: list[int]) -> Conversation:
    conv = Conversation()
    db.add(conv)
    await db.flush()  # flush pour avoir l'id de la conversation

    # Insertion des participants dans la table pivot
    for user_id in participant_ids:
        await db.execute(
            conversation_participants.insert().values(conversation_id=conv.id, user_id=user_id)
        )
    await db.commit()
    await db.refresh(conv)
    return conv
