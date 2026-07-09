import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
)
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
    )


@router.post("/login")
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not bcrypt.checkpw(
        password.encode("utf-8"), user.password_hash.encode("utf-8")
    ):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "用户名或密码错误"},
            status_code=401,
        )

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    response = RedirectResponse(url="/writing/", status_code=303)
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax",
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
    )


@router.post("/register")
async def register(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "两次输入的密码不一致"},
            status_code=400,
        )

    if len(username) < 2:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "用户名至少需要 2 个字符"},
            status_code=400,
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "密码至少需要 6 个字符"},
            status_code=400,
        )

    existing = await db.execute(
        select(User).where((User.username == username) | (User.email == email))
    )
    if existing.scalar_one_or_none() is not None:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "用户名或邮箱已被注册"},
            status_code=400,
        )

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    user = User(username=username, email=email, password_hash=password_hash)
    db.add(user)
    await db.commit()

    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="token")
    return response
