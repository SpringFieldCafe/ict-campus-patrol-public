"""Local SQLite storage; sessions/bootstrap adapted from the upstream template."""

from sqlmodel import Session, SQLModel, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    settings.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if not session.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first():
            crud.create_user(
                session=session,
                user_create=UserCreate(
                    email=settings.FIRST_SUPERUSER,
                    password=settings.FIRST_SUPERUSER_PASSWORD,
                    is_superuser=True,
                ),
            )
        if settings.REMOTE_ENABLED and settings.REMOTE_DEMO_PASSWORD:
            if settings.REMOTE_DEMO_USER == settings.FIRST_SUPERUSER:
                raise ValueError("Judge account must be separate from the administrator")
            existing = session.exec(
                select(User).where(User.email == settings.REMOTE_DEMO_USER)
            ).first()
            if existing and existing.is_superuser:
                raise ValueError("Judge demo account cannot be an administrator")
            if not existing:
                crud.create_user(
                    session=session,
                    user_create=UserCreate(
                        email=settings.REMOTE_DEMO_USER,
                        password=settings.REMOTE_DEMO_PASSWORD.get_secret_value(),
                        full_name="评委演示",
                        is_superuser=False,
                    ),
                )
