from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
from .database import init_db, engine
from .redis_client import redis_client
from .routers import knowledge, skill, metadata, search, team, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Knowledge API", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge.router)
app.include_router(skill.router)
app.include_router(metadata.router)
app.include_router(search.router)
app.include_router(team.router)
app.include_router(dashboard.router)


@app.get("/api/v1/health", tags=["dashboard"])
async def health_check():
    mysql_ok = False
    redis_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        mysql_ok = True
    except Exception:
        pass
    try:
        redis_ok = await redis_client.ping()
    except Exception:
        pass
    status = "healthy" if (mysql_ok and redis_ok) else ("degraded" if (mysql_ok or redis_ok) else "unhealthy")
    return {"status": status, "mysql": mysql_ok, "redis": redis_ok, "version": "1.1.0"}


static_dir = Path(__file__).parent.parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
