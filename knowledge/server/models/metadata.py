from sqlalchemy import Column, BigInteger, String, Text, DateTime, func
from ..database import Base


class DbMetadata(Base):
    __tablename__ = "db_metadata"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    db_name = Column(String(100), nullable=False)
    table_name = Column(String(100), nullable=False, index=True)
    column_name = Column(String(100))
    column_type = Column(String(100))
    column_comment = Column(Text)
    table_comment = Column(Text)
    vector_id = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
