from sqlalchemy import Column, BigInteger, String, Text, DateTime, Enum, func
from ..database import Base


class Team(Base):
    __tablename__ = "teams"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_by = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())


class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    team_id = Column(BigInteger, nullable=False)
    user_name = Column(String(100), nullable=False)
    role = Column(Enum("admin", "editor", "viewer"), default="viewer")
    created_at = Column(DateTime, server_default=func.now())
