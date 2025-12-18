from datetime import datetime, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_user
from dependencies import db_dependency
from models import (
    Users,
    Trainers,
    Subscriptions,
    SubscriptionPurchases,
    UserRole,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

admin_dependency = Annotated[dict, Depends(get_user)]


def ensure_admin(user: dict):
    if user["role"] != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ дозволений лише адміністратору",
        )


class TrainerCreateRequest(BaseModel):
    name: str
    specialization: str
    photo_url: Optional[str] = None
    rating: Optional[float] = 0.0
    description: Optional[str] = None
    experience_years: Optional[int] = 0
    price_per_session: Optional[float] = 0.0


class TrainerResponse(BaseModel):
    id: int
    name: str
    specialization: str
    photo_url: Optional[str]
    rating: float
    description: Optional[str]
    experience_years: int
    price_per_session: float

    class Config:
        from_attributes = True


class SubscriptionRequest(BaseModel):
    name: str
    subscription_type: str
    price: float
    duration_days: int
    visits_limit: Optional[int] = None


class SubscriptionResponse(BaseModel):
    id: int
    name: str
    subscription_type: str
    price: float
    duration_days: int
    visits_limit: Optional[int]

    class Config:
        from_attributes = True


class UserReportItem(BaseModel):
    id: int
    username: str
    email: str
    role: str
    subscription_active: bool
    subscription_expires_at: Optional[datetime]


class FinanceReportResponse(BaseModel):
    month: str
    total_amount: float
    total_sales: int


@router.get("/trainers", response_model=List[TrainerResponse])
async def list_trainers(db: db_dependency, user: admin_dependency):
    ensure_admin(user)
    return db.query(Trainers).all()


@router.post("/trainers", response_model=TrainerResponse, status_code=status.HTTP_201_CREATED)
async def create_trainer(payload: TrainerCreateRequest, db: db_dependency, user: admin_dependency):
    ensure_admin(user)
    trainer = Trainers(**payload.model_dump())
    db.add(trainer)
    db.commit()
    db.refresh(trainer)
    return trainer


@router.put("/trainers/{trainer_id}", response_model=TrainerResponse)
async def update_trainer(trainer_id: int, payload: TrainerCreateRequest, db: db_dependency, user: admin_dependency):
    ensure_admin(user)
    trainer = db.query(Trainers).filter(Trainers.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Тренер не знайдений")
    for field, value in payload.model_dump().items():
        setattr(trainer, field, value)
    db.commit()
    db.refresh(trainer)
    return trainer


@router.delete("/trainers/{trainer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trainer(trainer_id: int, db: db_dependency, user: admin_dependency):
    ensure_admin(user)
    trainer = db.query(Trainers).filter(Trainers.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Тренер не знайдений")
    db.delete(trainer)
    db.commit()
    return None


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(db: db_dependency, user: admin_dependency):
    ensure_admin(user)
    return db.query(Subscriptions).all()


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(payload: SubscriptionRequest, db: db_dependency, user: admin_dependency):
    ensure_admin(user)
    subscription = Subscriptions(**payload.model_dump())
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    payload: SubscriptionRequest,
    db: db_dependency,
    user: admin_dependency,
):
    ensure_admin(user)
    subscription = db.query(Subscriptions).filter(Subscriptions.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Абонемент не знайдено")
    for field, value in payload.model_dump().items():
        setattr(subscription, field, value)
    db.commit()
    db.refresh(subscription)
    return subscription


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(subscription_id: int, db: db_dependency, user: admin_dependency):
    ensure_admin(user)
    subscription = db.query(Subscriptions).filter(Subscriptions.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Абонемент не знайдено")
    db.delete(subscription)
    db.commit()
    return None


@router.get("/reports/users", response_model=List[UserReportItem])
async def users_report(db: db_dependency, user: admin_dependency):
    ensure_admin(user)
    users = db.query(Users).all()
    return users


@router.get("/reports/finance", response_model=FinanceReportResponse)
async def finance_report(
    month: str = Query(..., description="Місяць у форматі YYYY-MM"),
    db: db_dependency = None,
    user: admin_dependency = None,
):
    ensure_admin(user)
    try:
        start = datetime.fromisoformat(f"{month}-01")
        start = start.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Невірний формат month. Використовуйте YYYY-MM")

    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)

    total_amount = (
        db.query(func.coalesce(func.sum(SubscriptionPurchases.price), 0.0))
        .filter(
            SubscriptionPurchases.purchased_at >= start.replace(tzinfo=None),
            SubscriptionPurchases.purchased_at < end.replace(tzinfo=None),
        )
        .scalar()
    )
    total_sales = (
        db.query(func.count(SubscriptionPurchases.id))
        .filter(
            SubscriptionPurchases.purchased_at >= start.replace(tzinfo=None),
            SubscriptionPurchases.purchased_at < end.replace(tzinfo=None),
        )
        .scalar()
    )

    return FinanceReportResponse(
        month=month,
        total_amount=float(total_amount or 0.0),
        total_sales=int(total_sales or 0),
    )

