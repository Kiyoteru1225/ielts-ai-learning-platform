from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import writing

app = FastAPI(title="IELTS AI Learning Platform", version="0.1.0")

app.include_router(writing.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return {"message": "IELTS AI Learning Platform", "version": "0.1.0"}
