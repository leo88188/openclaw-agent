from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models.team import Team, TeamMember

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    created_by: Optional[str] = None


class MemberAdd(BaseModel):
    user_name: str
    role: str = "viewer"


@router.get("")
async def list_teams(db: AsyncSession = Depends(get_db)):
    items = (await db.execute(select(Team).order_by(Team.created_at.desc()))).scalars().all()
    return {"items": [{"id": t.id, "name": t.name, "description": t.description, "created_by": t.created_by} for t in items]}


@router.post("")
async def create_team(body: TeamCreate, db: AsyncSession = Depends(get_db)):
    team = Team(**body.model_dump())
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return {"id": team.id, "name": team.name}


@router.get("/{team_id}/members")
async def list_members(team_id: int, db: AsyncSession = Depends(get_db)):
    members = (await db.execute(select(TeamMember).where(TeamMember.team_id == team_id))).scalars().all()
    return {"items": [{"id": m.id, "user_name": m.user_name, "role": m.role} for m in members]}


@router.post("/{team_id}/members")
async def add_member(team_id: int, body: MemberAdd, db: AsyncSession = Depends(get_db)):
    db.add(TeamMember(team_id=team_id, user_name=body.user_name, role=body.role))
    await db.commit()
    return {"ok": True}
