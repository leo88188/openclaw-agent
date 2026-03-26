from sqlalchemy import Column, BigInteger, String, Text, JSON, DateTime, SmallInteger, func
from ..database import Base


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), index=True)
    tags = Column(JSON)
    team_id = Column(BigInteger, index=True)
    created_by = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(SmallInteger, default=0)
    vector_id = Column(String(100))
