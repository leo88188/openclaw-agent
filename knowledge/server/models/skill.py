from sqlalchemy import Column, BigInteger, String, Text, JSON, DateTime, SmallInteger, Integer, func
from ..database import Base


class Skill(Base):
    __tablename__ = "skills"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    prompt_template = Column(Text, nullable=False)
    params = Column(JSON)
    category = Column(String(100), index=True)
    is_public = Column(SmallInteger, default=1)
    created_by = Column(String(100))
    favorite_count = Column(Integer, default=0)
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(SmallInteger, default=0)


class SkillFavorite(Base):
    __tablename__ = "skill_favorites"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    skill_id = Column(BigInteger, nullable=False)
    user_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
