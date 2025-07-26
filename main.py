from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from starlette.status import HTTP_303_SEE_OTHER
import models
from pathlib import Path
from fastapi.staticfiles import StaticFiles

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
        email = form.get("email")

        if not name or not email:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "A név és email megadása kötelező."
            })

        user = models.User(name=name, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)

        return RedirectResponse(url="/register", status_code=HTTP_303_SEE_OTHER)

    return templates.TemplateResponse("register.html", {"request": request})
