from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models.metadata import DbMetadata

router = APIRouter(prefix="/api/v1/metadata", tags=["metadata"])


class MetadataImport(BaseModel):
    db_name: str
    connection_string: Optional[str] = None


@router.get("/tables")
async def list_tables(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(DbMetadata.db_name, DbMetadata.table_name, DbMetadata.table_comment)
        .distinct()
        .order_by(DbMetadata.table_name)
    )).all()
    return {"items": [{"db_name": r[0], "table_name": r[1], "table_comment": r[2]} for r in rows]}


@router.get("/tables/{table_name}")
async def get_table(table_name: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(DbMetadata).where(DbMetadata.table_name == table_name)
    )).scalars().all()
    if not rows:
        raise HTTPException(404, "Table not found")
    return {
        "table_name": table_name,
        "table_comment": rows[0].table_comment,
        "columns": [
            {"name": r.column_name, "type": r.column_type, "comment": r.column_comment}
            for r in rows if r.column_name
        ],
    }


@router.post("/import")
async def import_metadata(body: MetadataImport, db: AsyncSession = Depends(get_db)):
    """从 information_schema 导入当前数据库的表结构元数据"""
    rows = (await db.execute(text(
        "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT, TABLE_COMMENT "
        "FROM information_schema.COLUMNS c "
        "JOIN information_schema.TABLES t USING(TABLE_SCHEMA, TABLE_NAME) "
        "WHERE c.TABLE_SCHEMA = :db_name"
    ), {"db_name": body.db_name})).all()
    count = 0
    for r in rows:
        db.add(DbMetadata(
            db_name=body.db_name, table_name=r[0], column_name=r[1],
            column_type=r[2], column_comment=r[3], table_comment=r[4],
        ))
        count += 1
    await db.commit()
    return {"ok": True, "imported": count}
