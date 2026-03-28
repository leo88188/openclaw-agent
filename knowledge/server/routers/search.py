from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from ..database import get_db
from ..models.knowledge import KnowledgeItem
from ..models.skill import Skill
from ..models.metadata import DbMetadata

router = APIRouter(prefix="/api/v1/search", tags=["search"])

TIME_RANGE_MAP = {"7d": 7, "30d": 30, "90d": 90}


class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    source_type: Optional[str] = None  # knowledge / metadata / skill
    time_range: Optional[str] = None   # all / 7d / 30d / 90d
    limit: int = 20


def _score(query: str, title: str, content: str) -> float:
    """简易相关度评分：标题命中权重高于内容"""
    q = query.lower()
    t, c = (title or "").lower(), (content or "").lower()
    s = 0.0
    if q in t:
        s += 60
    if q in c:
        s += 30
    # 额外：完全匹配标题加分
    if q == t:
        s += 10
    return min(s, 100)


@router.post("")
async def search(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    results = []
    cutoff = None
    if body.time_range and body.time_range in TIME_RANGE_MAP:
        cutoff = datetime.now() - timedelta(days=TIME_RANGE_MAP[body.time_range])

    # --- 搜索知识条目 ---
    if body.source_type in (None, "knowledge"):
        q = select(KnowledgeItem).where(
            KnowledgeItem.is_deleted == 0,
            or_(KnowledgeItem.title.contains(body.query), KnowledgeItem.content.contains(body.query)),
        )
        if body.category:
            q = q.where(KnowledgeItem.category == body.category)
        if cutoff:
            q = q.where(KnowledgeItem.created_at >= cutoff)
        for i in (await db.execute(q.limit(body.limit))).scalars().all():
            results.append({
                "id": i.id, "title": i.title, "content": (i.content or "")[:200],
                "category": i.category, "tags": i.tags, "source_type": "knowledge",
                "score": _score(body.query, i.title, i.content or ""),
                "created_at": i.created_at.isoformat() if i.created_at else None,
            })

    # --- 搜索元数据 ---
    if body.source_type in (None, "metadata"):
        mq = select(DbMetadata).where(
            or_(
                DbMetadata.table_name.contains(body.query),
                DbMetadata.column_name.contains(body.query),
                DbMetadata.column_comment.contains(body.query),
                DbMetadata.table_comment.contains(body.query),
            )
        )
        if cutoff:
            mq = mq.where(DbMetadata.created_at >= cutoff)
        for m in (await db.execute(mq.limit(body.limit))).scalars().all():
            title = f"{m.table_name}.{m.column_name}" if m.column_name else m.table_name
            content = m.column_comment or m.table_comment or ""
            results.append({
                "id": m.id, "title": title, "content": content[:200],
                "category": "元数据", "tags": None, "source_type": "metadata",
                "score": _score(body.query, title, content),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })

    # --- 搜索 Skill ---
    if body.source_type in (None, "skill"):
        sq = select(Skill).where(
            Skill.is_deleted == 0,
            or_(Skill.name.contains(body.query), Skill.description.contains(body.query)),
        )
        if body.category:
            sq = sq.where(Skill.category == body.category)
        if cutoff:
            sq = sq.where(Skill.created_at >= cutoff)
        for s in (await db.execute(sq.limit(body.limit))).scalars().all():
            results.append({
                "id": s.id, "title": s.name, "content": (s.description or "")[:200],
                "category": s.category, "tags": None, "source_type": "skill",
                "score": _score(body.query, s.name, s.description or ""),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })

    # 按 score 降序排序，截取 limit
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:body.limit]
    return {"total": len(results), "items": results}
