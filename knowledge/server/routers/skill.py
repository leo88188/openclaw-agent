from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from ..database import get_db
from ..models.skill import Skill, SkillFavorite

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    description: Optional[str] = None
    prompt_template: str
    params: Optional[dict] = None
    category: Optional[str] = None
    is_public: int = 1
    created_by: Optional[str] = None


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_template: Optional[str] = None
    params: Optional[dict] = None
    category: Optional[str] = None
    is_public: Optional[int] = None


@router.get("")
async def list_skills(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Skill).where(Skill.is_deleted == 0)
    if category:
        q = q.where(Skill.category == category)
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    items = (await db.execute(q.order_by(Skill.created_at.desc()).offset((page - 1) * size).limit(size))).scalars().all()
    return {"total": total, "items": [_to_dict(i) for i in items]}


@router.post("")
async def create_skill(body: SkillCreate, db: AsyncSession = Depends(get_db)):
    item = Skill(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _to_dict(item)


@router.get("/{skill_id}")
async def get_skill(skill_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(Skill, skill_id)
    if not item or item.is_deleted:
        raise HTTPException(404, "Not found")
    return _to_dict(item)


@router.put("/{skill_id}")
async def update_skill(skill_id: int, body: SkillUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(Skill, skill_id)
    if not item or item.is_deleted:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return _to_dict(item)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(Skill, skill_id)
    if not item:
        raise HTTPException(404, "Not found")
    item.is_deleted = 1
    await db.commit()
    return {"ok": True}


@router.post("/{skill_id}/favorite")
async def toggle_favorite(skill_id: int, user_name: str = "default", db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(
        select(SkillFavorite).where(SkillFavorite.skill_id == skill_id, SkillFavorite.user_name == user_name)
    )).scalar_one_or_none()
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if existing:
        await db.delete(existing)
        skill.favorite_count = max(0, (skill.favorite_count or 0) - 1)
        action = "unfavorited"
    else:
        db.add(SkillFavorite(skill_id=skill_id, user_name=user_name))
        skill.favorite_count = (skill.favorite_count or 0) + 1
        action = "favorited"
    await db.commit()
    return {"ok": True, "action": action}


def _to_dict(item: Skill):
    return {
        "id": item.id, "name": item.name, "description": item.description,
        "prompt_template": item.prompt_template, "params": item.params,
        "category": item.category, "is_public": item.is_public,
        "created_by": item.created_by, "favorite_count": item.favorite_count,
        "use_count": item.use_count,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
