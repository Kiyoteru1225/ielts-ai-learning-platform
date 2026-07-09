from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import auth, writing

app = FastAPI(title="IELTS AI Learning Platform", version="0.1.0")

app.include_router(writing.router)
app.include_router(auth.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    return {"message": "IELTS AI Learning Platform", "version": "0.1.0"}
