from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import users
from app.security import (
    get_or_create_csrf_token, verify_csrf_token,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "user_login.html", {
        "csrf_token": get_or_create_csrf_token(request), "error": None,
    })


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...),
                 csrf_token: str = Form(...)):
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    user = users.authenticate(settings.db_path, email, password)
    if not user:
        return templates.TemplateResponse(request, "user_login.html", {
            "csrf_token": get_or_create_csrf_token(request),
            "error": "E-mail ou senha inválidos.",
        })
    request.session["user_id"] = user["id"]
    request.session["user_name"] = user["name"]
    return RedirectResponse("/app/ocorrencias", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    request.session.pop("user_name", None)
    return RedirectResponse("/login", status_code=303)



