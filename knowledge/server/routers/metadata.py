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


@router.get("/tables")
async def list_tables(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            DbMetadata.table_name,
            func.max(DbMetadata.table_comment).label("table_comment"),
            func.count(DbMetadata.column_name).label("column_count"),
        ).group_by(DbMetadata.table_name).order_by(DbMetadata.table_name)
    )).all()
    return {"tables": [
        {"table_name": r[0], "table_comment": r[1], "column_count": r[2]}
        for r in rows
    ]}


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
            {"column_name": r.column_name, "column_type": r.column_type, "column_comment": r.column_comment}
            for r in rows if r.column_name
        ],
    }


@router.post("/import")
async def import_metadata(body: MetadataImport, db: AsyncSession = Depends(get_db)):
    """从 information_schema 导入，增量更新（先删旧数据再插入）"""
    # 删除该 db 的旧元数据
    old = (await db.execute(select(DbMetadata).where(DbMetadata.db_name == body.db_name))).scalars().all()
    for o in old:
        await db.delete(o)

    rows = (await db.execute(text(
        "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT, TABLE_COMMENT "
        "FROM information_schema.COLUMNS c "
        "JOIN information_schema.TABLES t USING(TABLE_SCHEMA, TABLE_NAME) "
        "WHERE c.TABLE_SCHEMA = :db_name"
    ), {"db_name": body.db_name})).all()

    tables = set()
    for r in rows:
        tables.add(r[0])
        db.add(DbMetadata(
            db_name=body.db_name, table_name=r[0], column_name=r[1],
            column_type=r[2], column_comment=r[3], table_comment=r[4],
        ))
    await db.commit()
    return {"imported_tables": len(tables), "imported_columns": len(rows)}
