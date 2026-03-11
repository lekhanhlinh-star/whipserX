from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.db import get_db, User
from core.auth import hash_password, create_jwt_token
from core.auth import get_current_user

router = APIRouter()

class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

@router.post("/register/")
async def register_user(user: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists.")
    user_id = str(uuid4())
    db_user = User(id=user_id, username=user.username, password_hash=hash_password(user.password))
    db.add(db_user)
    db.commit()
    return {"message": "User registered successfully.", "user_id": user_id}

@router.post("/login/")
async def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or db_user.password_hash != hash_password(user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_jwt_token(db_user.id)
    return {"token": token, "user_id": db_user.id}


@router.get("/me/")
async def get_user_info(current_user: User = Depends(get_current_user)):
    return {"user_id": current_user.id, "username": current_user.username}
