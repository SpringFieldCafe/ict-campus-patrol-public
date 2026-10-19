"""Authentication adapted from the FastAPI full-stack template (MIT)."""

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import User, UserCreate

DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def create_user(*, session: Session, user_create: UserCreate) -> User:
    user = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(session=session, email=email)
    if not user:
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_hash = verify_password(password, user.hashed_password)
    if not verified:
        return None
    if updated_hash:
        user.hashed_password = updated_hash
        session.add(user)
        session.commit()
        session.refresh(user)
    return user
