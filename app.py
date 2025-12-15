from starlette import status
from fastapi import HTTPException

from fastapi import FastAPI, Depends
from database import engine, Base
from typing import Annotated
import auth
import client
import models
from auth import get_user
from factory import db_dependency

app = FastAPI()
app.include_router(auth.router)
app.include_router(client.router)

Base.metadata.create_all(bind=engine)

user_dependency = Annotated[dict, Depends(get_user)]


@app.get("/", status_code=status.HTTP_200_OK)
async def user(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail='Testing')
    return {"User": user}

