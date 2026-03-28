from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, String
from pydantic import BaseModel
from typing import Optional, List
from ..database import get_db
from ..models.knowledge import KnowledgeItem

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class KnowledgeCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    team_id: Optional[int] = None
    created_by: Optional[str] = None


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


@router.get("")
async def list_knowledge(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    tags: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(KnowledgeItem).where(KnowledgeItem.is_deleted == 0)
    if category:
        q = q.where(KnowledgeItem.category == category)
    if keyword:
        q = q.where(KnowledgeItem.title.contains(keyword) | KnowledgeItem.content.contains(keyword))
    if tags:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                q = q.where(cast(KnowledgeItem.tags, String).contains(tag))
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    items = (await db.execute(
        q.order_by(KnowledgeItem.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_to_dict(i) for i in items]}


@router.post("")
async def create_knowledge(body: KnowledgeCreate, db: AsyncSession = Depends(get_db)):
    item = KnowledgeItem(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _to_dict(item)


@router.get("/{item_id}")
async def get_knowledge(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(KnowledgeItem, item_id)
    if not item or item.is_deleted:
        raise HTTPException(404, "Not found")
    return _to_dict(item)


@router.put("/{item_id}")
async def update_knowledge(item_id: int, body: KnowledgeUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(KnowledgeItem, item_id)
    if not item or item.is_deleted:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return _to_dict(item)


@router.delete("/{item_id}")
async def delete_knowledge(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(KnowledgeItem, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    item.is_deleted = 1
    await db.commit()
    return {"ok": True}


def _to_dict(item: KnowledgeItem):
    return {
        "id": item.id, "title": item.title, "content": item.content,
        "category": item.category, "tags": item.tags, "team_id": item.team_id,
        "created_by": item.created_by,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
