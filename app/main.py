from .db import engine
from .models import Base
from fastapi import FastAPI
from app.api import jobs

app = FastAPI()

app.include_router(jobs.router, prefix="/api")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def on_startup():
    await init_db()