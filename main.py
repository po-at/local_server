from urllib import response
from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from starlette.status import HTTP_303_SEE_OTHER
from pathlib import Path
from passlib.hash import bcrypt
import models
from itsdangerous import URLSafeSerializer
import os
import httpx
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
serializer = URLSafeSerializer(SECRET_KEY)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def require_login(request: Request, db: Session):
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        return None

    try:
        username = serializer.loads(session_cookie)
    except Exception:
        return None

    user = db.query(models.User).filter_by(name=username).first()
    return user

app.mount("/static", StaticFiles(directory="static"), name="static")

models.Base.metadata.create_all(bind=engine)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user
    })

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request):
    session_cookie = request.cookies.get("session")
    if session_cookie:
        try:
            username = serializer.loads(session_cookie)
            return username
        except Exception:
            return None
    return None


@app.api_route("/register", methods=["GET", "POST"])
async def register(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = await request.form()
        name = form.get("name")
        password = form.get("password")

        if not name or not password:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "A felhasználónév és jelszó megadása kötelező."
            })

        existing_user = db.query(models.User).filter(models.User.name == name).first()
        if existing_user:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "Ez a felhasználónév már foglalt."
            })

        # bcrypt warning: old version fixed
        hashed_pw = bcrypt.hash(password)
        user = models.User(name=name, hashed_password=hashed_pw)
        db.add(user)
        db.commit()

        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)

    return templates.TemplateResponse("register.html", {"request": request})

@app.api_route("/login", methods=["GET", "POST"])
async def login(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = await request.form()
        name = form.get("name")
        password = form.get("password")

        if not name or not password:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "A felhasználónév és a jelszó megadása kötelező."
            })

        user = db.query(models.User).filter(models.User.name == name).first()

        if not user or not bcrypt.verify(password, user.hashed_password):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Hibás felhasználónév vagy jelszó."
            })

        response = RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="session",
            value=serializer.dumps(user.name),
            httponly=True,
            max_age=None,
            expires=None
        )
        return response

    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
    response.delete_cookie("session")
    return response

@app.api_route("/notes", methods=["GET", "POST"])
async def notes(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)

    if request.method == "POST":
        form = await request.form()
        content = form.get("content")
        if content:
            new_note = models.Note(content=content, user_id=user.id)
            db.add(new_note)
            db.commit()

    user_notes = db.query(models.Note).filter_by(user_id=user.id).all()

    return templates.TemplateResponse("notes.html", {
        "request": request,
        "notes": user_notes,
        "user": user.name
    })

@app.post("/notes/delete/{note_id}")
def delete_note(note_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)

    note = db.query(models.Note).filter_by(id=note_id, user_id=user.id).first()

    if note:
        db.delete(note)
        db.commit()

    return RedirectResponse(url="/notes", status_code=HTTP_303_SEE_OTHER)

@app.get("/api/openmeteo")
async def get_weather():
    latitude = 47.3849
    longitude = 16.5365

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        return JSONResponse(status_code=500, content={"error": "API hiba"})

    data = response.json()
    current = data.get("current", {})

    return {
        "city": "Bük",
        "temp": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
    }

@app.get("/weather", response_class=HTMLResponse)
async def weather_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("weather.html", {"request": request, "user": user})

@app.api_route("/weather", methods=["GET", "POST"])
async def weather_page_rainfalls(request: Request, db: Session = Depends(get_db)):
    user_name = get_current_user(request)
    if not user_name:
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)

    user = db.query(models.User).filter(models.User.name == user_name).first()
    if user is None:
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)

    if request.method == "POST":
        form = await request.form()
        date_str = form.get("date")
        amount_str = form.get("amount")

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            amount = float(amount_str)
        except (ValueError, TypeError):
            return templates.TemplateResponse("weather.html", {
                "request": request,
                "user": user_name,
                "error": "Érvénytelen dátum vagy csapadék érték.",
            })

        # Ellenőrizzük, hogy van-e már adat erre a dátumra (ugyanannál a felhasználónál)
        existing = db.query(models.Rainfall).filter(
            models.Rainfall.user_id == user.id,
            models.Rainfall.date == date_obj
        ).first()

        if existing:
            existing.amount = amount  # felülírjuk
        else:
            new_rainfall = models.Rainfall(date=date_obj, amount=amount, user_id=user.id)
            db.add(new_rainfall)

        db.commit()

    # Lekérjük az adott év (most az aktuális év) csapadékösszegét
    current_year = datetime.now().year
    total_rainfall = db.query(models.Rainfall).filter(
        models.Rainfall.user_id == user.id,
        models.Rainfall.date.between(f"{current_year}-01-01", f"{current_year}-12-31")
    ).with_entities(func.sum(models.Rainfall.amount)).scalar() or 0.0

    return templates.TemplateResponse("weather.html", {
        "request": request,
        "user": user_name,
        "total_rainfall": total_rainfall,
    })

