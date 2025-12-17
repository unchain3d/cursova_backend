from datetime import datetime, timedelta, date, time, timezone
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, field_validator
from models import (
    Users, Trainers, Subscriptions,
    SubscriptionPurchases,
    UserRole, SubscriptionType
)
from dependencies import db_dependency
from auth import get_user

router = APIRouter(
    prefix='/client',
    tags=['client']
)

user_dependency = Annotated[dict, Depends(get_user)]


def generate_time_slots(start_hour: int = 9, end_hour: int = 21) -> List[str]:
    """
    Генерує список доступних слотів
    """
    slots = []
    for hour in range(start_hour, end_hour):
        for minute in [0, 15, 30, 45]:
            time_str = f"{hour:02d}:{minute:02d}"
            slots.append(time_str)
    return slots


class TrainerResponse(BaseModel):
    id: int
    name: str
    specialization: str
    photo_url: Optional[str]
    rating: float

    class Config:
        from_attributes = True


class TrainerDetailResponse(BaseModel):
    id: int
    name: str
    specialization: str
    photo_url: Optional[str]
    rating: float
    description: Optional[str]

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    id: int
    name: str
    subscription_type: str
    price: float
    duration_days: int

    class Config:
        from_attributes = True


class PurchaseRequest(BaseModel):
    subscription_id: int


class ProfileResponse(BaseModel):
    username: str
    email: str
    subscription_type: Optional[str]
    subscription_expires_at: Optional[datetime]
    subscription_active: bool
    visit_history: List[dict]


class TimeSlotResponse(BaseModel):
    time: str
    datetime: datetime
    available: bool


@router.get("/trainers", response_model=List[TrainerResponse])
async def get_trainers(db: db_dependency, user: user_dependency):
    """
    Отримати список всіх тренерів
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )
    
    trainers = db.query(Trainers).all()
    return trainers


@router.get("/trainers/{trainer_id}", response_model=TrainerDetailResponse)
async def get_trainer_details(trainer_id: int, db: db_dependency, user: user_dependency):
    """
    Отримати детальну інформацію про тренера
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )
    
    trainer = db.query(Trainers).filter(Trainers.id == trainer_id).first()
    if not trainer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тренер не знайдений"
        )
    
    return trainer


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def get_subscriptions(db: db_dependency, user: user_dependency):
    """
    Отримати список доступних абонементів
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )
    
    subscriptions = db.query(Subscriptions).all()
    return subscriptions


@router.post("/purchase-subscription", status_code=status.HTTP_200_OK)
async def purchase_subscription(
    purchase_request: PurchaseRequest,
    db: db_dependency,
    user: user_dependency
):
    """
    Придбати абонемент
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )
    
    subscription = db.query(Subscriptions).filter(
        Subscriptions.id == purchase_request.subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Абонемент не знайдений"
        )
    
    db_user = db.query(Users).filter(Users.id == user['id']).first()
    
    now_utc = datetime.now(timezone.utc)
    
    if db_user.subscription_active and db_user.subscription_expires_at:
        expires_at_utc = db_user.subscription_expires_at
        if expires_at_utc.tzinfo is None:
            expires_at_utc = expires_at_utc.replace(tzinfo=timezone.utc)
        else:
            expires_at_utc = expires_at_utc.astimezone(timezone.utc)
            
        if expires_at_utc > now_utc:
            new_expires_at = expires_at_utc + timedelta(days=subscription.duration_days)
        else:
            new_expires_at = now_utc + timedelta(days=subscription.duration_days)
    else:
        new_expires_at = now_utc + timedelta(days=subscription.duration_days)
    
    db_user.subscription_expires_at = new_expires_at.replace(tzinfo=None)
    
    db_user.subscription_type = subscription.subscription_type
    db_user.subscription_active = True

    purchase = SubscriptionPurchases(
        user_id=user['id'],
        subscription_id=subscription.id,
        price=subscription.price,
        purchased_at=now_utc.replace(tzinfo=None)
    )
    db.add(purchase)
    
    db.commit()
    db.refresh(db_user)
    
    return {
        "message": "Абонемент успішно придбано",
        "subscription_type": db_user.subscription_type,
        "expires_at": db_user.subscription_expires_at
    }



