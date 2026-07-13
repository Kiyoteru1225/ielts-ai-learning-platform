import logging
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from starlette.templating import _TemplateResponse

from app.database import Base, async_session, engine
from app.routers import auth, listening, reading, speaking, vocabulary, writing

app = FastAPI(title="IELTS AI Learning Platform", version="0.1.0")

app.include_router(writing.router)
app.include_router(auth.router)
app.include_router(speaking.router)
app.include_router(listening.router)
app.include_router(reading.router)
app.include_router(vocabulary.router)
app.mount("/static", StaticFiles(directory="static"), name="static")

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "templates"
)
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))


@app.on_event("startup")
async def startup() -> None:
    from app.services.vocabulary_service import seed_vocabulary

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        count = await seed_vocabulary(db)
        if count > 0:
            logging.getLogger("uvicorn").info(f"Seeded {count} vocabulary words")


@app.get("/")
async def root(request: Request):
    template = _jinja_env.get_template("home.html")
    return _TemplateResponse(template, {"request": request})
