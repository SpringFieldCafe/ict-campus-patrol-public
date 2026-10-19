"""Login routes adapted from the FastAPI full-stack template (MIT)."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.core import security
from app.core.config import settings
from app.models import Token, UserPublic

router = APIRouter(tags=["login"])


@router.post("/login/access-token", response_model=Token)
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    user = crud.authenticate(session=session, email=form_data.username, password=form_data.password)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
    )


@router.get("/users/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser):
    return current_user
