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


class RoleUpdate(BaseModel):
    role: str


@router.get("")
async def list_teams(db: AsyncSession = Depends(get_db)):
    items = (await db.execute(select(Team).order_by(Team.created_at.desc()))).scalars().all()
    return {"items": [
        {"id": t.id, "name": t.name, "description": t.description,
         "created_by": t.created_by, "created_at": t.created_at.isoformat() if t.created_at else None}
        for t in items
    ]}


@router.post("")
async def create_team(body: TeamCreate, db: AsyncSession = Depends(get_db)):
    team = Team(**body.model_dump())
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return {"id": team.id, "name": team.name, "description": team.description,
            "created_by": team.created_by, "created_at": team.created_at.isoformat() if team.created_at else None}


@router.get("/{team_id}/members")
async def list_members(team_id: int, db: AsyncSession = Depends(get_db)):
    members = (await db.execute(select(TeamMember).where(TeamMember.team_id == team_id))).scalars().all()
    return {"items": [
        {"id": m.id, "team_id": m.team_id, "user_name": m.user_name, "role": m.role,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in members
    ]}


@router.post("/{team_id}/members")
async def add_member(team_id: int, body: MemberAdd, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_name == body.user_name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, detail={"code": "CONFLICT", "message": "该成员已存在"})
    db.add(TeamMember(team_id=team_id, user_name=body.user_name, role=body.role))
    await db.commit()
    return {"ok": True}


@router.put("/{team_id}/members/{uid}")
async def update_member_role(team_id: int, uid: str, body: RoleUpdate, db: AsyncSession = Depends(get_db)):
    member = (await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_name == uid)
    )).scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Member not found")
    member.role = body.role
    await db.commit()
    await db.refresh(member)
    return {"id": member.id, "team_id": member.team_id, "user_name": member.user_name, "role": member.role,
            "created_at": member.created_at.isoformat() if member.created_at else None}


@router.delete("/{team_id}/members/{uid}")
async def remove_member(team_id: int, uid: str, db: AsyncSession = Depends(get_db)):
    member = (await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_name == uid)
    )).scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Member not found")
    await db.delete(member)
    await db.commit()
    return {"ok": True}
