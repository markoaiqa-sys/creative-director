import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests

from app.core.config import get_settings
from app.services.database import ChatDatabase

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("auth")


class GoogleAuthRequest(BaseModel):
    credential: str


class EmailAuthRequest(BaseModel):
    email: str
    password: str | None = None


class AllowedEmailRequest(BaseModel):
    email: str


@router.post("/google")
async def auth_google(request: GoogleAuthRequest):
    settings = get_settings()
    client_id = settings.google_client_id

    if not client_id:
        log.error("Google authentication failed: GOOGLE_CLIENT_ID is not configured in environment.")
        raise HTTPException(
            status_code=400,
            detail="Google Client ID is not configured on the backend server."
        )

    try:
        # Verify the Google ID Token
        idinfo = id_token.verify_oauth2_token(
            request.credential,
            requests.Request(),
            client_id
        )
    except ValueError as e:
        log.warning(f"Google token verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Google token verification failed: {e}"
        )

    email = idinfo.get("email")
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Google credential does not contain an email address."
        )

    email_lower = email.lower().strip()
    chat_db = ChatDatabase(settings)

    if not chat_db.is_email_allowed(email_lower):
        log.warning(f"Access denied: Email '{email_lower}' is not in allowed list.")
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Email '{email}' is not registered in the system."
        )

    log.info(f"Successful Google login for user: {email_lower}")
    return {
        "email": email_lower,
        "name": idinfo.get("name", email_lower.split("@")[0]),
        "picture": idinfo.get("picture"),
    }


@router.post("/email-login")
async def email_login(request: EmailAuthRequest):
    settings = get_settings()
    email_lower = request.email.lower().strip()

    chat_db = ChatDatabase(settings)
    if not chat_db.is_email_allowed(email_lower):
        log.warning(f"Access denied: Email login attempt for '{email_lower}' rejected.")
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Email '{request.email}' is not registered in the system."
        )

    log.info(f"Successful email login check for user: {email_lower}")
    return {
        "email": email_lower,
        "name": email_lower.split("@")[0],
        "picture": None,
    }


# Admin / Utility endpoints for allowed emails list
@router.post("/allowed-emails")
async def add_allowed_email(request: AllowedEmailRequest):
    settings = get_settings()
    email_lower = request.email.lower().strip()
    chat_db = ChatDatabase(settings)

    with chat_db._cursor() as cur:
        if cur is None:
            raise HTTPException(status_code=500, detail="Database connection failed.")
        cur.execute(
            "INSERT INTO allowed_users (email) VALUES (%s) ON CONFLICT (email) DO NOTHING;",
            (email_lower,)
        )
    log.info(f"Added '{email_lower}' to allowed users list.")
    return {"status": "success", "message": f"Email '{email_lower}' added to allowed list."}


@router.delete("/allowed-emails/{email}")
async def delete_allowed_email(email: str):
    settings = get_settings()
    email_lower = email.lower().strip()
    chat_db = ChatDatabase(settings)

    with chat_db._cursor() as cur:
        if cur is None:
            raise HTTPException(status_code=500, detail="Database connection failed.")
        cur.execute("DELETE FROM allowed_users WHERE email = %s;", (email_lower,))
    log.info(f"Removed '{email_lower}' from allowed users list.")
    return {"status": "success", "message": f"Email '{email_lower}' removed from allowed list."}


@router.get("/allowed-emails")
async def get_allowed_emails():
    settings = get_settings()
    chat_db = ChatDatabase(settings)

    with chat_db._cursor() as cur:
        if cur is None:
            raise HTTPException(status_code=500, detail="Database connection failed.")
        cur.execute("SELECT email, created_at FROM allowed_users ORDER BY created_at DESC;")
        rows = cur.fetchall()
        return [{"email": row[0], "created_at": row[1].isoformat()} for row in rows]
