from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from ..database import get_db
from ..models.knowledge import KnowledgeItem

router = APIRouter(prefix="/api/v1/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    category: str | None = None
    limit: int = 20


@router.post("")
async def search(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    """简易关键词搜索（向量搜索需集成嵌入模型后扩展）"""
    q = select(KnowledgeItem).where(
        KnowledgeItem.is_deleted == 0,
        KnowledgeItem.title.contains(body.query) | KnowledgeItem.content.contains(body.query),
    )
    if body.category:
        q = q.where(KnowledgeItem.category == body.category)
    items = (await db.execute(q.limit(body.limit))).scalars().all()
    return {
        "total": len(items),
        "items": [
            {"id": i.id, "title": i.title, "content": i.content[:200],
             "category": i.category, "tags": i.tags,
             "created_at": i.created_at.isoformat() if i.created_at else None}
            for i in items
        ],
    }
