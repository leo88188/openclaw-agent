from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..database import get_db
from ..models.knowledge import KnowledgeItem
from ..models.skill import Skill
from ..models.metadata import DbMetadata

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    knowledge_count = await db.scalar(select(func.count(KnowledgeItem.id)).where(KnowledgeItem.is_deleted == 0))
    skill_count = await db.scalar(select(func.count(Skill.id)).where(Skill.is_deleted == 0))
    metadata_count = await db.scalar(select(func.count(func.distinct(DbMetadata.table_name))))
    return {
        "knowledge_count": knowledge_count or 0,
        "skill_count": skill_count or 0,
        "table_count": metadata_count or 0,
    }
