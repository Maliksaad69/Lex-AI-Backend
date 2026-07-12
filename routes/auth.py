from pathlib import Path
import sys
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select

from db.session import get_session
from db.models.user import User
from db.models.case import Case

from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv
from sqlalchemy import func

load_dotenv()

import os
from models.user import Token, UserRegister

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


router = APIRouter()


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


model = None
classes = None


@router.get("/health")
def health():
    return {"status": "ok"}


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str):
    return pwd_context.verify(plain, hashed)


def create_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
):
    """Decode JWT and return the authenticated user's database ID."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user.id


@router.get("/users/me")
def get_me(
    session: Session = Depends(get_session),
    current_user_id: int = Depends(get_current_user),
):
    """Return the currently authenticated user's profile."""
    user = session.get(User, current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/")
def health_check():
    return {"status": "ok", "message": "Backend API is running"}

    return list(metrics.find({}, {"_id": 0}).sort("epoch", 1))


@router.post("/register")
def register(user: UserRegister, session: Session = Depends(get_session)):
    existing_user = session.exec(
        select(User).where(User.username == user.username)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    existing_email = session.exec(select(User).where(User.email == user.email)).first()

    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return {"message": "Account created successfully"}


@router.post("/token", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == form_data.username)).first()

    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    if not verify_password(
        form_data.password,
        user.password_hash,
    ):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_token(
        {
            "sub": user.username,
            "user_id": user.id,
        },
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/debug/users")
def debug_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()


@router.get("/dashboard/stats")
def dashboard_stats(
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    """Return aggregate stats for the authenticated user's dashboard."""
    case_count = session.exec(select(func.count()).where(Case.user_id == user_id)).one()

    # Sum document_count across all user's cases
    total_docs = session.exec(
        select(func.coalesce(func.sum(Case.document_count), 0)).where(
            Case.user_id == user_id
        )
    ).one()

    return {
        "totalCases": case_count,
        "totalDocuments": total_docs,
        "totalAnalyses": case_count,  # placeholder — one analysis per case for now
        "totalReports": 0,  # placeholder — reports not built yet
    }
