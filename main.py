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


app = FastAPI()
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

models.Base.metadata.create_all(bind=engine)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
        email = form.get("email")
        password = form.get("password")
        
        if not email:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Az email megadása kötelező."
            })

        return RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)

    return templates.TemplateResponse("login.html", {"request": request})
