from urllib import response
from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from starlette.status import HTTP_303_SEE_OTHER
from pathlib import Path
from passlib.hash import bcrypt
import models
from itsdangerous import URLSafeSerializer
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
serializer = URLSafeSerializer(SECRET_KEY)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

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
        response.set_cookie(key="session", value=serializer.dumps(user.name), httponly=True)
        return response

    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
    response.delete_cookie("session")
    return response
