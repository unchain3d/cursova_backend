from datetime import timedelta, datetime, timezone
from typing import Annotated
from starlette import status
from models import Users, UserRole
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
import re
from factory import db_dependency


router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

SECRET_KEY = 'idh3oihoidhoi3jnidjoi3hoi4hoi3hi4oi'
ALGORITHM = 'HS256'

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/login')


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(db: db_dependency,
                      register_request: RegisterRequest):
    username = register_request.username
    password = register_request.password

    if len(username) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ім'я користувача має містити мінімум 8 символів"
        )

    if len(password) < 8 or not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль має містити мінімум 8 символів та хоча б одну цифру"
        )

    register_model = Users(
        username=register_request.username,
        email=register_request.email,
        hashed_password=bcrypt_context.hash(register_request.password),
        role=UserRole.CLIENT.value
    )

    db.add(register_model)
    db.commit()
    db.refresh(register_model)


@router.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                 db: db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user.')
    token = create_token(user.username, user.id, user.role, timedelta(minutes=45))

    return {'access_token': token, 'token_type': 'bearer', 'role': user.role}


def authenticate_user(username:str, password: str, db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user


def create_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {'sub': username, 'id': user_id, 'role': role}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        role: str = payload.get('role')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
        return {'username': username, 'id': user_id, 'role': role}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user.')
